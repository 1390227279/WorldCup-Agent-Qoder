"""Pure simulation inputs and deterministic random helpers."""

import hashlib
import json
import math
import zlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

from app.services.scenario_resolver import (
    ATTACK_LAMBDA_DELTA,
    CONCEDE_LAMBDA_DELTA,
)
from app.services.tournament_rules import GROUP_NAMES


MIN_EXPECTED_GOALS = 0.05
MAX_EXPECTED_GOALS = 8.0
MODEL_VERSION = "elo-poisson-deterministic-v1"
ADVANCEMENT_STAGES = ("R32", "R16", "QF", "SF", "FINAL", "CHAMPION")


class SimulationInputError(ValueError):
    """Raised when tournament simulation inputs are incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class TeamSimulationInput:
    id: int
    name: str
    name_cn: str
    fifa_code: str
    elo_rating: float
    tournament_group: str
    tournament_pot: int | None = None
    confederation: str | None = None
    fifa_ranking: int | None = None
    stats: dict[str, Any] | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeamSimulationInput":
        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            name_cn=str(data["name_cn"]),
            fifa_code=str(data.get("fifa_code", "")).upper(),
            elo_rating=float(data.get("elo_rating") or 1500.0),
            tournament_group=str(data.get("tournament_group", "")).upper(),
            tournament_pot=(
                int(data["tournament_pot"])
                if data.get("tournament_pot") is not None else None
            ),
            confederation=data.get("confederation"),
            fifa_ranking=data.get("fifa_ranking"),
            stats=dict(data["stats"]) if data.get("stats") else None,
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "name_cn": self.name_cn,
            "fifa_code": self.fifa_code,
            "confederation": self.confederation,
            "fifa_ranking": self.fifa_ranking,
            "elo_rating": self.elo_rating,
            "stats": self.stats,
        }


@dataclass(frozen=True, slots=True)
class TeamImpactInput:
    fifa_code: str
    attack_lambda_delta: float = 0.0
    concede_lambda_delta: float = 0.0


@dataclass(slots=True)
class TournamentOutcome:
    champion_team_id: int
    champion_name: str
    reached_team_ids: dict[str, tuple[int, ...]]
    log_likelihood: float
    stages: dict[str, dict] | None = None


@dataclass(frozen=True, slots=True)
class SimulationInput:
    teams: tuple[TeamSimulationInput, ...]
    iterations: int
    seed: int
    team_impacts: tuple[TeamImpactInput, ...] = ()
    event_ids: tuple[int, ...] = ()
    model_version: str = MODEL_VERSION

    @classmethod
    def from_raw(
        cls,
        teams: Iterable[dict[str, Any]],
        *,
        iterations: int,
        seed: int,
        team_impacts: dict[str, dict[str, float]] | None = None,
        event_ids: Iterable[int] | None = None,
    ) -> "SimulationInput":
        normalized_teams = tuple(
            sorted(
                (TeamSimulationInput.from_dict(team) for team in teams),
                key=lambda team: (
                    team.tournament_group,
                    team.tournament_pot or 99,
                    team.id,
                ),
            )
        )
        impacts = tuple(
            TeamImpactInput(
                fifa_code=code.upper(),
                attack_lambda_delta=float(values.get(ATTACK_LAMBDA_DELTA, 0.0)),
                concede_lambda_delta=float(values.get(CONCEDE_LAMBDA_DELTA, 0.0)),
            )
            for code, values in sorted((team_impacts or {}).items())
        )
        result = cls(
            teams=normalized_teams,
            iterations=int(iterations),
            seed=int(seed),
            team_impacts=impacts,
            event_ids=tuple(sorted(set(event_ids or []))),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.iterations <= 0:
            raise SimulationInputError("iterations must be positive")
        if self.seed <= 0:
            raise SimulationInputError("seed must be positive")
        if len(self.teams) != 48:
            raise SimulationInputError(
                f"A 2026 tournament simulation requires 48 teams, got {len(self.teams)}"
            )
        if len({team.id for team in self.teams}) != len(self.teams):
            raise SimulationInputError("Team IDs must be unique")
        if len({team.fifa_code for team in self.teams}) != len(self.teams):
            raise SimulationInputError("FIFA codes must be unique")
        group_counts = {
            group: sum(team.tournament_group == group for team in self.teams)
            for group in GROUP_NAMES
        }
        if any(count != 4 for count in group_counts.values()):
            raise SimulationInputError(
                f"Every group A-L must contain four teams, got {group_counts}"
            )

    @property
    def impact_by_code(self) -> dict[str, dict[str, float]]:
        return {
            impact.fifa_code: {
                ATTACK_LAMBDA_DELTA: impact.attack_lambda_delta,
                CONCEDE_LAMBDA_DELTA: impact.concede_lambda_delta,
            }
            for impact in self.team_impacts
        }

    def fingerprint(self) -> str:
        payload = {
            "teams": [
                {
                    "id": team.id,
                    "code": team.fifa_code,
                    "elo": team.elo_rating,
                    "group": team.tournament_group,
                    "pot": team.tournament_pot,
                }
                for team in self.teams
            ],
            "iterations": self.iterations,
            "seed": self.seed,
            "impacts": [
                {
                    "code": impact.fifa_code,
                    "attack": impact.attack_lambda_delta,
                    "concede": impact.concede_lambda_delta,
                }
                for impact in self.team_impacts
            ],
            "event_ids": self.event_ids,
            "model_version": self.model_version,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()


def derive_child_seed(master_seed: int, *parts: object) -> int:
    """Derive a stable positive 63-bit seed without Python's randomized hash()."""
    material = "|".join([str(master_seed), *(str(part) for part in parts)])
    digest = hashlib.blake2b(material.encode("utf-8"), digest_size=8).digest()
    return (int.from_bytes(digest, "big") & ((1 << 63) - 1)) or 1


@lru_cache(maxsize=1024)
def _stable_slot_key(parts: tuple[object, ...]) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    low = zlib.crc32(material)
    high = zlib.crc32(material, 0xA5A5A5A5)
    return (high << 32) | low


class KeyedRandom:
    """Independent deterministic random values keyed by tournament match slots."""

    def __init__(self, seed: int):
        if seed <= 0:
            raise SimulationInputError("Random seed must be positive")
        self.seed = seed

    def uniform(self, *parts: object) -> float:
        value = self.seed ^ _stable_slot_key(parts)
        # SplitMix64: fast, deterministic, and stable across Python processes.
        value = (value + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
        value ^= value >> 31
        return (value + 0.5) / float(1 << 64)

    def poisson(self, expected_goals: float, *parts: object) -> int:
        rate = clamp_expected_goals(expected_goals)
        uniform = self.uniform(*parts)
        probability = math.exp(-rate)
        cumulative = probability
        goals = 0
        while uniform > cumulative:
            goals += 1
            probability *= rate / goals
            cumulative += probability
        return goals


def clamp_expected_goals(expected_goals: float) -> float:
    return max(MIN_EXPECTED_GOALS, min(MAX_EXPECTED_GOALS, expected_goals))


def poisson_log_probability(goals: int, expected_goals: float) -> float:
    """Stable log probability for one sampled Poisson score."""
    rate = clamp_expected_goals(expected_goals)
    return goals * math.log(rate) - rate - math.lgamma(goals + 1)
