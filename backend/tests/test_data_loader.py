"""Integration tests for the full Fetch -> Parse -> Load pipeline."""

import hashlib
import json
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, DataCollectionChange, DataCollectionRun, Team
from app.services.data_loader import DataLoaderService
from app.services.data_parser import DataParserService, ParsedSnapshot, TeamEloJsonParser


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_teams(db):
    teams = [
        ("Argentina", "ARG", "CONMEBOL", 1, 2100.0),
        ("France", "FRA", "UEFA", 2, 2080.0),
        ("Brazil", "BRA", "CONMEBOL", 3, 2075.0),
        ("Qatar", "QAT", "AFC", 37, 1480.0),
    ]
    for name, code, confed, rank, elo in teams:
        db.add(Team(
            name=name, name_cn=name, fifa_code=code,
            confederation=confed, fifa_ranking=rank, elo_rating=elo,
        ))
    await db.commit()


@pytest.mark.asyncio
async def test_load_metrics_updates_elo_and_finalises_run(tmp_path, session):
    await _seed_teams(session)

    payload = json.dumps({"teams": [
        {"fifa_code": "ARG", "elo": 2130.0},
        {"fifa_code": "FRA", "elo": 2095.0},
        {"fifa_code": "BRA", "elo": 2080.0},
    ]}).encode()
    snapshot_dir = tmp_path / "resources" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = snapshot_dir / "elo_test.json"
    snapshot.write_bytes(payload)

    run = DataCollectionRun(
        source_name="world_football_elo",
        status="FETCHED",
        snapshot_path="resources/snapshots/elo_test.json",
        snapshot_bytes=len(payload),
        sha256_hash=hashlib.sha256(payload).hexdigest(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    parsed = DataParserService(app_root=tmp_path).parse_run(run)
    result = await DataLoaderService().load_metrics(run, parsed, session)

    assert result.updated_team_count == 3
    assert result.skipped_team_count == 0

    teams_result = await session.execute(select(Team))
    teams_by_code = {t.fifa_code: t.elo_rating for t in teams_result.scalars().all()}
    assert teams_by_code["ARG"] == 2130.0
    assert teams_by_code["FRA"] == 2095.0
    assert teams_by_code["BRA"] == 2080.0
    assert teams_by_code["QAT"] == 1480.0

    await session.refresh(run)
    assert run.status == "COMPLETED"
    assert run.updated_team_count == 3
    assert run.raw_record_count == 3
    changes = (await session.execute(select(DataCollectionChange))).scalars().all()
    assert len(changes) == 3 and all(change.change_status == "UPDATED" for change in changes)


@pytest.mark.asyncio
async def test_zero_matched_teams_is_marked_failed(tmp_path, session):
    await _seed_teams(session)

    payload = json.dumps({"teams": [
        {"fifa_code": "XYZ", "elo": 1900.0},
    ]}).encode()
    snapshot_dir = tmp_path / "resources" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = snapshot_dir / "no_match.json"
    snapshot.write_bytes(payload)

    run = DataCollectionRun(
        source_name="world_football_elo",
        status="FETCHED",
        snapshot_path="resources/snapshots/no_match.json",
        snapshot_bytes=len(payload),
        sha256_hash=hashlib.sha256(payload).hexdigest(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    parsed = DataParserService(app_root=tmp_path).parse_run(run)
    result = await DataLoaderService().load_metrics(run, parsed, session)

    assert result.updated_team_count == 0
    assert result.skipped_team_count > 0
    await session.refresh(run)
    assert run.status == "FAILED"
    assert run.error_message is not None


@pytest.mark.asyncio
async def test_load_metrics_rejects_non_fetched_run(session):
    run = DataCollectionRun(source_name="world_football_elo", status="FAILED")
    session.add(run)
    await session.commit()

    parsed = ParsedSnapshot(source_name="world_football_elo", raw_record_count=0)
    with pytest.raises(ValueError, match="FETCHED"):
        await DataLoaderService().load_metrics(run, parsed, session)


@pytest.mark.asyncio
async def test_elo_out_of_range_is_skipped_by_parser_not_loader(tmp_path, session):
    await _seed_teams(session)

    payload = json.dumps({"teams": [
        {"fifa_code": "ARG", "elo": 500.0},
        {"fifa_code": "FRA", "elo": 3000.0},
        {"fifa_code": "BRA", "elo": 2000.0},
    ]}).encode()
    snapshot_dir = tmp_path / "resources" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = snapshot_dir / "range_test.json"
    snapshot.write_bytes(payload)

    run = DataCollectionRun(
        source_name="world_football_elo",
        status="FETCHED",
        snapshot_path="resources/snapshots/range_test.json",
        snapshot_bytes=len(payload),
        sha256_hash=hashlib.sha256(payload).hexdigest(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    parsed = DataParserService(app_root=tmp_path).parse_run(run)
    assert parsed.raw_record_count == 3
    assert parsed.skipped_record_count == 2
    assert len(parsed.records) == 1

    result = await DataLoaderService().load_metrics(run, parsed, session)
    assert result.updated_team_count == 1
    assert result.skipped_team_count == 0


@pytest.mark.asyncio
async def test_loader_rejects_metric_records_from_a_different_source(session):
    run = DataCollectionRun(source_name="openfootball", status="FETCHED")
    session.add(run)
    await session.commit()
    parsed = TeamEloJsonParser().parse(json.dumps({"teams": [
        {"fifa_code": "ARG", "elo": 2140.0},
    ]}).encode())

    with pytest.raises(ValueError, match="来源"):
        await DataLoaderService().load_metrics(run, parsed, session)

    await session.refresh(run)
    assert run.status == "FETCHED"


@pytest.mark.asyncio
async def test_loader_rejects_snapshot_without_team_metrics(session):
    run = DataCollectionRun(source_name="openfootball", status="FETCHED")
    session.add(run)
    await session.commit()
    parsed = ParsedSnapshot(source_name="openfootball", raw_record_count=1)

    with pytest.raises(ValueError, match="不包含可加载"):
        await DataLoaderService().load_metrics(run, parsed, session)

    await session.refresh(run)
    assert run.status == "FETCHED"
