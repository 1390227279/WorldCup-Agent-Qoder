"""Monte Carlo Tournament Simulator — deterministic ELO + Poisson."""

import math
import threading
import time
from collections import defaultdict
from typing import Optional

import numpy as np

from app.services.scenario_resolver import (
    ATTACK_LAMBDA_DELTA,
    CONCEDE_LAMBDA_DELTA,
)
from app.services.representative_path import (
    REPRESENTATIVE_PATH_TYPE,
    RepresentativePathSelector,
)
from app.services.simulation_models import (
    ADVANCEMENT_STAGES,
    KeyedRandom,
    MODEL_VERSION,
    SimulationInput,
    TournamentOutcome,
    derive_child_seed,
    poisson_log_probability,
)
from app.services.tournament_rules import (
    BracketSlot,
    GROUP_NAMES,
    GroupStanding,
    build_round_of_32_pairings,
    rank_group,
    select_knockout_qualifiers,
)


ATTACK_FACTOR = 0.8
DEFENSE_FACTOR = 0.6
ELO_DIVISOR = 1000.0


def _eg(attack_elo: float, defense_elo: float) -> float:
    atk = (attack_elo / ELO_DIVISOR) * ATTACK_FACTOR
    df = max((defense_elo / ELO_DIVISOR) * DEFENSE_FACTOR, 0.1)
    return max(atk / df, 0.1)


def calculate_match_lambdas(
    home_elo: float,
    away_elo: float,
    home_code: str,
    away_code: str,
    team_impacts: Optional[dict] = None,
) -> tuple[float, float]:
    """使用与赛事模拟完全相同的公式计算单场进球期望。"""
    home_lambda = _eg(home_elo, away_elo)
    away_lambda = _eg(away_elo, home_elo)
    if team_impacts:
        home_impact = team_impacts.get(home_code, {})
        away_impact = team_impacts.get(away_code, {})
        home_lambda *= (1.0 + home_impact.get(ATTACK_LAMBDA_DELTA, 0.0)) * (
            1.0 + away_impact.get(CONCEDE_LAMBDA_DELTA, 0.0)
        )
        away_lambda *= (1.0 + away_impact.get(ATTACK_LAMBDA_DELTA, 0.0)) * (
            1.0 + home_impact.get(CONCEDE_LAMBDA_DELTA, 0.0)
        )
    return max(home_lambda, 0.1), max(away_lambda, 0.1)


def _knockout_winner(
    home,
    away,
    home_score: int,
    away_score: int,
    random_source: KeyedRandom,
    stage: str,
    match_index: int,
):
    if home_score > away_score:
        return home, "REGULAR_TIME", 0.0
    if away_score > home_score:
        return away, "REGULAR_TIME", 0.0

    home_penalty_probability = 1.0 / (1.0 + 10.0 ** ((away[3] - home[3]) / 400.0))
    if (
        random_source.uniform(stage, match_index, "penalties")
        < home_penalty_probability
    ):
        return home, "PENALTIES", math.log(home_penalty_probability)
    return away, "PENALTIES", math.log(1.0 - home_penalty_probability)


class MonteCarloEngine:

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._rng = np.random.default_rng()

    def run(
        self,
        teams: list[dict],
        iterations: int = 1000,
        force_refresh: bool = False,
        team_impacts: Optional[dict] = None,
        event_ids: Optional[list[int]] = None,
        seed: int | None = None,
    ) -> dict:
        cache_seed = seed if seed is not None else "auto"
        cache_key = self._pre_seed_cache_key(
            teams, iterations, team_impacts, event_ids, cache_seed
        )
        with self._lock:
            if not force_refresh and cache_key in self._cache:
                timestamp, result = self._cache[cache_key]
                if time.time() - timestamp < 300:
                    return result

        master_seed = seed or int(self._rng.integers(1, 2**31 - 1))
        simulation_input = SimulationInput.from_raw(
            teams,
            iterations=iterations,
            seed=master_seed,
            team_impacts=team_impacts,
            event_ids=event_ids,
        )
        team_ids = [team.id for team in simulation_input.teams]
        team_info = {
            team.id: (
                team.name,
                team.name_cn,
                team.elo_rating,
                team.tournament_group,
                team.fifa_code,
            )
            for team in simulation_input.teams
        }
        public_teams = {
            team.id: team.to_public_dict() for team in simulation_input.teams
        }
        impacts = simulation_input.impact_by_code

        advancement_counts: dict[str, dict[int, int]] = {
            stage: defaultdict(int) for stage in ADVANCEMENT_STAGES
        }
        path_selector = RepresentativePathSelector()
        for iteration in range(simulation_input.iterations):
            iteration_seed = derive_child_seed(master_seed, "iteration", iteration)
            outcome = self._sim_one(
                team_ids,
                team_info,
                KeyedRandom(iteration_seed),
                impacts,
            )
            for stage, reached_team_ids in outcome.reached_team_ids.items():
                for team_id in reached_team_ids:
                    advancement_counts[stage][team_id] += 1
            path_selector.observe(
                outcome,
                iteration_index=iteration,
                iteration_seed=iteration_seed,
            )

        total = max(simulation_input.iterations, 1)
        advancement_probs = {
            team.id: {
                "team_id": team.id,
                "team": public_teams[team.id],
                **{
                    stage: advancement_counts[stage][team.id] / total
                    for stage in ADVANCEMENT_STAGES
                },
            }
            for team in simulation_input.teams
        }
        champion_probs_by_team_id = {
            team.id: advancement_probs[team.id]["CHAMPION"]
            for team in simulation_input.teams
        }
        ranked_team_ids = sorted(
            champion_probs_by_team_id,
            key=lambda team_id: (-champion_probs_by_team_id[team_id], team_id),
        )
        probability_leader_id = ranked_team_ids[0]
        probability_leader = {
            "team": public_teams[probability_leader_id],
            "probability": champion_probs_by_team_id[probability_leader_id],
        }
        top3 = [
            {
                "team": public_teams[team_id],
                "probability": champion_probs_by_team_id[team_id],
            }
            for team_id in ranked_team_ids[:3]
        ]

        path_candidate = path_selector.for_champion(probability_leader_id)
        path_outcome = self._sim_one(
            team_ids,
            team_info,
            KeyedRandom(path_candidate.iteration_seed),
            impacts,
            capture_path=True,
            team_by_id=public_teams,
        )
        if path_outcome.champion_team_id != probability_leader_id:
            raise RuntimeError(
                "Representative path replay produced a different champion"
            )

        representative_path = {
            "path_type": REPRESENTATIVE_PATH_TYPE,
            "champion": public_teams[path_outcome.champion_team_id],
            "iteration_index": path_candidate.iteration_index,
            "iteration_seed": path_candidate.iteration_seed,
            "log_likelihood": path_outcome.log_likelihood,
            "group_stage": path_outcome.group_stage,
            "stages": path_outcome.stages,
        }

        result = {
            "seed": master_seed,
            "advancement_probs": advancement_probs,
            "champion_probs_by_team_id": champion_probs_by_team_id,
            "probability_leader": probability_leader,
            "top3": top3,
            "representative_path": representative_path,
            "iterations": simulation_input.iterations,
            "model_version": MODEL_VERSION,
            "input_fingerprint": simulation_input.fingerprint(),
        }
        with self._lock:
            self._cache[cache_key] = (time.time(), result)
        return result

    @staticmethod
    def _pre_seed_cache_key(
        teams: list[dict],
        iterations: int,
        team_impacts: dict | None,
        event_ids: list[int] | None,
        seed: int | str,
    ) -> str:
        team_part = ",".join(
            f"{team['id']}:{team.get('elo_rating') or 1500}:"
            f"{team.get('tournament_group')}:{team.get('tournament_pot')}"
            for team in sorted(teams, key=lambda item: item["id"])
        )
        impact_part = ",".join(
            f"{code}:{values.get(ATTACK_LAMBDA_DELTA, 0.0):.4f}:"
            f"{values.get(CONCEDE_LAMBDA_DELTA, 0.0):.4f}"
            for code, values in sorted((team_impacts or {}).items())
        )
        event_part = ",".join(map(str, sorted(event_ids or [])))
        return (
            f"{MODEL_VERSION}|{seed}|{iterations}|{team_part}|"
            f"{impact_part}|{event_part}"
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _sim_one(
        self,
        team_ids,
        team_info,
        random_source: KeyedRandom,
        team_impacts=None,
        capture_path: bool = False,
        team_by_id: Optional[dict[int, dict]] = None,
    ):
        # Group record: [team_id, name, name_cn, elo, points, gf, ga, gd]
        trace_log_likelihood = 0.0
        groups = {group: [] for group in GROUP_NAMES}
        group_matches: dict[str, list[dict]] = {group: [] for group in GROUP_NAMES}
        for team_id in team_ids:
            name, name_cn, elo, group_name, _code = team_info[team_id]
            groups[group_name].append([team_id, name, name_cn, elo, 0, 0, 0, 0])

        for group_name, group_records in groups.items():
            group_index = GROUP_NAMES.index(group_name)
            for first_index in range(4):
                first = group_records[first_index]
                for second_index in range(first_index + 1, 4):
                    second = group_records[second_index]
                    if (
                        random_source.uniform(
                            "GROUP", group_name, first_index, second_index, "home-order"
                        )
                        < 0.5
                    ):
                        home, away = first, second
                    else:
                        home, away = second, first
                    home_lambda, away_lambda = self._match_lambdas(
                        home, away, team_info, team_impacts
                    )
                    home_goals = random_source.poisson(
                        home_lambda,
                        "GROUP",
                        group_name,
                        first_index,
                        second_index,
                        "home-goals",
                    )
                    away_goals = random_source.poisson(
                        away_lambda,
                        "GROUP",
                        group_name,
                        first_index,
                        second_index,
                        "away-goals",
                    )
                    trace_log_likelihood += poisson_log_probability(
                        home_goals, home_lambda
                    ) + poisson_log_probability(away_goals, away_lambda)
                    if home_goals > away_goals:
                        home[4] += 3
                    elif away_goals > home_goals:
                        away[4] += 3
                    else:
                        home[4] += 1
                        away[4] += 1
                    home[5] += home_goals
                    home[6] += away_goals
                    home[7] = home[5] - home[6]
                    away[5] += away_goals
                    away[6] += home_goals
                    away[7] = away[5] - away[6]
                    if capture_path and team_by_id is not None:
                        group_matches[group_name].append({
                            "id": -(10_000 + group_index * 10 + len(group_matches[group_name]) + 1),
                            "match_key": f"GROUP-{group_name}-{len(group_matches[group_name]) + 1}",
                            "stage": "GROUP",
                            "round_name": f"{group_name} 组",
                            "group_name": group_name,
                            "home_team": team_by_id[home[0]],
                            "away_team": team_by_id[away[0]],
                            "home_score": home_goals,
                            "away_score": away_goals,
                            "winner_team_id": (
                                home[0] if home_goals > away_goals
                                else away[0] if away_goals > home_goals
                                else None
                            ),
                            "winner": (
                                home[1] if home_goals > away_goals
                                else away[1] if away_goals > home_goals
                                else "平局"
                            ),
                            "is_simulated": True,
                            "match_order": len(group_matches[group_name]),
                        })

        group_rankings = {}
        for group_name in GROUP_NAMES:
            group_rankings[group_name] = rank_group(
                GroupStanding(
                    team_id=record[0],
                    group_name=group_name,
                    points=record[4],
                    goal_difference=record[7],
                    goals_for=record[5],
                    elo_rating=record[3],
                    payload=record,
                )
                for record in groups[group_name]
            )

        winners, runners_up, best_thirds = select_knockout_qualifiers(
            group_rankings
        )
        round_of_32 = build_round_of_32_pairings(group_rankings)
        current = [
            slot for pairing in round_of_32 for slot in (pairing.home, pairing.away)
        ]
        reached_team_ids = {"R32": tuple(slot.team_id for slot in current)}
        group_stage = None
        if capture_path and team_by_id is not None:
            qualification_by_team_id = {
                **{team.team_id: "GROUP_WINNER" for team in winners.values()},
                **{team.team_id: "RUNNER_UP" for team in runners_up.values()},
                **{team.team_id: "BEST_THIRD" for team in best_thirds},
            }
            group_stage = {
                group_name: {
                    "label": f"{group_name} 组",
                    "matches": group_matches[group_name],
                    "standings": [
                        self._group_standing_row(
                            qualified,
                            position,
                            team_by_id,
                            group_matches[group_name],
                            qualification_by_team_id.get(qualified.team_id),
                        )
                        for position, qualified in enumerate(
                            group_rankings[group_name], start=1
                        )
                    ],
                }
                for group_name in GROUP_NAMES
            }
        stages: dict[str, dict] = {}
        stage_names = ["R32", "R16", "QF", "SF"]
        next_stage = {"R32": "R16", "R16": "QF", "QF": "SF", "SF": "FINAL"}
        stage_labels = {
            "R32": "32 强",
            "R16": "16 强",
            "QF": "1/4 决赛",
            "SF": "半决赛",
            "FINAL": "决赛",
        }

        for stage_name in stage_names:
            winners = []
            stage_matches = []
            for match_index in range(len(current) // 2):
                home_slot = current[match_index * 2]
                away_slot = current[match_index * 2 + 1]
                if random_source.uniform(stage_name, match_index, "home-order") >= 0.5:
                    home_slot, away_slot = away_slot, home_slot
                home, away = home_slot.payload, away_slot.payload
                home_lambda, away_lambda = self._match_lambdas(
                    home, away, team_info, team_impacts
                )
                home_goals = random_source.poisson(
                    home_lambda, stage_name, match_index, "home-goals"
                )
                away_goals = random_source.poisson(
                    away_lambda, stage_name, match_index, "away-goals"
                )
                winner, decided_by, decision_log_probability = _knockout_winner(
                    home,
                    away,
                    home_goals,
                    away_goals,
                    random_source,
                    stage_name,
                    match_index,
                )
                trace_log_likelihood += (
                    poisson_log_probability(home_goals, home_lambda)
                    + poisson_log_probability(away_goals, away_lambda)
                    + decision_log_probability
                )
                match_key = f"{stage_name}-{match_index + 1}"
                winners.append(
                    BracketSlot(
                        team_id=winner[0],
                        payload=winner,
                        source_slot=match_key,
                    )
                )
                if capture_path and team_by_id is not None:
                    stage_matches.append(
                        self._path_match(
                            stage_name,
                            match_index,
                            home,
                            away,
                            home_goals,
                            away_goals,
                            winner,
                            team_by_id,
                            stage_labels[stage_name],
                            [home_slot.source_slot, away_slot.source_slot],
                            decided_by,
                        )
                    )
            current = winners
            reached_team_ids[next_stage[stage_name]] = tuple(
                slot.team_id for slot in current
            )
            if capture_path:
                stages[stage_name] = {
                    "label": stage_labels[stage_name],
                    "matches": stage_matches,
                }

        home_slot, away_slot = current
        if random_source.uniform("FINAL", 0, "home-order") >= 0.5:
            home_slot, away_slot = away_slot, home_slot
        home, away = home_slot.payload, away_slot.payload
        home_lambda, away_lambda = self._match_lambdas(
            home, away, team_info, team_impacts
        )
        home_goals = random_source.poisson(home_lambda, "FINAL", 0, "home-goals")
        away_goals = random_source.poisson(away_lambda, "FINAL", 0, "away-goals")
        winner, decided_by, decision_log_probability = _knockout_winner(
            home,
            away,
            home_goals,
            away_goals,
            random_source,
            "FINAL",
            0,
        )
        trace_log_likelihood += (
            poisson_log_probability(home_goals, home_lambda)
            + poisson_log_probability(away_goals, away_lambda)
            + decision_log_probability
        )
        reached_team_ids["CHAMPION"] = (winner[0],)
        if capture_path and team_by_id is not None:
            stages["FINAL"] = {
                "label": stage_labels["FINAL"],
                "matches": [
                    self._path_match(
                        "FINAL",
                        0,
                        home,
                        away,
                        home_goals,
                        away_goals,
                        winner,
                        team_by_id,
                        stage_labels["FINAL"],
                        [home_slot.source_slot, away_slot.source_slot],
                        decided_by,
                    )
                ],
            }
            return TournamentOutcome(
                champion_team_id=winner[0],
                champion_name=winner[1],
                reached_team_ids=reached_team_ids,
                log_likelihood=trace_log_likelihood,
                stages=stages,
                group_stage=group_stage,
            )
        return TournamentOutcome(
            champion_team_id=winner[0],
            champion_name=winner[1],
            reached_team_ids=reached_team_ids,
            log_likelihood=trace_log_likelihood,
        )

    @staticmethod
    def _group_standing_row(
        qualified,
        position: int,
        team_by_id: dict[int, dict],
        matches: list[dict],
        qualification_type: str | None,
    ) -> dict:
        wins = draws = losses = 0
        for match in matches:
            if qualified.team_id not in {
                match["home_team"]["id"], match["away_team"]["id"]
            }:
                continue
            if match["winner_team_id"] is None:
                draws += 1
            elif match["winner_team_id"] == qualified.team_id:
                wins += 1
            else:
                losses += 1
        standing = qualified.standing
        goals_against = standing.goals_for - standing.goal_difference
        return {
            "position": position,
            "team_id": qualified.team_id,
            "team": team_by_id[qualified.team_id],
            "played": wins + draws + losses,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_for": standing.goals_for,
            "goals_against": goals_against,
            "goal_difference": standing.goal_difference,
            "points": standing.points,
            "qualified": qualification_type is not None,
            "qualification_type": qualification_type,
        }

    @staticmethod
    def _match_lambdas(home, away, team_info, team_impacts):
        return calculate_match_lambdas(
            home[3],
            away[3],
            team_info[home[0]][4],
            team_info[away[0]][4],
            team_impacts,
        )

    @staticmethod
    def _path_match(
        stage: str,
        match_index: int,
        home,
        away,
        home_score: int,
        away_score: int,
        winner,
        team_by_id: dict[int, dict],
        label: str,
        source_slots: list[str],
        decided_by: str,
    ) -> dict:
        stage_offsets = {
            "R32": 100,
            "R16": 200,
            "QF": 300,
            "SF": 400,
            "FINAL": 500,
        }
        return {
            "id": -(stage_offsets[stage] + match_index + 1),
            "match_key": f"{stage}-{match_index + 1}",
            "stage": stage,
            "round_name": label,
            "home_team": team_by_id[home[0]],
            "away_team": team_by_id[away[0]],
            "home_score": home_score,
            "away_score": away_score,
            "winner_team_id": winner[0],
            "winner": winner[1],
            "source_slots": source_slots,
            "decided_by": decided_by,
            "is_simulated": True,
            "match_order": match_index,
        }


_engine: Optional[MonteCarloEngine] = None


def get_engine() -> MonteCarloEngine:
    global _engine
    if _engine is None:
        _engine = MonteCarloEngine()
    return _engine
