"""Monte Carlo Tournament Simulator — ELO + Poisson."""

import time
import threading
import uuid
from collections import defaultdict
from typing import Optional

import numpy as np

ATTACK_FACTOR = 0.8
DEFENSE_FACTOR = 0.6
ELO_DIVISOR = 1000.0
GROUP_NAMES = "ABCDEFGHIJKL"


def _eg(attack_elo: float, defense_elo: float) -> float:
    atk = (attack_elo / ELO_DIVISOR) * ATTACK_FACTOR
    df = (defense_elo / ELO_DIVISOR) * DEFENSE_FACTOR
    if df < 0.1:
        df = 0.1
    x = atk / df
    return x if x > 0.1 else 0.1


class MonteCarloEngine:

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._rng = np.random.default_rng()

    def run(self, teams: list[dict], iterations: int = 1000,
            force_refresh: bool = False,
            team_impacts: Optional[dict] = None,
            event_ids: Optional[list[int]] = None) -> dict:
        cache_key = ",".join(sorted(t["name"] for t in teams))
        cache_key = f"{cache_key}:{iterations}"
        if team_impacts:
            impact_str = ",".join(f"{k}:{v}" for k, v in sorted(
                (code, f"{imp.get('attack',0):.2f},{imp.get('defense',0):.2f}")
                for code, imp in team_impacts.items()
            ))
            cache_key = f"{cache_key}:imp({impact_str})"
        cache_key = f"{cache_key}:events({','.join(map(str, sorted(event_ids or [])))})"

        with self._lock:
            if not force_refresh and cache_key in self._cache:
                ts, result = self._cache[cache_key]
                if time.time() - ts < 300:
                    return result

        tid2info: dict[int, tuple] = {}
        for t in teams:
            tid2info[t["id"]] = (
                t["name"], t["name_cn"],
                t["elo_rating"] or 1500.0, t["group_name"],
                t.get("fifa_code", "")
            )
        team_ids = list(tid2info.keys())

        seed = int(self._rng.integers(1, 2**31 - 1))
        probability_rng = np.random.default_rng(seed)
        path_rng = np.random.default_rng(seed ^ 0x5F3759DF)
        champion_counts: dict[str, int] = defaultdict(int)

        for _ in range(iterations):
            champ = self._sim_one(team_ids, tid2info, probability_rng, team_impacts)
            champion_counts[champ] += 1

        total = max(sum(champion_counts.values()), 1)
        probs = {name: count / total for name, count in champion_counts.items()}
        top3 = sorted(probs.items(), key=lambda x: -x[1])[:3]

        path_champion, stages = self._sim_one(
            team_ids, tid2info, path_rng, team_impacts,
            capture_path=True,
            team_by_id={team["id"]: team for team in teams},
        )

        result = {
            "simulation_id": uuid.uuid4().hex,
            "seed": seed,
            "event_ids": sorted(event_ids or []),
            "champion_probs": probs,
            "top3": top3,
            "iterations": iterations,
            "predicted_champion": path_champion,
            "stages": stages,
        }

        with self._lock:
            self._cache[cache_key] = (time.time(), result)

        return result

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _sim_one(
        self,
        team_ids,
        tid2info,
        rng,
        team_impacts=None,
        capture_path: bool = False,
        team_by_id: Optional[dict[int, dict]] = None,
    ):
        # Group stage setup: list of [tid, name, cn, elo, pts, gf, ga, gd]
        groups = {g: [] for g in GROUP_NAMES}
        for tid in team_ids:
            name, cn, elo, grp, _code = tid2info[tid]
            groups[grp].append([tid, name, cn, elo, 0, 0, 0, 0])

        for grp_records in groups.values():
            for i in range(4):
                ri = grp_records[i]
                for j in range(i + 1, 4):
                    rj = grp_records[j]
                    if rng.random() < 0.5:
                        a, b = ri, rj
                    else:
                        a, b = rj, ri
                    lambda_home = _eg(a[3], b[3])
                    lambda_away = _eg(b[3], a[3])
                    if team_impacts:
                        home_code = tid2info[a[0]][4]
                        away_code = tid2info[b[0]][4]
                        home_imp = team_impacts.get(home_code, {})
                        away_imp = team_impacts.get(away_code, {})
                        lambda_home *= (1.0 + home_imp.get("attack", 0.0)) * (1.0 + away_imp.get("defense", 0.0))
                        lambda_away *= (1.0 + away_imp.get("attack", 0.0)) * (1.0 + home_imp.get("defense", 0.0))
                        lambda_home = max(lambda_home, 0.05)
                        lambda_away = max(lambda_away, 0.05)
                    hg = int(rng.poisson(lambda_home))
                    ag = int(rng.poisson(lambda_away))
                    if hg > ag:
                        a[4] += 3
                    elif ag > hg:
                        b[4] += 3
                    else:
                        a[4] += 1
                        b[4] += 1
                    a[5] += hg; a[6] += ag; a[7] = a[5] - a[6]
                    b[5] += ag; b[6] += hg; b[7] = b[5] - b[6]

        sk = lambda r: (r[4], r[7], r[5], r[3])  # pts, gd, gf, elo

        group_winners, group_runners_up, group_thirds = [], [], []
        for gn in GROUP_NAMES:
            recs = sorted(groups[gn], key=sk, reverse=True)
            group_winners.append(recs[0])
            group_runners_up.append(recs[1])
            group_thirds.append(recs[2])

        best_thirds = sorted(group_thirds, key=sk, reverse=True)[:8]

        current = group_winners + group_runners_up + best_thirds
        rng.shuffle(current)

        stages: dict[str, dict] = {}
        stage_names = ["R32", "R16", "QF", "SF"]
        stage_labels = {
            "R32": "32 强", "R16": "16 强", "QF": "1/4 决赛",
            "SF": "半决赛", "FINAL": "决赛",
        }

        for stage_name in stage_names:
            winners = []
            stage_matches = []
            for k in range(0, len(current), 2):
                a, b = current[k], current[k + 1]
                if rng.random() < 0.5:
                    a, b = b, a
                lambda_home = _eg(a[3], b[3])
                lambda_away = _eg(b[3], a[3])
                if team_impacts:
                    home_code = tid2info[a[0]][4]
                    away_code = tid2info[b[0]][4]
                    home_imp = team_impacts.get(home_code, {})
                    away_imp = team_impacts.get(away_code, {})
                    lambda_home *= (1.0 + home_imp.get("attack", 0.0)) * (1.0 + away_imp.get("defense", 0.0))
                    lambda_away *= (1.0 + away_imp.get("attack", 0.0)) * (1.0 + home_imp.get("defense", 0.0))
                    lambda_home = max(lambda_home, 0.05)
                    lambda_away = max(lambda_away, 0.05)
                hg = int(rng.poisson(lambda_home))
                ag = int(rng.poisson(lambda_away))
                if hg > ag:
                    winner = a
                elif ag > hg:
                    winner = b
                else:
                    winner = a if a[3] >= b[3] else b
                winners.append(winner)
                if capture_path and team_by_id is not None:
                    stage_matches.append(self._path_match(
                        stage_name, len(stage_matches), a, b, hg, ag,
                        winner, team_by_id, stage_labels[stage_name],
                    ))
            current = winners
            if capture_path:
                stages[stage_name] = {
                    "label": stage_labels[stage_name],
                    "matches": stage_matches,
                }

        a, b = current[0], current[1]
        if rng.random() < 0.5:
            a, b = b, a
        lambda_home = _eg(a[3], b[3])
        lambda_away = _eg(b[3], a[3])
        if team_impacts:
            home_code = tid2info[a[0]][4]
            away_code = tid2info[b[0]][4]
            home_imp = team_impacts.get(home_code, {})
            away_imp = team_impacts.get(away_code, {})
            lambda_home *= (1.0 + home_imp.get("attack", 0.0)) * (1.0 + away_imp.get("defense", 0.0))
            lambda_away *= (1.0 + away_imp.get("attack", 0.0)) * (1.0 + home_imp.get("defense", 0.0))
            lambda_home = max(lambda_home, 0.05)
            lambda_away = max(lambda_away, 0.05)
        hg = int(rng.poisson(lambda_home))
        ag = int(rng.poisson(lambda_away))
        if hg > ag:
            winner = a
        elif ag > hg:
            winner = b
        else:
            winner = a if a[3] >= b[3] else b

        if capture_path and team_by_id is not None:
            stages["FINAL"] = {
                "label": stage_labels["FINAL"],
                "matches": [self._path_match(
                    "FINAL", 0, a, b, hg, ag, winner,
                    team_by_id, stage_labels["FINAL"],
                )],
            }
            return winner[1], stages
        return winner[1]

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
    ) -> dict:
        stage_offsets = {"R32": 100, "R16": 200, "QF": 300, "SF": 400, "FINAL": 500}
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
            "is_simulated": True,
            "match_order": match_index,
        }


_engine: Optional[MonteCarloEngine] = None


def get_engine() -> MonteCarloEngine:
    global _engine
    if _engine is None:
        _engine = MonteCarloEngine()
    return _engine
