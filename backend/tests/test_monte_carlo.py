import json

import pytest

from app.services.monte_carlo import MonteCarloEngine
from app.services.simulation_models import (
    KeyedRandom,
    MAX_EXPECTED_GOALS,
    MIN_EXPECTED_GOALS,
    SimulationInput,
    derive_child_seed,
)
from app.services.tournament_data import DEFAULT_TOURNAMENT_DATA_PATH


def _teams():
    rows = json.loads(DEFAULT_TOURNAMENT_DATA_PATH.read_text(encoding="utf-8"))[
        "participants"
    ]
    return [
        {
            "id": index + 1,
            "name": row["name"],
            "name_cn": row["name_cn"],
            "fifa_code": row["fifa_code"],
            "elo_rating": 1500.0 + index,
            "tournament_group": row["group_name"],
            "tournament_pot": row["pot"],
        }
        for index, row in enumerate(rows)
    ]


def test_same_seed_produces_identical_probabilities_and_path():
    engine = MonteCarloEngine()
    first = engine.run(_teams(), iterations=100, seed=20260713, force_refresh=True)
    second = engine.run(_teams(), iterations=100, seed=20260713, force_refresh=True)

    assert first["seed"] == second["seed"] == 20260713
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["champion_probs_by_team_id"] == second["champion_probs_by_team_id"]
    assert first["advancement_probs"] == second["advancement_probs"]
    assert first["top3"] == second["top3"]
    assert first["representative_path"] == second["representative_path"]


def test_team_order_does_not_change_seeded_result():
    engine = MonteCarloEngine()
    teams = _teams()
    forward = engine.run(teams, iterations=100, seed=42, force_refresh=True)
    reverse = engine.run(
        list(reversed(teams)), iterations=100, seed=42, force_refresh=True
    )

    assert forward["input_fingerprint"] == reverse["input_fingerprint"]
    assert forward["champion_probs_by_team_id"] == reverse["champion_probs_by_team_id"]
    assert forward["representative_path"] == reverse["representative_path"]


def test_baseline_and_scenario_can_share_master_seed_without_mutating_teams():
    engine = MonteCarloEngine()
    teams = _teams()
    original = [dict(team) for team in teams]
    baseline = engine.run(teams, iterations=100, seed=88, force_refresh=True)
    scenario = engine.run(
        teams,
        iterations=100,
        seed=88,
        force_refresh=True,
        team_impacts={
            "ARG": {
                "attack_lambda_delta": -0.2,
                "concede_lambda_delta": 0.1,
            }
        },
        event_ids=[1],
    )

    assert baseline["seed"] == scenario["seed"] == 88
    assert baseline["input_fingerprint"] != scenario["input_fingerprint"]
    assert teams == original


def test_keyed_random_is_stable_and_clamps_poisson_rate():
    first = KeyedRandom(derive_child_seed(123, "iteration", 1))
    second = KeyedRandom(derive_child_seed(123, "iteration", 1))

    assert first.uniform("R32", 0, "home") == second.uniform("R32", 0, "home")
    assert first.poisson(-100, "low") == second.poisson(MIN_EXPECTED_GOALS, "low")
    assert first.poisson(100, "high") == second.poisson(MAX_EXPECTED_GOALS, "high")


def test_simulation_input_has_stable_fingerprint():
    teams = _teams()
    first = SimulationInput.from_raw(teams, iterations=100, seed=7)
    second = SimulationInput.from_raw(reversed(teams), iterations=100, seed=7)

    assert first.fingerprint() == second.fingerprint()


def test_advancement_probabilities_have_valid_totals_and_monotonicity():
    result = MonteCarloEngine().run(
        _teams(), iterations=200, seed=20260713, force_refresh=True
    )
    probabilities = result["advancement_probs"]

    expected_totals = {
        "R32": 32,
        "R16": 16,
        "QF": 8,
        "SF": 4,
        "FINAL": 2,
        "CHAMPION": 1,
    }
    for stage, expected_total in expected_totals.items():
        assert sum(team[stage] for team in probabilities.values()) == pytest.approx(
            expected_total
        )

    for team in probabilities.values():
        stages = [
            team["R32"],
            team["R16"],
            team["QF"],
            team["SF"],
            team["FINAL"],
            team["CHAMPION"],
        ]
        assert all(0.0 <= probability <= 1.0 for probability in stages)
        assert stages == sorted(stages, reverse=True)


def test_probability_leader_and_top3_use_id_based_champion_probabilities():
    result = MonteCarloEngine().run(
        _teams(), iterations=200, seed=99, force_refresh=True
    )
    leader = result["probability_leader"]
    leader_id = leader["team"]["id"]

    assert leader["probability"] == max(result["champion_probs_by_team_id"].values())
    assert result["champion_probs_by_team_id"][leader_id] == leader["probability"]
    assert result["top3"][0] == leader


def test_representative_path_replays_once_and_uses_probability_leader():
    class CountingEngine(MonteCarloEngine):
        def __init__(self):
            super().__init__()
            self.simulation_calls = 0

        def _sim_one(self, *args, **kwargs):
            self.simulation_calls += 1
            return super()._sim_one(*args, **kwargs)

    engine = CountingEngine()
    result = engine.run(_teams(), iterations=100, seed=77, force_refresh=True)
    representative = result["representative_path"]

    assert engine.simulation_calls == 101
    assert representative["path_type"] == ("top_champion_highest_likelihood_sample")
    assert (
        representative["champion"]["id"] == result["probability_leader"]["team"]["id"]
    )
    assert representative["stages"]["FINAL"]["matches"][0]["winner_team_id"] == representative["champion"]["id"]
    assert representative["log_likelihood"] < 0
