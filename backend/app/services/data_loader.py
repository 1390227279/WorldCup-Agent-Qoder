"""Data Loader — writes validated metric records into the database.

This is the final link in the data collection pipeline:
  Fetch → Parse → Load → Invalidate cache

Only TeamMetricRecord entries (ELO) are loaded into teams.elo_rating.
HistoricalMatchRecord entries are parsed but not loaded — they go into
a separate historical-matches pipeline later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.models.team import Team
from app.services.data_parser import ParsedSnapshot, TeamMetricRecord
from app.services.simulation_cache import get_simulation_cache

logger = logging.getLogger(__name__)

ELO_MIN = 800.0
ELO_MAX = 2500.0


class DataLoadError(ValueError):
    """Raised when the loading step cannot proceed or produces zero results."""


@dataclass(slots=True)
class LoadResult:
    updated_team_count: int = 0
    skipped_team_count: int = 0
    errors: list[str] = field(default_factory=list)


class DataLoaderService:
    """Load validated TeamMetricRecord entries into the live teams table.

    Only FETCHED runs can be loaded. After loading, the run transitions:
      FETCHING → FETCHED → PROCESSING → COMPLETED  (or FAILED)

    Zero matched teams is treated as a failure because it likely indicates
    a data format mismatch or a corrupted snapshot.
    """

    async def load_metrics(
        self,
        run: DataCollectionRun,
        parsed: ParsedSnapshot,
        db: AsyncSession,
    ) -> LoadResult:
        if run.status != "FETCHED":
            raise DataLoadError(
                f"只有 FETCHED 状态可以加载，当前状态：{run.status}"
            )

        metric_records = [
            r for r in parsed.records if isinstance(r, TeamMetricRecord)
        ]

        if parsed.source_name != run.source_name:
            raise DataLoadError(
                f"解析来源 {parsed.source_name} 与采集来源 {run.source_name} 不一致"
            )
        if not metric_records:
            raise DataLoadError("当前快照不包含可加载的球队指标")

        result = LoadResult()

        # ── Transition to PROCESSING ──────────────────────────
        run.status = "PROCESSING"
        run.raw_record_count = parsed.raw_record_count
        run.skipped_team_count = parsed.skipped_record_count
        await db.commit()

        # ── Resolve teams by fifa_code ────────────────────────
        teams_result = await db.execute(select(Team))
        teams_by_code: dict[str, Team] = {
            team.fifa_code.upper(): team
            for team in teams_result.scalars().all()
        }

        # ── Load each record ──────────────────────────────────
        for record in metric_records:
            try:
                if record.metric_type != "ELO":
                    result.skipped_team_count += 1
                    continue

                code = record.fifa_code.upper()
                team = teams_by_code.get(code)
                if team is None:
                    result.skipped_team_count += 1
                    result.errors.append(
                        f"ELO 记录 {code}：数据库中无此球队，跳过"
                    )
                    continue

                if not (ELO_MIN <= record.value <= ELO_MAX):
                    result.skipped_team_count += 1
                    result.errors.append(
                        f"ELO 记录 {code} 值 {record.value:.1f} "
                        f"超出合理范围 [{ELO_MIN:.0f}, {ELO_MAX:.0f}]"
                    )
                    continue

                team.elo_rating = record.value
                result.updated_team_count += 1

            except Exception as exc:
                result.skipped_team_count += 1
                result.errors.append(f"加载第 {record.source_index} 条记录失败：{exc}")

        # Finalise in the same transaction as team updates.
        if result.updated_team_count == 0 and result.skipped_team_count > 0:
            run.status = "FAILED"
            run.error_message = (
                f"ELO 加载失败：{result.updated_team_count} 支球队更新，"
                f"{result.skipped_team_count} 支球队跳过。"
                f"首批错误：{'; '.join(result.errors[:3])}"
            )[:2000]
        else:
            run.status = "COMPLETED"
            run.error_message = None
            if result.errors:
                run.error_message = (
                    f"部分成功 — {len(result.errors)} 个非致命问题："
                    f"{'; '.join(result.errors[:3])}"
                )[:2000]

        run.updated_team_count = result.updated_team_count
        run.skipped_team_count = (
            result.skipped_team_count + parsed.skipped_record_count
        )
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        # ── Invalidate simulation cache ───────────────────────
        if result.updated_team_count > 0:
            logger.info(
                "ELO 更新 %d 支球队，清除模拟缓存",
                result.updated_team_count,
            )
            get_simulation_cache().clear()

        return result
