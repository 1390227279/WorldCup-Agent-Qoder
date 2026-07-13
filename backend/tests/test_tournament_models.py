import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.models import Base, Team, Tournament, TournamentTeam
from app.models.seed import TEAMS_SEED, seed_all


def test_tournament_team_keeps_edition_specific_attributes():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(
            name="Argentina",
            name_cn="阿根廷",
            fifa_code="ARG",
            confederation="CONMEBOL",
        )
        tournament = Tournament(
            code="world-cup-2026-test",
            name="World Cup 2026 Test",
            name_cn="2026 世界杯测试",
            year=2026,
        )
        participant = TournamentTeam(
            tournament=tournament,
            team=team,
            group_name="C",
            pot=1,
            qualification_status="LEGACY",
            active=True,
        )
        session.add(participant)
        session.flush()

        assert participant in tournament.participants
        assert participant in team.tournament_entries
        assert participant.to_dict()["group_name"] == "C"
        assert tournament.to_dict()["code"] == "world-cup-2026-test"


@pytest.mark.asyncio
async def test_seed_creates_default_tournament_participants():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await seed_all(session)
        participant_count = await session.scalar(
            select(func.count()).select_from(TournamentTeam)
        )
        tournament_count = await session.scalar(
            select(func.count()).select_from(Tournament)
        )

    await engine.dispose()

    assert tournament_count == 1
    assert participant_count == len(TEAMS_SEED) == 48
