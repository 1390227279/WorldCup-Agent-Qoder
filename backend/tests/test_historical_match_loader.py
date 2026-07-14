from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, DataCollectionChange, DataCollectionRun, HistoricalMatch, Team
from app.services.data_parser import HistoricalMatchRecord, ParsedSnapshot
from app.services.historical_match_loader import HistoricalMatchLoaderService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add_all([Team(name="Argentina", name_cn="阿根廷", fifa_code="ARG", confederation="CONMEBOL"), Team(name="France", name_cn="法国", fifa_code="FRA", confederation="UEFA")])
        await db.commit(); yield db
    await engine.dispose()


def parsed():
    return ParsedSnapshot(source_name="openfootball", raw_record_count=1, records=[HistoricalMatchRecord(1, date(2022,12,18), "World Cup 2022", "Final", "ARG", "FRA", 3, 3)])


@pytest.mark.asyncio
async def test_loader_inserts_and_deduplicates_matches(session):
    first = DataCollectionRun(source_name="openfootball", status="FETCHED"); session.add(first); await session.commit(); await session.refresh(first)
    result = await HistoricalMatchLoaderService().load(first, parsed(), session)
    assert result.inserted_match_count == 1 and first.status == "COMPLETED"
    assert (await session.execute(select(func.count()).select_from(DataCollectionChange))).scalar_one() == 1
    second = DataCollectionRun(source_name="openfootball", status="FETCHED"); session.add(second); await session.commit(); await session.refresh(second)
    result = await HistoricalMatchLoaderService().load(second, parsed(), session)
    assert result.duplicate_match_count == 1
    assert (await session.execute(select(func.count()).select_from(HistoricalMatch))).scalar_one() == 1


@pytest.mark.asyncio
async def test_loader_marks_zero_match_as_failed(session):
    run = DataCollectionRun(source_name="openfootball", status="FETCHED"); session.add(run); await session.commit(); await session.refresh(run)
    bad = ParsedSnapshot(source_name="openfootball", raw_record_count=1, records=[HistoricalMatchRecord(1, date(2022,1,1), "Cup", "Group", "XXX", "FRA", 1, 0)])
    result = await HistoricalMatchLoaderService().load(run, bad, session)
    assert result.unmatched_team_count == 1 and run.status == "FAILED"
