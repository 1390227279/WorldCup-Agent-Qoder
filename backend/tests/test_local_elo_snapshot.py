import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, DataCollectionRun, Team
from app.models.seed import seed_all
from app.services.data_loader import DataLoaderService
from app.services.data_parser import DataParserService


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_all(session)
        yield session
    await engine.dispose()


def _create_run_from_file(db_session, tmp_path, source_name):
    """Helper: create a FETCHED run from a local snapshot file."""
    snapshot_path = (
        Path(__file__).resolve().parent.parent
        / "app/resources/snapshots/world_football_elo_20260714.json"
    )
    content = snapshot_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()

    dest = tmp_path / "resources/snapshots/snapshot.json"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(content)

    run = DataCollectionRun(
        source_name=source_name,
        status="FETCHED",
        snapshot_path="resources/snapshots/snapshot.json",
        snapshot_bytes=len(content),
        sha256_hash=digest,
    )
    db_session.add(run)
    return run


@pytest.mark.asyncio
async def test_local_elo_snapshot_is_parseable(tmp_path, db_session):
    run = _create_run_from_file(db_session, tmp_path, "world_football_elo")
    await db_session.commit()
    await db_session.refresh(run)

    parsed = DataParserService(app_root=tmp_path).parse_run(run)
    assert parsed.raw_record_count == 48
    assert len(parsed.records) == 48
    assert all(
        hasattr(record, "fifa_code") and len(record.fifa_code) == 3
        for record in parsed.records
    )


@pytest.mark.asyncio
async def test_local_elo_snapshot_loads_all_48_teams(tmp_path, db_session):
    run = _create_run_from_file(db_session, tmp_path, "world_football_elo")
    await db_session.commit()
    await db_session.refresh(run)

    parsed = DataParserService(app_root=tmp_path).parse_run(run)
    result = await DataLoaderService().load_metrics(run, parsed, db_session)

    assert result.updated_team_count == 48
    assert result.skipped_team_count == 0
    await db_session.refresh(run)
    assert run.status == "COMPLETED"

    teams = (await db_session.execute(select(Team))).scalars().all()
    assert all(
        team.elo_rating is not None and 800 <= team.elo_rating <= 2500
        for team in teams
    )
