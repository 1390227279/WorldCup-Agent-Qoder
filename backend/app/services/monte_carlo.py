"""Monte Carlo Tournament Simulator — ELO + Poisson."""

import time
import threading
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
            team_impacts: Optional[dict] = None) -> dict:
        cache_key = ",".join(sorted(t["name"] for t in teams))
        cache_key = f"{cache_key}:{iterations}"
        if team_impacts:
            impact_str = ",".join(f"{k}:{v}" for k, v in sorted(
                (code, f"{imp.get('attack',0):.2f},{imp.get('defense',0):.2f}")
                for code, imp in team_impacts.items()
            ))
            cache_key = f"{cache_key}:imp({impact_str})"

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

        champion_counts: dict[str, int] = defaultdict(int)
        rng = self._rng

        for _ in range(iterations):
            champ = self._sim_one(team_ids, tid2info, rng, team_impacts)
            champion_counts[champ] += 1

        total = max(sum(champion_counts.values()), 1)
        probs = {name: count / total for name, count in champion_counts.items()}
        top3 = sorted(probs.items(), key=lambda x: -x[1])[:3]

        result = {
            "champion_probs": probs,
            "top3": top3,
            "iterations": iterations,
        }

        with self._lock:
            self._cache[cache_key] = (time.time(), result)

        return result

    def _sim_one(self, team_ids, tid2info, rng, team_impacts=None):
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

        for _ in range(4):  # R32, R16, QF, SF
            winners = []
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
                    winners.append(a)
                elif ag > hg:
                    winners.append(b)
                else:
                    winners.append(a if a[3] >= b[3] else b)
            current = winners

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
            return a[1]
        elif ag > hg:
            return b[1]
        return a[1] if a[3] >= b[3] else b[1]


_engine: Optional[MonteCarloEngine] = None


def get_engine() -> MonteCarloEngine:
    global _engine
    if _engine is None:
        _engine = MonteCarloEngine()
    return _engine
