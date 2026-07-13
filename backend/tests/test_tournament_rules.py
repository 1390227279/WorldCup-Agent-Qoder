import pytest

from app.services.tournament_rules import (
    GROUP_NAMES,
    GroupStanding,
    TournamentRulesError,
    build_round_of_32_pairings,
    rank_group,
    select_knockout_qualifiers,
)


def _group_rankings():
    rankings = {}
    team_id = 1
    for group_index, group_name in enumerate(GROUP_NAMES):
        standings = []
        for position in range(4):
            points = (30, 25, 20 - group_index, 0)[position]
            payload = [team_id, f"Team {team_id}", f"球队{team_id}", 1800 - team_id]
            standings.append(GroupStanding(
                team_id=team_id,
                group_name=group_name,
                points=points,
                goal_difference=8 - position,
                goals_for=10 - position,
                elo_rating=1800 - team_id,
                payload=payload,
            ))
            team_id += 1
        rankings[group_name] = rank_group(standings)
    return rankings


def test_rank_group_uses_deterministic_tiebreakers():
    standings = [
        GroupStanding(4, "A", 5, 2, 4, 1600, [4]),
        GroupStanding(3, "A", 5, 2, 4, 1700, [3]),
        GroupStanding(2, "A", 5, 3, 3, 1500, [2]),
        GroupStanding(1, "A", 6, 0, 2, 1400, [1]),
    ]

    ranking = rank_group(standings)

    assert [team.team_id for team in ranking] == [1, 2, 3, 4]
    assert [team.source_slot for team in ranking] == [
        "GROUP_A_1", "GROUP_A_2", "GROUP_A_3", "GROUP_A_4"
    ]


def test_selects_12_winners_12_runners_and_8_best_thirds():
    winners, runners, thirds = select_knockout_qualifiers(_group_rankings())

    assert set(winners) == set(GROUP_NAMES)
    assert set(runners) == set(GROUP_NAMES)
    assert len(thirds) == 8
    assert [team.group_name for team in thirds] == list("ABCDEFGH")


def test_builds_fixed_legal_round_of_32_without_group_rematches():
    pairings = build_round_of_32_pairings(_group_rankings())

    assert len(pairings) == 16
    team_ids = [
        slot.payload[0]
        for pairing in pairings
        for slot in (pairing.home, pairing.away)
    ]
    assert len(team_ids) == len(set(team_ids)) == 32

    for pairing in pairings[:8]:
        assert pairing.home.source_slot.endswith("_1")
        assert pairing.away.source_slot.endswith("_3")
        assert pairing.home.group_name != pairing.away.group_name

    assert pairings[8].home.source_slot == "GROUP_I_1"
    assert pairings[8].away.source_slot == "GROUP_L_2"
    assert pairings[12].home.source_slot == "GROUP_A_2"
    assert pairings[12].away.source_slot == "GROUP_B_2"


def test_rejects_incomplete_group_rankings():
    rankings = _group_rankings()
    del rankings["L"]

    with pytest.raises(TournamentRulesError, match="every group A-L"):
        build_round_of_32_pairings(rankings)
