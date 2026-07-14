import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.models import Base
from app.services.local_baseline import LocalBaselineService

@pytest.mark.asyncio
async def test_local_baseline_registration_is_traceable_and_idempotent():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async with factory() as db:
        first=await LocalBaselineService().register(db); second=await LocalBaselineService().register(db)
        assert first.id==second.id
        assert first.acquisition_method=="CURATED_LOCAL_BASELINE"
        assert first.http_status is None and len(first.sha256_hash)==64 and first.status=="FETCHED"
    await engine.dispose()
