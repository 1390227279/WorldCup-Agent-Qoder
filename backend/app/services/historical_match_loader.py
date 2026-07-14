"""Load normalized openfootball matches with deterministic deduplication."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.models.historical_match import HistoricalMatch
from app.models.team import Team
from app.services.data_parser import HistoricalMatchRecord, ParsedSnapshot


class HistoricalMatchLoadError(ValueError):
    pass


@dataclass(slots=True)
class HistoricalMatchLoadResult:
    inserted_match_count: int = 0
    duplicate_match_count: int = 0
    unmatched_team_count: int = 0
    invalid_match_count: int = 0
    errors: list[str] = field(default_factory=list)


def match_fingerprint(record: HistoricalMatchRecord) -> str:
    raw = "|".join((record.match_date.isoformat(), record.tournament, record.stage,
        record.home_fifa_code, record.away_fifa_code, str(record.home_goals), str(record.away_goals)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class HistoricalMatchLoaderService:
    async def load(self, run: DataCollectionRun, parsed: ParsedSnapshot, db: AsyncSession) -> HistoricalMatchLoadResult:
        if run.status != "FETCHED":
            raise HistoricalMatchLoadError(f"只有 FETCHED 状态可以导入，当前状态：{run.status}")
        if run.source_name != parsed.source_name or run.source_name != "openfootball":
            raise HistoricalMatchLoadError("采集来源与历史比赛解析器不匹配")
        records = [item for item in parsed.records if isinstance(item, HistoricalMatchRecord)]
        if not records:
            raise HistoricalMatchLoadError("快照中没有可导入的历史比赛")

        run.status = "PROCESSING"
        run.raw_record_count = parsed.raw_record_count
        await db.commit()
        result = HistoricalMatchLoadResult(invalid_match_count=parsed.skipped_record_count)
        result.errors.extend(parsed.errors)
        teams = (await db.execute(select(Team))).scalars().all()
        teams_by_code = {team.fifa_code.upper(): team for team in teams}
        fingerprints = [match_fingerprint(record) for record in records]
        existing = set((await db.execute(select(HistoricalMatch.match_fingerprint).where(
            HistoricalMatch.match_fingerprint.in_(fingerprints)
        ))).scalars())

        for record, fingerprint in zip(records, fingerprints, strict=True):
            home = teams_by_code.get(record.home_fifa_code)
            away = teams_by_code.get(record.away_fifa_code)
            if home is None or away is None:
                result.unmatched_team_count += 1
                result.errors.append(f"第 {record.source_index} 条：无法匹配 {record.home_fifa_code}/{record.away_fifa_code}")
                continue
            if fingerprint in existing:
                result.duplicate_match_count += 1
                continue
            db.add(HistoricalMatch(
                match_date=record.match_date, tournament=record.tournament, stage=record.stage,
                home_team_id=home.id, away_team_id=away.id,
                home_fifa_code=record.home_fifa_code, away_fifa_code=record.away_fifa_code,
                home_goals=record.home_goals, away_goals=record.away_goals,
                source_name=run.source_name, source_run_id=run.id,
                external_match_id=str(record.source_index), match_fingerprint=fingerprint,
            ))
            existing.add(fingerprint)
            result.inserted_match_count += 1

        run.inserted_record_count = result.inserted_match_count
        run.duplicate_record_count = result.duplicate_match_count
        run.skipped_team_count = result.unmatched_team_count + result.invalid_match_count
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if result.inserted_match_count == 0 and result.duplicate_match_count == 0:
            run.status = "FAILED"
            run.error_message = "; ".join(result.errors[:5])[:2000] or "没有可导入的历史比赛"
        else:
            run.status = "COMPLETED"
            run.error_message = "; ".join(result.errors[:5])[:2000] or None
        await db.commit()
        return result
