from app.services.simulation_cache import (
    SimulationCache,
    build_simulation_context_key,
)


def _response(simulation_id: str, scenario_type: str, event_ids=None):
    baseline_id = simulation_id if scenario_type == "BASELINE" else "baseline-1"
    return {
        "simulation_id": simulation_id,
        "baseline_simulation_id": baseline_id,
        "model": {"seed": 123},
        "scenario": {
            "requested_event_ids": event_ids or [],
            "event_content_fingerprint": f"fingerprint-{simulation_id}",
        },
    }


def test_cache_keeps_current_and_seeded_baseline():
    cache = SimulationCache()
    response = _response("baseline-1", "BASELINE")

    cache.store_baseline("context", response)

    assert cache.get_baseline("context").simulation_id == "baseline-1"
    assert cache.get_baseline("context", 123).simulation_id == "baseline-1"
    assert cache.get_by_id("baseline-1").scenario_type == "BASELINE"


def test_targeted_event_invalidation_does_not_remove_baseline():
    cache = SimulationCache()
    cache.store_baseline("context", _response("baseline-1", "BASELINE"))
    first = _response("scenario-1", "EVENT", [1])
    first["scenario"]["event_content_fingerprint"] = "event-1"
    second = _response("scenario-2", "EVENT", [2])
    second["scenario"]["event_content_fingerprint"] = "event-2"
    cache.store_scenario("context", first)
    cache.store_scenario("context", second)

    cache.invalidate_scenarios({1})

    assert cache.get_by_id("baseline-1") is not None
    assert cache.get_by_id("scenario-1") is None
    assert cache.get_by_id("scenario-2") is not None


def test_context_key_is_order_independent_and_versioned():
    teams = [
        {"id": 2, "fifa_code": "BRA", "elo_rating": 2000, "group_name": "B", "pot": 1},
        {"id": 1, "fifa_code": "ARG", "elo_rating": 2100, "group_name": "A", "pot": 1},
    ]
    arguments = {
        "tournament_id": 1,
        "tournament_code": "world-cup-2026",
        "data_version": "v1",
        "rules_version": "rules-v1",
        "iterations": 1000,
    }

    first = build_simulation_context_key(teams=teams, **arguments)
    second = build_simulation_context_key(teams=list(reversed(teams)), **arguments)
    changed = build_simulation_context_key(
        teams=teams, **{**arguments, "data_version": "v2"}
    )

    assert first == second
    assert first != changed
