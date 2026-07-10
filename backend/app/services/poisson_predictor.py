"""
Poisson Score Predictor — 泊松分布比分预测器

Agent 系统的统计兜底模型（第三层容错）：
当 Qwen API 故障或 CircuitBreaker 触发时，降级使用本模块进行预测。

核心原理：
  1. 从 ELO 分数推导攻击力和防守力
  2. 用泊松分布计算每支球队的进球概率分布
  3. 枚举所有可能比分，计算胜/平/负概率

依赖：scipy.stats.poisson
"""

import random
from dataclasses import dataclass

from scipy.stats import poisson


# ── 常量 ──────────────────────────────────────────────────

ATTACK_FACTOR = 0.8          # ELO → 攻击力 的缩放系数
DEFENSE_FACTOR = 0.6         # ELO → 防守力 的缩放系数
ELO_DIVISOR = 1000.0         # ELO 归一化除数
HOME_ADVANTAGE_COEFF = 1.1   # 主场进球优势系数
MAX_GOALS = 10               # 枚举比分时的最大进球数


# ── 输出数据结构 ──────────────────────────────────────────

@dataclass
class ScorePrediction:
    """泊松模型预测结果。"""

    most_likely_score: str       # 最可能比分，如 "2-1"
    home_win_prob: float         # 主队胜率 (0-1)
    draw_prob: float             # 平局概率 (0-1)
    away_win_prob: float         # 客队胜率 (0-1)
    home_expected_goals: float   # 主队预期进球
    away_expected_goals: float   # 客队预期进球


# ── 预测器 ────────────────────────────────────────────────

class PoissonPredictor:
    """基于泊松分布的比分预测器。

    使用场景：
      - Agent 系统降级兜底（Qwen API 不可用时）
      - 为 Agent 的工具箱提供统计基线预测
      - 蒙特卡洛模拟单场比赛
    """

    def __init__(
        self,
        attack_factor: float = ATTACK_FACTOR,
        defense_factor: float = DEFENSE_FACTOR,
        elo_divisor: float = ELO_DIVISOR,
        home_advantage: float = HOME_ADVANTAGE_COEFF,
        max_goals: int = MAX_GOALS,
    ) -> None:
        """初始化预测器，允许覆盖默认参数。

        Args:
            attack_factor: ELO → 攻击力的缩放系数。
            defense_factor: ELO → 防守力的缩放系数。
            elo_divisor: ELO 归一化除数。
            home_advantage: 主场进球优势系数。
            max_goals: 枚举比分时的最大进球数。
        """
        self.attack_factor = attack_factor
        self.defense_factor = defense_factor
        self.elo_divisor = elo_divisor
        self.home_advantage = home_advantage
        self.max_goals = max_goals

    # ── 攻击力 / 防守力推导 ──────────────────────────────

    def attack_strength(self, elo: float) -> float:
        """从 ELO 分数推导攻击力。

        Formula: attack = (ELO / elo_divisor) * attack_factor
        典型值：ELO 1800 → attack ≈ 1.44

        Args:
            elo: 球队 ELO 分数。

        Returns:
            攻击力指标（正数，越高越强）。
        """
        return (elo / self.elo_divisor) * self.attack_factor

    def defense_strength(self, elo: float) -> float:
        """从 ELO 分数推导防守力。

        Formula: defense = (ELO / elo_divisor) * defense_factor
        典型值：ELO 1800 → defense ≈ 1.08

        注意：防守力越高，对手预期进球越少。
        在计算对手预期进球时，我们用 1/defense 来削弱对方攻击力。

        Args:
            elo: 球队 ELO 分数。

        Returns:
            防守力指标（正数，越高越强）。
        """
        return (elo / self.elo_divisor) * self.defense_factor

    # ── 核心预测 ─────────────────────────────────────────

    def predict(
        self,
        home_team_attack: float,
        away_team_defense: float,
        away_team_attack: float,
        home_team_defense: float,
    ) -> tuple[float, float]:
        """计算主客队预期进球数。

        Formula:
          home_expected = home_attack / away_defense * home_advantage
          away_expected = away_attack / home_defense

        防守力取倒数来"削弱"对方攻击力——防守越强，对方进球越少。
        为防止除零，防守力下限为 0.1。

        Args:
            home_team_attack: 主队攻击力。
            away_team_defense: 客队防守力。
            away_team_attack: 客队攻击力。
            home_team_defense: 主队防守力。

        Returns:
            (home_expected_goals, away_expected_goals)
        """
        away_def = max(away_team_defense, 0.1)
        home_def = max(home_team_defense, 0.1)

        home_expected = (home_team_attack / away_def) * self.home_advantage
        away_expected = away_team_attack / home_def

        # 预期进球下限为 0.1（避免泊松 lambda=0 的退化情况）
        home_expected = max(home_expected, 0.1)
        away_expected = max(away_expected, 0.1)

        return home_expected, away_expected

    def predict_score(
        self,
        home_team: str,
        away_team: str,
        home_elo: float,
        away_elo: float,
    ) -> ScorePrediction:
        """预测一场比赛的最可能比分和胜/平/负概率。

        完整流程：
          1. ELO → 攻击力 / 防守力
          2. 攻击力 / 防守力 → 预期进球
          3. 泊松分布 → 各进球数概率
          4. 枚举所有比分组合 → 最可能比分 + 胜负概率

        Args:
            home_team: 主队名称。
            away_team: 客队名称。
            home_elo: 主队 ELO 分数。
            away_elo: 客队 ELO 分数。

        Returns:
            ScorePrediction 包含最可能比分和概率分布。
        """
        # Step 1: ELO → 攻防指标
        home_attack = self.attack_strength(home_elo)
        home_defense = self.defense_strength(home_elo)
        away_attack = self.attack_strength(away_elo)
        away_defense = self.defense_strength(away_elo)

        # Step 2: 预期进球
        home_exp, away_exp = self.predict(
            home_attack, away_defense, away_attack, home_defense,
        )

        # Step 3 & 4: 泊松分布 → 枚举比分
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0
        best_score = (0, 0)
        best_prob = 0.0

        for h in range(self.max_goals + 1):
            p_home_goal = poisson.pmf(h, home_exp)
            for a in range(self.max_goals + 1):
                p_away_goal = poisson.pmf(a, away_exp)
                p = p_home_goal * p_away_goal

                if h > a:
                    home_win_prob += p
                elif h == a:
                    draw_prob += p
                else:
                    away_win_prob += p

                if p > best_prob:
                    best_prob = p
                    best_score = (h, a)

        most_likely = f"{best_score[0]}-{best_score[1]}"

        return ScorePrediction(
            most_likely_score=most_likely,
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            home_expected_goals=round(home_exp, 2),
            away_expected_goals=round(away_exp, 2),
        )

    # ── 蒙特卡洛模拟 ─────────────────────────────────────

    def simulate_match(
        self,
        home_team: str,
        away_team: str,
        home_elo: float,
        away_elo: float,
        seed: int | None = None,
    ) -> tuple[str, str, int, int]:
        """用概率抽样随机生成一场比赛的比分。

        基于泊松分布随机抽样，适合蒙特卡洛模拟锦标赛。

        Args:
            home_team: 主队名称。
            away_team: 客队名称。
            home_elo: 主队 ELO 分数。
            away_elo: 客队 ELO 分数。
            seed: 随机种子（可选，用于可复现的模拟）。

        Returns:
            (home_team, away_team, home_goals, away_goals)
        """
        if seed is not None:
            random.seed(seed)

        # 计算预期进球
        home_attack = self.attack_strength(home_elo)
        home_defense = self.defense_strength(home_elo)
        away_attack = self.attack_strength(away_elo)
        away_defense = self.defense_strength(away_elo)
        home_exp, away_exp = self.predict(
            home_attack, away_defense, away_attack, home_defense,
        )

        # 泊松随机抽样
        home_goals = int(poisson.rvs(home_exp, random_state=random.randint(0, 2**31)))
        away_goals = int(poisson.rvs(away_exp, random_state=random.randint(0, 2**31)))

        return home_team, away_team, home_goals, away_goals
