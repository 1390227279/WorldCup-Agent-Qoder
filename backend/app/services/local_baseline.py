import hashlib
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_collection import DataCollectionRun

BASELINE_PATH = Path(__file__).resolve().parent.parent / "resources/snapshots/world_football_elo_20260714.json"

class LocalBaselineService:
    async def register(self, db: AsyncSession) -> DataCollectionRun:
        content = BASELINE_PATH.read_bytes(); digest = hashlib.sha256(content).hexdigest()
        existing = (await db.execute(select(DataCollectionRun).where(
            DataCollectionRun.source_name == "curated_elo_baseline",
            DataCollectionRun.sha256_hash == digest,
        ).order_by(DataCollectionRun.id.desc()))).scalars().first()
        if existing is not None: return existing
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run = DataCollectionRun(source_name="curated_elo_baseline", source_url=None,
            acquisition_method="CURATED_LOCAL_BASELINE", started_at=now, completed_at=now,
            status="FETCHED", snapshot_path="resources/snapshots/world_football_elo_20260714.json",
            snapshot_bytes=len(content), sha256_hash=digest)
        db.add(run); await db.commit(); await db.refresh(run); return run
