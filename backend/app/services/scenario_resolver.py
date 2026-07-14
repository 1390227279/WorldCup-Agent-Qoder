"""Resolve selected events into bounded, auditable scenario modifiers."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from numbers import Real
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event
from app.models.team import Team
from app.models.tournament import DEFAULT_TOURNAMENT_CODE, Tournament, TournamentTeam


ATTACK_LAMBDA_DELTA = "attack_lambda_delta"
CONCEDE_LAMBDA_DELTA = "concede_lambda_delta"
LEGACY_ATTACK_KEY = "attack"
LEGACY_DEFENSE_KEY = "defense"
MIN_EVENT_DELTA = -0.5
MAX_EVENT_DELTA = 0.5
IMPACT_MODE_MATH = "MATH"
IMPACT_MODE_NARRATIVE = "NARRATIVE"
IMPACT_MODE_INVALID = "INVALID"


class EventImpactError(ValueError):
    """Raised when an event impact contains ambiguous or invalid lambda values."""


@dataclass(frozen=True, slots=True)
class LambdaImpact:
    attack_lambda_delta: float = 0.0
    concede_lambda_delta: float = 0.0

    @property
    def has_effect(self) -> bool:
        return bool(self.attack_lambda_delta or self.concede_lambda_delta)

    def to_dict(self) -> dict[str, float]:
        return {
            ATTACK_LAMBDA_DELTA: self.attack_lambda_delta,
            CONCEDE_LAMBDA_DELTA: self.concede_lambda_delta,
        }


@dataclass(frozen=True, slots=True)
class AppliedScenarioEvent:
    event_id: int
    team_id: int
    team_code: str
    title: str
    impact: LambdaImpact

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "team_id": self.team_id,
            "team_code": self.team_code,
            "title": self.title,
            "impact": self.impact.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class NarrativeScenarioEvent:
    event_id: int
    team_id: int
    team_code: str
    type: str
    severity: str
    title: str
    description: str | None
    impact: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "team_id": self.team_id,
            "team_code": self.team_code,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "impact": self.impact,
        }


@dataclass(frozen=True, slots=True)
class IgnoredScenarioEvent:
    event_id: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "reason": self.reason}


@dataclass(slots=True)
class ScenarioResolution:
    requested_event_ids: list[int]
    team_impacts: dict[str, dict[str, float]] = field(default_factory=dict)
    math_events: list[AppliedScenarioEvent] = field(default_factory=list)
    narrative_events: list[NarrativeScenarioEvent] = field(default_factory=list)
    ignored_events: list[IgnoredScenarioEvent] = field(default_factory=list)
    team_math_event_ids: dict[str, list[int]] = field(default_factory=dict)
    team_narrative_event_ids: dict[str, list[int]] = field(default_factory=dict)
    event_content_fingerprint: str = field(
        default_factory=lambda: hashlib.sha256(b"[]").hexdigest()
    )

    @property
    def math_event_ids(self) -> list[int]:
        return [event.event_id for event in self.math_events]

    def audit_dict(self) -> dict[str, Any]:
        return {
            "requested_event_ids": self.requested_event_ids,
            "math_events": [event.to_dict() for event in self.math_events],
            "narrative_events": [
                event.to_dict() for event in self.narrative_events
            ],
            "ignored_events": [event.to_dict() for event in self.ignored_events],
            "team_impacts": self.team_impacts,
            "team_math_event_ids": self.team_math_event_ids,
            "team_narrative_event_ids": self.team_narrative_event_ids,
            "event_content_fingerprint": self.event_content_fingerprint,
        }


def parse_event_ids(value: str | Iterable[int] | None) -> list[int]:
    """Normalize event IDs into a sorted unique positive-integer list."""
    if value is None:
        return []
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
        parsed = [int(part) for part in values if part.isdigit() and int(part) > 0]
    else:
        parsed = [int(event_id) for event_id in value if int(event_id) > 0]
    return sorted(set(parsed))


def _numeric_delta(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EventImpactError(f"{field_name} 必须是数字")
    result = float(value)
    if result < MIN_EVENT_DELTA or result > MAX_EVENT_DELTA:
        raise EventImpactError(
            f"{field_name} 必须在 {MIN_EVENT_DELTA:.1f} 到 {MAX_EVENT_DELTA:.1f} 之间"
        )
    return result


def _resolve_alias(
    impact: dict[str, Any], canonical_key: str, legacy_key: str
) -> float:
    canonical_present = canonical_key in impact
    legacy_present = legacy_key in impact
    if canonical_present and legacy_present:
        canonical_value = _numeric_delta(impact[canonical_key], canonical_key)
        legacy_value = _numeric_delta(impact[legacy_key], legacy_key)
        if canonical_value != legacy_value:
            raise EventImpactError(f"{canonical_key} 与兼容字段 {legacy_key} 的值冲突")
        return canonical_value
    if canonical_present:
        return _numeric_delta(impact[canonical_key], canonical_key)
    if legacy_present:
        return _numeric_delta(impact[legacy_key], legacy_key)
    return 0.0


def extract_lambda_impact(impact: dict[str, Any] | None) -> LambdaImpact:
    """Read canonical fields while remaining compatible with legacy keys."""
    if impact is None:
        return LambdaImpact()
    if not isinstance(impact, dict):
        raise EventImpactError("impact 必须是 JSON 对象")
    return LambdaImpact(
        attack_lambda_delta=_resolve_alias(
            impact, ATTACK_LAMBDA_DELTA, LEGACY_ATTACK_KEY
        ),
        concede_lambda_delta=_resolve_alias(
            impact, CONCEDE_LAMBDA_DELTA, LEGACY_DEFENSE_KEY
        ),
    )


def classify_event_impact(impact: dict[str, Any] | None) -> str:
    """Classify whether an event changes mathematics or only enriches AI context."""
    try:
        lambda_impact = extract_lambda_impact(impact)
    except EventImpactError:
        return IMPACT_MODE_INVALID
    return IMPACT_MODE_MATH if lambda_impact.has_effect else IMPACT_MODE_NARRATIVE


def normalize_impact_for_storage(
    impact: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Store lambda modifiers canonically while preserving unrelated Agent fields."""
    if impact is None:
        return None
    if not isinstance(impact, dict):
        raise EventImpactError("impact 必须是 JSON 对象")

    normalized = {
        key: value
        for key, value in impact.items()
        if key
        not in {
            ATTACK_LAMBDA_DELTA,
            CONCEDE_LAMBDA_DELTA,
            LEGACY_ATTACK_KEY,
            LEGACY_DEFENSE_KEY,
        }
    }
    lambda_impact = extract_lambda_impact(impact)
    if ATTACK_LAMBDA_DELTA in impact or LEGACY_ATTACK_KEY in impact:
        normalized[ATTACK_LAMBDA_DELTA] = lambda_impact.attack_lambda_delta
    if CONCEDE_LAMBDA_DELTA in impact or LEGACY_DEFENSE_KEY in impact:
        normalized[CONCEDE_LAMBDA_DELTA] = lambda_impact.concede_lambda_delta
    return normalized


def event_is_current(event: Event, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    if not event.active:
        return False
    if event.effective_at is not None and event.effective_at > now:
        return False
    if event.expires_at is not None and event.expires_at <= now:
        return False
    return True


def _clamp(value: float) -> float:
    return max(MIN_EVENT_DELTA, min(MAX_EVENT_DELTA, value))


async def resolve_scenario_events(
    session: AsyncSession,
    event_ids: str | Iterable[int] | None,
    *,
    tournament_code: str = DEFAULT_TOURNAMENT_CODE,
    now: datetime | None = None,
) -> ScenarioResolution:
    """Resolve selected events for active participants of one tournament."""
    requested_ids = parse_event_ids(event_ids)
    resolution = ScenarioResolution(requested_event_ids=requested_ids)
    if not requested_ids:
        return resolution

    participant_rows = await session.execute(
        select(Team.id, Team.fifa_code)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .join(Tournament, Tournament.id == TournamentTeam.tournament_id)
        .where(
            Tournament.code == tournament_code,
            TournamentTeam.active.is_(True),
        )
    )
    active_team_codes = dict(participant_rows.all())

    event_rows = await session.execute(
        select(Event)
        .options(selectinload(Event.team))
        .where(Event.id.in_(requested_ids))
    )
    events_by_id = {event.id: event for event in event_rows.scalars().all()}
    current_time = now or datetime.utcnow()
    fingerprint_payload = []
    for event_id in requested_ids:
        event = events_by_id.get(event_id)
        if event is None:
            fingerprint_payload.append({"event_id": event_id, "missing": True})
            continue
        fingerprint_payload.append(
            {
                "event_id": event.id,
                "team_id": event.team_id,
                "type": event.type,
                "title": event.title,
                "severity": event.severity,
                "active": event.active,
                "impact": event.impact,
                "source": event.source,
                "source_type": event.source_type,
                "source_url": event.source_url,
                "external_id": event.external_id,
                "effective_at": (
                    event.effective_at.isoformat() if event.effective_at else None
                ),
                "expires_at": (
                    event.expires_at.isoformat() if event.expires_at else None
                ),
                "updated_at": (
                    event.updated_at.isoformat() if event.updated_at else None
                ),
            }
        )
    resolution.event_content_fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    totals: dict[str, LambdaImpact] = {}
    for event_id in requested_ids:
        event = events_by_id.get(event_id)
        if event is None:
            resolution.ignored_events.append(
                IgnoredScenarioEvent(event_id, "not_found")
            )
            continue
        if not event.active:
            resolution.ignored_events.append(IgnoredScenarioEvent(event_id, "inactive"))
            continue
        if event.effective_at is not None and event.effective_at > current_time:
            resolution.ignored_events.append(
                IgnoredScenarioEvent(event_id, "not_effective")
            )
            continue
        if event.expires_at is not None and event.expires_at <= current_time:
            resolution.ignored_events.append(IgnoredScenarioEvent(event_id, "expired"))
            continue

        team_code = active_team_codes.get(event.team_id)
        if team_code is None:
            resolution.ignored_events.append(
                IgnoredScenarioEvent(event_id, "team_not_in_tournament")
            )
            continue
        try:
            lambda_impact = extract_lambda_impact(event.impact)
        except EventImpactError:
            resolution.ignored_events.append(
                IgnoredScenarioEvent(event_id, "invalid_impact")
            )
            continue
        if not lambda_impact.has_effect:
            resolution.narrative_events.append(
                NarrativeScenarioEvent(
                    event_id=event.id,
                    team_id=event.team_id,
                    team_code=team_code,
                    type=event.type,
                    severity=event.severity,
                    title=event.title,
                    description=event.description,
                    impact=dict(event.impact or {}),
                )
            )
            resolution.team_narrative_event_ids.setdefault(team_code, []).append(
                event.id
            )
            continue

        previous = totals.get(team_code, LambdaImpact())
        totals[team_code] = LambdaImpact(
            attack_lambda_delta=(
                previous.attack_lambda_delta + lambda_impact.attack_lambda_delta
            ),
            concede_lambda_delta=(
                previous.concede_lambda_delta + lambda_impact.concede_lambda_delta
            ),
        )
        resolution.math_events.append(
            AppliedScenarioEvent(
                event_id=event.id,
                team_id=event.team_id,
                team_code=team_code,
                title=event.title,
                impact=lambda_impact,
            )
        )
        resolution.team_math_event_ids.setdefault(team_code, []).append(event.id)

    resolution.team_impacts = {
        team_code: LambdaImpact(
            attack_lambda_delta=_clamp(impact.attack_lambda_delta),
            concede_lambda_delta=_clamp(impact.concede_lambda_delta),
        ).to_dict()
        for team_code, impact in totals.items()
    }
    return resolution
