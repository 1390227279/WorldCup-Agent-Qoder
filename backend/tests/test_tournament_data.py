import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, Team, Tournament, TournamentTeam
from app.models.seed import TEAMS_SEED, seed_all
from app.services.tournament_data import (
    DEFAULT_TOURNAMENT_DATA_PATH,
    EXPECTED_GROUPS,
    TournamentDataError,
    load_tournament_dataset,
    sync_tournament_dataset,
)


def test_versioned_scenario_dataset_has_valid_48_team_structure():
    dataset = load_tournament_dataset()

    assert dataset.tournament.dataset_kind == "SCENARIO"
    assert dataset.tournament.is_official is False
    assert dataset.tournament.source_url == "manual_mock_data"
    assert len(dataset.participants) == 48
    assert len({entry.fifa_code for entry in dataset.participants}) == 48
    for group in EXPECTED_GROUPS:
        group_entries = [
            entry for entry in dataset.participants if entry.group_name == group
        ]
        assert len(group_entries) == 4
        assert {entry.pot for entry in group_entries} == {1, 2, 3, 4}


def test_dataset_rejects_duplicate_fifa_codes(tmp_path):
    data = json.loads(DEFAULT_TOURNAMENT_DATA_PATH.read_text(encoding="utf-8"))
    data["participants"][1]["fifa_code"] = data["participants"][0]["fifa_code"]
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TournamentDataError, match="must be unique"):
        load_tournament_dataset(invalid_path)
@pytest.mark.asyncio
async def test_sync_adds_missing_teams_and_keeps_exactly_48_active_participants():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await seed_all(session)
        first_sync = await sync_tournament_dataset(session)
        await session.commit()
        second_sync = await sync_tournament_dataset(session)
        await session.commit()

        team_count = await session.scalar(select(func.count()).select_from(Team))
        active_count = await session.scalar(
            select(func.count())
            .select_from(TournamentTeam)
            .where(TournamentTeam.active.is_(True))
        )
        tournament = await session.scalar(
            select(Tournament).where(Tournament.code == "world-cup-2026")
        )

    await engine.dispose()

    assert team_count == len(TEAMS_SEED) + 7
    assert active_count == 48
    assert tournament.status == "SCENARIO"
    assert tournament.data_version == "user-scenario-20260713-v1"
    assert first_sync.teams_created == 0
    assert second_sync.teams_created == 0
    assert second_sync.participants_created == 0
