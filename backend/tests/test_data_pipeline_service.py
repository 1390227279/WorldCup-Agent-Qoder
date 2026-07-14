import hashlib, json
from pathlib import Path
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.models import Base, DataCollectionRun, HistoricalMatch, Team
from app.services.data_parser import DataParserService
from app.services.data_pipeline import DataPipelineService

@pytest.fixture
async def session():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async with factory() as db:
        db.add_all([Team(name="Argentina",name_cn="阿根廷",fifa_code="ARG",confederation="CONMEBOL"),Team(name="France",name_cn="法国",fifa_code="FRA",confederation="UEFA")]); await db.commit(); yield db
    await engine.dispose()

async def make_run(db, root: Path, source: str, payload: dict):
    content=json.dumps(payload).encode(); folder=root/"resources/snapshots"; folder.mkdir(parents=True); (folder/"raw.json").write_bytes(content)
    run=DataCollectionRun(source_name=source,status="FETCHED",snapshot_path="resources/snapshots/raw.json",snapshot_bytes=len(content),sha256_hash=hashlib.sha256(content).hexdigest()); db.add(run); await db.commit(); await db.refresh(run); return run

@pytest.mark.asyncio
async def test_pipeline_dispatches_openfootball(tmp_path,session):
    run=await make_run(session,tmp_path,"openfootball",{"matches":[{"date":"2022-12-18","team1":"ARG","team2":"FRA","score":{"ft":[3,3]}}]})
    result=await DataPipelineService(DataParserService(app_root=tmp_path)).process(run,session)
    assert result.inserted_record_count==1 and result.status=="COMPLETED"
    assert (await session.execute(select(func.count()).select_from(HistoricalMatch))).scalar_one()==1

@pytest.mark.asyncio
async def test_pipeline_marks_unknown_source_failed(tmp_path,session):
    run=await make_run(session,tmp_path,"unknown",{"teams":[]})
    with pytest.raises(ValueError): await DataPipelineService(DataParserService(app_root=tmp_path)).process(run,session)
    await session.refresh(run); assert run.status=="FAILED"
