import json

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
            "group_name": row["group_name"],
            "pot": row["pot"],
        }
        for index, row in enumerate(rows)
    ]


def test_same_seed_produces_identical_probabilities_and_path():
    engine = MonteCarloEngine()
    first = engine.run(_teams(), iterations=100, seed=20260713, force_refresh=True)
    second = engine.run(_teams(), iterations=100, seed=20260713, force_refresh=True)

    assert first["seed"] == second["seed"] == 20260713
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["champion_probs"] == second["champion_probs"]
    assert first["top3"] == second["top3"]
    assert first["predicted_champion"] == second["predicted_champion"]
    assert first["stages"] == second["stages"]


def test_team_order_does_not_change_seeded_result():
    engine = MonteCarloEngine()
    teams = _teams()
    forward = engine.run(teams, iterations=100, seed=42, force_refresh=True)
    reverse = engine.run(
        list(reversed(teams)), iterations=100, seed=42, force_refresh=True
    )

    assert forward["input_fingerprint"] == reverse["input_fingerprint"]
    assert forward["champion_probs"] == reverse["champion_probs"]
    assert forward["stages"] == reverse["stages"]


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
