"""In-memory registry for stable baseline and event-scenario simulations."""

import copy
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass
from typing import Any, Iterable

from app.services.simulation_models import MODEL_VERSION


@dataclass(frozen=True, slots=True)
class CachedSimulation:
    simulation_id: str
    baseline_simulation_id: str
    context_key: str
    scenario_type: str
    seed: int
    event_ids: tuple[int, ...]
    event_content_fingerprint: str
    response: dict[str, Any]


class SimulationCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_id: dict[str, CachedSimulation] = {}
        self._current_baseline: dict[str, str] = {}
        self._baseline_by_seed: dict[tuple[str, int], str] = {}
        self._scenario_by_key: dict[tuple[str, str, str], str] = {}

    @staticmethod
    def new_seed() -> int:
        return secrets.randbelow(2**31 - 2) + 1

    def get_baseline(
        self, context_key: str, seed: int | None = None
    ) -> CachedSimulation | None:
        with self._lock:
            if seed is None:
                simulation_id = self._current_baseline.get(context_key)
            else:
                simulation_id = self._baseline_by_seed.get((context_key, seed))
            return self._copy_record(simulation_id)

    def get_by_id(self, simulation_id: str) -> CachedSimulation | None:
        with self._lock:
            return self._copy_record(simulation_id)

    def get_scenario(
        self,
        context_key: str,
        baseline_simulation_id: str,
        event_content_fingerprint: str,
    ) -> CachedSimulation | None:
        key = (context_key, baseline_simulation_id, event_content_fingerprint)
        with self._lock:
            return self._copy_record(self._scenario_by_key.get(key))

    def store_baseline(
        self, context_key: str, response: dict[str, Any]
    ) -> CachedSimulation:
        record = CachedSimulation(
            simulation_id=response["simulation_id"],
            baseline_simulation_id=response["simulation_id"],
            context_key=context_key,
            scenario_type="BASELINE",
            seed=response["model"]["seed"],
            event_ids=(),
            event_content_fingerprint=response["scenario"]["event_content_fingerprint"],
            response=copy.deepcopy(response),
        )
        with self._lock:
            self._by_id[record.simulation_id] = record
            self._current_baseline[context_key] = record.simulation_id
            self._baseline_by_seed[(context_key, record.seed)] = record.simulation_id
        return record

    def store_scenario(
        self, context_key: str, response: dict[str, Any]
    ) -> CachedSimulation:
        record = CachedSimulation(
            simulation_id=response["simulation_id"],
            baseline_simulation_id=response["baseline_simulation_id"],
            context_key=context_key,
            scenario_type="EVENT",
            seed=response["model"]["seed"],
            event_ids=tuple(response["scenario"]["requested_event_ids"]),
            event_content_fingerprint=response["scenario"]["event_content_fingerprint"],
            response=copy.deepcopy(response),
        )
        key = (
            context_key,
            record.baseline_simulation_id,
            record.event_content_fingerprint,
        )
        with self._lock:
            old_id = self._scenario_by_key.get(key)
            if old_id:
                self._by_id.pop(old_id, None)
            self._by_id[record.simulation_id] = record
            self._scenario_by_key[key] = record.simulation_id
        return record

    def invalidate_scenarios(self, event_ids: Iterable[int] | None = None) -> None:
        selected = set(event_ids or [])
        with self._lock:
            remove_ids = [
                simulation_id
                for simulation_id, record in self._by_id.items()
                if record.scenario_type == "EVENT"
                and (not selected or selected.intersection(record.event_ids))
            ]
            for simulation_id in remove_ids:
                self._by_id.pop(simulation_id, None)
            self._scenario_by_key = {
                key: simulation_id
                for key, simulation_id in self._scenario_by_key.items()
                if simulation_id not in remove_ids
            }

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._current_baseline.clear()
            self._baseline_by_seed.clear()
            self._scenario_by_key.clear()

    def _copy_record(self, simulation_id: str | None) -> CachedSimulation | None:
        if simulation_id is None:
            return None
        record = self._by_id.get(simulation_id)
        if record is None:
            return None
        return CachedSimulation(
            simulation_id=record.simulation_id,
            baseline_simulation_id=record.baseline_simulation_id,
            context_key=record.context_key,
            scenario_type=record.scenario_type,
            seed=record.seed,
            event_ids=record.event_ids,
            event_content_fingerprint=record.event_content_fingerprint,
            response=copy.deepcopy(record.response),
        )


def build_simulation_context_key(
    *,
    tournament_id: int,
    tournament_code: str,
    data_version: str,
    rules_version: str,
    iterations: int,
    teams: list[dict[str, Any]],
) -> str:
    payload = {
        "tournament_id": tournament_id,
        "tournament_code": tournament_code,
        "data_version": data_version,
        "rules_version": rules_version,
        "model_version": MODEL_VERSION,
        "iterations": iterations,
        "teams": [
            {
                "id": team["id"],
                "code": team["fifa_code"],
                "elo": team["elo_rating"],
                "group": team["group_name"],
                "pot": team["pot"],
            }
            for team in sorted(teams, key=lambda item: item["id"])
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_cache = SimulationCache()


def get_simulation_cache() -> SimulationCache:
    return _cache
