import hashlib
import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, DataCollectionRun
from app.services.data_fetcher import DataFetchError, DataFetcherService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_fetcher_persists_raw_response_before_marking_run_fetched(tmp_path, session):
    payload = {"name": "World Cup 2022", "matches": [{"team1": "ARG", "team2": "FRA"}]}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200,
        content=raw,
        headers={"content-type": "application/json"},
        request=request,
    ))
    async with httpx.AsyncClient(transport=transport) as client:
        run = await DataFetcherService(client=client, snapshot_root=tmp_path).fetch(
            "openfootball_worldcup_2022", session
        )

    snapshots = list(tmp_path.glob("*_openfootball_*_raw.json"))
    assert len(snapshots) == 1
    assert snapshots[0].read_bytes() == raw
    assert run.status == "FETCHED"
    assert run.http_status == 200
    assert run.snapshot_bytes == len(raw)
    assert run.sha256_hash == hashlib.sha256(raw).hexdigest()
    assert run.snapshot_path.endswith(snapshots[0].name)
    assert run.updated_team_count == 0


@pytest.mark.asyncio
async def test_fetcher_records_http_failure_without_creating_snapshot(tmp_path, session):
    transport = httpx.MockTransport(lambda request: httpx.Response(
        503,
        text="temporarily unavailable",
        request=request,
    ))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(DataFetchError) as caught:
            await DataFetcherService(client=client, snapshot_root=tmp_path).fetch(
                "openfootball_worldcup_2022", session
            )

    run = (await session.execute(select(DataCollectionRun))).scalar_one()
    assert caught.value.run_id == run.id
    assert run.status == "FAILED"
    assert run.http_status == 503
    assert run.snapshot_path is None
    assert run.completed_at is not None
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_fetcher_rejects_unknown_source_without_arbitrary_request(session):
    with pytest.raises(DataFetchError, match="未知或未授权"):
        await DataFetcherService().fetch("https://attacker.invalid/data", session)
    assert (await session.execute(select(DataCollectionRun))).scalars().all() == []


@pytest.mark.asyncio
async def test_fetcher_rejects_oversized_response_and_leaves_failure_receipt(tmp_path, session):
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200,
        content=b"{}" * 20,
        headers={"content-type": "application/json"},
        request=request,
    ))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(DataFetchError, match="超过允许上限"):
            await DataFetcherService(client=client, snapshot_root=tmp_path, max_snapshot_bytes=10).fetch(
                "openfootball_worldcup_2022", session
            )
    run = (await session.execute(select(DataCollectionRun))).scalar_one()
    assert run.status == "FAILED"
    assert run.snapshot_path is None
