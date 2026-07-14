from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, Event, Team
from app.models.seed import seed_all
from app.services.scenario_resolver import (
    EventImpactError,
    extract_lambda_impact,
    normalize_impact_for_storage,
    resolve_scenario_events,
)


def test_normalizes_legacy_lambda_fields_for_storage():
    normalized = normalize_impact_for_storage({
        "attack": -0.1,
        "defense": 0.2,
        "morale": -0.05,
    })

    assert normalized == {
        "attack_lambda_delta": -0.1,
        "concede_lambda_delta": 0.2,
        "morale": -0.05,
    }
    assert extract_lambda_impact(normalized).to_dict() == {
        "attack_lambda_delta": -0.1,
        "concede_lambda_delta": 0.2,
    }


def test_rejects_conflicting_or_out_of_range_lambda_fields():
    with pytest.raises(EventImpactError, match="值冲突"):
        normalize_impact_for_storage({
            "attack": -0.1,
            "attack_lambda_delta": -0.2,
        })
    with pytest.raises(EventImpactError, match="必须在"):
        normalize_impact_for_storage({"concede_lambda_delta": 0.8})


@pytest.mark.asyncio
async def test_resolver_filters_events_clamps_totals_and_preserves_elo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    now = datetime(2026, 7, 13, 12, 0, 0)
    async with session_factory() as session:
        await seed_all(session)
        argentina = await session.scalar(select(Team).where(Team.fifa_code == "ARG"))
        inactive_team = await session.scalar(select(Team).where(Team.fifa_code == "AUT"))
        original_elo = argentina.elo_rating
        events = [
            Event(team_id=argentina.id, type="INJURY", title="进攻影响1", severity="MAJOR", impact={"attack": 0.4}),
            Event(team_id=argentina.id, type="INJURY", title="进攻影响2", severity="MAJOR", impact={"attack_lambda_delta": 0.4, "concede_lambda_delta": 0.1}),
            Event(team_id=argentina.id, type="TACTICAL", title="进攻反向修正", severity="MINOR", impact={"attack_lambda_delta": -0.4}),
            Event(team_id=argentina.id, type="MORALE", title="仅文本影响", severity="MINOR", impact={"morale": 0.1}),
            Event(team_id=argentina.id, type="INJURY", title="已停用", severity="MINOR", impact={"attack": -0.1}, active=False),
            Event(team_id=argentina.id, type="INJURY", title="未生效", severity="MINOR", impact={"attack": -0.1}, effective_at=now + timedelta(days=1)),
            Event(team_id=argentina.id, type="INJURY", title="已过期", severity="MINOR", impact={"attack": -0.1}, expires_at=now),
            Event(team_id=inactive_team.id, type="INJURY", title="非参赛球队", severity="MINOR", impact={"attack": -0.1}),
        ]
        session.add_all(events)
        await session.commit()

        resolution = await resolve_scenario_events(
            session,
            [event.id for event in events] + [999999],
            now=now,
        )
        await session.refresh(argentina)

    await engine.dispose()

    assert resolution.team_impacts["ARG"] == {
        "attack_lambda_delta": 0.4,
        "concede_lambda_delta": 0.1,
    }
    assert len(resolution.math_events) == 3
    assert [event.title for event in resolution.narrative_events] == ["仅文本影响"]
    assert {ignored.reason for ignored in resolution.ignored_events} == {
        "inactive",
        "not_effective",
        "expired",
        "team_not_in_tournament",
        "not_found",
    }
    assert argentina.elo_rating == original_elo
