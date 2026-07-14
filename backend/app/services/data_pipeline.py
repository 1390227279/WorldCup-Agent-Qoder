"""Single dispatcher for verified snapshot parsing and source-specific loading."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_collection import DataCollectionRun
from app.services.data_loader import DataLoaderService
from app.services.data_parser import DataParserService
from app.services.historical_match_loader import HistoricalMatchLoaderService


@dataclass(slots=True)
class PipelineResult:
    run_id: int; status: str; raw_record_count: int
    inserted_record_count: int = 0; duplicate_record_count: int = 0
    updated_team_count: int = 0; skipped_record_count: int = 0
    errors: list[str] = field(default_factory=list); message: str = ""


class DataPipelineService:
    def __init__(self, parser: DataParserService | None = None) -> None:
        self.parser = parser or DataParserService()

    async def process(self, run: DataCollectionRun, db: AsyncSession) -> PipelineResult:
        run_id = run.id
        try:
            parsed = self.parser.parse_run(run)
            if run.source_name == "openfootball":
                loaded = await HistoricalMatchLoaderService().load(run, parsed, db)
                return PipelineResult(run.id, run.status, run.raw_record_count,
                    inserted_record_count=loaded.inserted_match_count,
                    duplicate_record_count=loaded.duplicate_match_count,
                    skipped_record_count=loaded.unmatched_team_count + loaded.invalid_match_count,
                    errors=loaded.errors,
                    message=f"新增 {loaded.inserted_match_count} 场历史比赛，跳过 {loaded.duplicate_match_count} 场重复比赛")
            if run.source_name in {"world_football_elo", "curated_elo_baseline"}:
                loaded = await DataLoaderService().load_metrics(run, parsed, db)
                return PipelineResult(run.id, run.status, run.raw_record_count,
                    updated_team_count=loaded.updated_team_count,
                    skipped_record_count=run.skipped_team_count, errors=loaded.errors,
                    message=f"成功更新 {loaded.updated_team_count} 支球队的 ELO 评分")
            raise ValueError(f"没有适用于 {run.source_name} 的加载流程")
        except Exception as exc:
            await db.rollback()
            persisted = await db.get(DataCollectionRun, run_id)
            if persisted is not None and persisted.status != "COMPLETED":
                persisted.status = "FAILED"; persisted.error_message = str(exc)[:2000]
                persisted.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
            raise
