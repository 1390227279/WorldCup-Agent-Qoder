from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.models import Base, DataCollectionRun, HistoricalMatch, Team
from app.services.agent_service import AgentService

@pytest.mark.asyncio
async def test_agent_history_tools_read_database_and_report_evidence():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async with factory() as db:
        arg=Team(name="Argentina",name_cn="阿根廷",fifa_code="ARG",confederation="CONMEBOL"); fra=Team(name="France",name_cn="法国",fifa_code="FRA",confederation="UEFA")
        db.add_all([arg,fra]); await db.commit()
        run=DataCollectionRun(source_name="openfootball",status="COMPLETED",sha256_hash="a"*64); db.add(run); await db.commit()
        db.add(HistoricalMatch(match_date=date(2022,12,18),tournament="World Cup 2022",stage="Final",home_team_id=arg.id,away_team_id=fra.id,home_fifa_code="ARG",away_fifa_code="FRA",home_goals=3,away_goals=3,source_name="openfootball",source_run_id=run.id,match_fingerprint="b"*64)); await db.commit()
        service=AgentService()
        recent=await service._tool_get_recent_form({"team_name":"ARG","n_matches":5},db)
        h2h=await service._tool_get_h2h_record({"team_a":"阿根廷","team_b":"法国"},db)
        assert "3-3" in recent and "#1 openfootball aaaaaaaa" in recent
        assert "已采集交锋共 1 场" in h2h
    await engine.dispose()

@pytest.mark.asyncio
async def test_agent_does_not_silently_fallback_to_builtin_history():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async with factory() as db:
        db.add(Team(name="Argentina",name_cn="阿根廷",fifa_code="ARG",confederation="CONMEBOL")); await db.commit()
        result=await AgentService()._tool_get_recent_form({"team_name":"ARG"},db)
        assert "暂无" in result and "未使用硬编码" in result
    await engine.dispose()
