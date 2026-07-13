"""Database initialization and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables and load seed data on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from app.models.migrations import run_migrations
        await conn.run_sync(run_migrations)

    # Seed data loading
    from app.models.seed import seed_all
    async with async_session() as session:
        await seed_all(session)


async def get_db() -> AsyncSession:
    """Dependency injection: yield an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
