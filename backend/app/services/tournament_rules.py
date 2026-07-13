"""Deterministic qualification and bracket-slot rules for scenario tournaments."""

from dataclasses import dataclass, field
from typing import Any, Iterable


GROUP_NAMES = tuple("ABCDEFGHIJKL")
SCENARIO_RULES_VERSION = "scenario-fixed-v1"


class TournamentRulesError(ValueError):
    """Raised when group standings cannot produce a valid knockout bracket."""


@dataclass(frozen=True, slots=True)
class GroupStanding:
    """One team's completed group-stage standing and its simulator payload."""

    team_id: int
    group_name: str
    points: int
    goal_difference: int
    goals_for: int
    elo_rating: float
    payload: Any = field(compare=False, repr=False)

    @property
    def ranking_key(self) -> tuple[int, int, int, float, int]:
        # Lower team ID is the final deterministic tiebreaker.
        return (
            self.points,
            self.goal_difference,
            self.goals_for,
            self.elo_rating,
            -self.team_id,
        )

@dataclass(frozen=True, slots=True)
class QualifiedTeam:
    standing: GroupStanding
    group_position: int

    @property
    def team_id(self) -> int:
        return self.standing.team_id

    @property
    def group_name(self) -> str:
        return self.standing.group_name

    @property
    def payload(self) -> Any:
        return self.standing.payload

    @property
    def source_slot(self) -> str:
        return f"GROUP_{self.group_name}_{self.group_position}"


@dataclass(frozen=True, slots=True)
class BracketSlot:
    team_id: int
    payload: Any
    source_slot: str
    group_name: str | None = None


@dataclass(frozen=True, slots=True)
class RoundOf32Pairing:
    home: BracketSlot
    away: BracketSlot


def rank_group(standings: Iterable[GroupStanding]) -> tuple[QualifiedTeam, ...]:
    """Rank one four-team group using deterministic tournament tiebreakers."""
    records = list(standings)
    if len(records) != 4:
        raise TournamentRulesError(
            f"Each group must contain four standings, got {len(records)}"
        )
    groups = {record.group_name for record in records}
    if len(groups) != 1 or next(iter(groups)) not in GROUP_NAMES:
        raise TournamentRulesError("A group ranking must contain one valid group A-L")
    if len({record.team_id for record in records}) != 4:
        raise TournamentRulesError("A group cannot contain duplicate teams")

    ranked = sorted(records, key=lambda record: record.ranking_key, reverse=True)
    return tuple(
        QualifiedTeam(standing=record, group_position=index + 1)
        for index, record in enumerate(ranked)
    )


def select_knockout_qualifiers(
    group_rankings: dict[str, tuple[QualifiedTeam, ...]],
) -> tuple[
    dict[str, QualifiedTeam],
    dict[str, QualifiedTeam],
    tuple[QualifiedTeam, ...],
]:
    """Select 12 winners, 12 runners-up, and the eight best thirds."""
    if set(group_rankings) != set(GROUP_NAMES):
        raise TournamentRulesError("Group rankings must contain every group A-L")

    winners = {}
    runners_up = {}
    thirds = []
    all_team_ids = set()
    for group_name in GROUP_NAMES:
        ranking = group_rankings[group_name]
        if len(ranking) != 4:
            raise TournamentRulesError(f"Group {group_name} must contain four teams")
        winners[group_name] = ranking[0]
        runners_up[group_name] = ranking[1]
        thirds.append(ranking[2])
        for team in ranking:
            if team.team_id in all_team_ids:
                raise TournamentRulesError("A team cannot appear in multiple groups")
            all_team_ids.add(team.team_id)

    best_thirds = tuple(
        sorted(
            thirds,
            key=lambda team: team.standing.ranking_key,
            reverse=True,
        )[:8]
    )
    return winners, runners_up, best_thirds


def _assign_thirds_without_group_rematches(
    winner_groups: tuple[str, ...],
    best_thirds: tuple[QualifiedTeam, ...],
) -> tuple[QualifiedTeam, ...]:
    """Assign third-place teams deterministically while avoiding group rematches."""
    preferred = tuple(reversed(best_thirds))  # weaker qualifiers face earlier winners
    assigned: list[QualifiedTeam] = []
    used_team_ids = set()

    def search(index: int) -> bool:
        if index == len(winner_groups):
            return True
        winner_group = winner_groups[index]
        for candidate in preferred:
            if candidate.team_id in used_team_ids:
                continue
            if candidate.group_name == winner_group:
                continue
            assigned.append(candidate)
            used_team_ids.add(candidate.team_id)
            if search(index + 1):
                return True
            used_team_ids.remove(candidate.team_id)
            assigned.pop()
        return False

    if not search(0):
        raise TournamentRulesError(
            "Unable to assign best third-place teams without a group rematch"
        )
    return tuple(assigned)


def _slot(team: QualifiedTeam) -> BracketSlot:
    return BracketSlot(
        team_id=team.team_id,
        payload=team.payload,
        source_slot=team.source_slot,
        group_name=team.group_name,
    )


def build_round_of_32_pairings(
    group_rankings: dict[str, tuple[QualifiedTeam, ...]],
) -> tuple[RoundOf32Pairing, ...]:
    """Build 16 fixed and explainable scenario R32 slots.

    This is a product-defined scenario rule, not an official FIFA bracket mapping:
    - A1-H1 face the eight best thirds, assigned without group rematches.
    - I1-L1 face L2-I2 in mirrored order.
    - The remaining A2-H2 runners-up are paired by adjacent groups.
    """
    winners, runners_up, best_thirds = select_knockout_qualifiers(group_rankings)
    third_winner_groups = tuple("ABCDEFGH")
    assigned_thirds = _assign_thirds_without_group_rematches(
        third_winner_groups, best_thirds
    )

    pairings = [
        RoundOf32Pairing(_slot(winners[group]), _slot(third))
        for group, third in zip(third_winner_groups, assigned_thirds, strict=True)
    ]
    pairings.extend([
        RoundOf32Pairing(_slot(winners["I"]), _slot(runners_up["L"])),
        RoundOf32Pairing(_slot(winners["J"]), _slot(runners_up["K"])),
        RoundOf32Pairing(_slot(winners["K"]), _slot(runners_up["J"])),
        RoundOf32Pairing(_slot(winners["L"]), _slot(runners_up["I"])),
        RoundOf32Pairing(_slot(runners_up["A"]), _slot(runners_up["B"])),
        RoundOf32Pairing(_slot(runners_up["C"]), _slot(runners_up["D"])),
        RoundOf32Pairing(_slot(runners_up["E"]), _slot(runners_up["F"])),
        RoundOf32Pairing(_slot(runners_up["G"]), _slot(runners_up["H"])),
    ])

    team_ids = [
        slot.team_id
        for pairing in pairings
        for slot in (pairing.home, pairing.away)
    ]
    if len(pairings) != 16 or len(team_ids) != 32 or len(set(team_ids)) != 32:
        raise TournamentRulesError("Round of 32 must contain 16 matches and 32 teams")
    return tuple(pairings)
