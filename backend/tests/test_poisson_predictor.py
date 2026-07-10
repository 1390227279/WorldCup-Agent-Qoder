"""
泊松预测器测试套件。

测试覆盖：
  1. 攻击力/防守力推导正确性
  2. 预期进球计算
  3. 比分预测概率分布
  4. 模拟比赛合理性
  5. 边界情况（极低/极高 ELO）

Run: pytest tests/test_poisson_predictor.py -v
"""

import pytest

from app.services.poisson_predictor import (
    PoissonPredictor,
    ScorePrediction,
    ATTACK_FACTOR,
    DEFENSE_FACTOR,
    ELO_DIVISOR,
    HOME_ADVANTAGE_COEFF,
)


@pytest.fixture
def predictor() -> PoissonPredictor:
    """创建默认参数的预测器实例。"""
    return PoissonPredictor()


# ── 攻击力 / 防守力推导 ──────────────────────────────────

class TestAttackDefenseStrength:
    """验证 ELO → 攻防指标的推导。"""

    def test_attack_strength_default_elo(self, predictor: PoissonPredictor):
        """ELO 1500 → attack = 1500/1000 * 0.8 = 1.2"""
        attack = predictor.attack_strength(1500)
        assert attack == pytest.approx(1.2, rel=1e-3)

    def test_defense_strength_default_elo(self, predictor: PoissonPredictor):
        """ELO 1500 → defense = 1500/1000 * 0.6 = 0.9"""
        defense = predictor.defense_strength(1500)
        assert defense == pytest.approx(0.9, rel=1e-3)

    def test_attack_higher_elo_is_stronger(self, predictor: PoissonPredictor):
        """高 ELO 球队攻击力更高。"""
        strong = predictor.attack_strength(2100)
        weak = predictor.attack_strength(1200)
        assert strong > weak

    def test_defense_higher_elo_is_stronger(self, predictor: PoissonPredictor):
        """高 ELO 球队防守力更高。"""
        strong = predictor.defense_strength(2100)
        weak = predictor.defense_strength(1200)
        assert strong > weak

    def test_attack_defense_ratio(self, predictor: PoissonPredictor):
        """攻击力系数(0.8) > 防守力系数(0.6)，同 ELO 下攻击 > 防守。"""
        attack = predictor.attack_strength(1800)
        defense = predictor.defense_strength(1800)
        assert attack > defense


# ── 预期进球计算 ──────────────────────────────────────────

class TestPredict:
    """验证 predict() 预期进球计算。"""

    def test_equal_teams_home_advantage(self, predictor: PoissonPredictor):
        """实力相同球队：主队预期进球 > 客队（因为有主场优势）。"""
        attack = predictor.attack_strength(1500)
        defense = predictor.defense_strength(1500)
        home_exp, away_exp = predictor.predict(attack, defense, attack, defense)
        assert home_exp > away_exp

    def test_strong_vs_weak(self, predictor: PoissonPredictor):
        """强队 vs 弱队：强队预期进球更高。"""
        strong_atk = predictor.attack_strength(2100)
        strong_def = predictor.defense_strength(2100)
        weak_atk = predictor.attack_strength(1200)
        weak_def = predictor.defense_strength(1200)
        # 强队主场
        home_exp, away_exp = predictor.predict(strong_atk, weak_def, weak_atk, strong_def)
        assert home_exp > away_exp

    def test_expected_goals_positive(self, predictor: PoissonPredictor):
        """预期进球始终为正数。"""
        for elo in [800, 1500, 2200]:
            atk = predictor.attack_strength(elo)
            dfn = predictor.defense_strength(elo)
            h, a = predictor.predict(atk, dfn, atk, dfn)
            assert h > 0
            assert a > 0

    def test_defense_floor(self, predictor: PoissonPredictor):
        """极低防守力不会导致除零或异常。"""
        h, a = predictor.predict(2.0, 0.0, 2.0, 0.0)  # defense=0 触发下限
        assert h > 0
        assert a > 0


# ── 比分预测 ──────────────────────────────────────────────

class TestPredictScore:
    """验证 predict_score() 的概率分布。"""

    def test_return_type(self, predictor: PoissonPredictor):
        """返回类型应为 ScorePrediction。"""
        result = predictor.predict_score("Brazil", "Germany", 2100, 1900)
        assert isinstance(result, ScorePrediction)

    def test_probabilities_sum_to_one(self, predictor: PoissonPredictor):
        """主胜 + 平局 + 客胜 ≈ 1.0。"""
        result = predictor.predict_score("Brazil", "Germany", 2100, 1900)
        total = result.home_win_prob + result.draw_prob + result.away_win_prob
        assert total == pytest.approx(1.0, abs=0.02)

    def test_strong_home_team_favored(self, predictor: PoissonPredictor):
        """高 ELO 主队应该有更高胜率。"""
        result = predictor.predict_score("Brazil", "China PR", 2100, 1350)
        assert result.home_win_prob > result.away_win_prob
        assert result.home_win_prob > 0.5

    def test_equal_teams_draw_significant(self, predictor: PoissonPredictor):
        """实力相近球队，平局概率不应太低。"""
        result = predictor.predict_score("France", "England", 1900, 1900)
        assert result.draw_prob > 0.15  # 平局概率至少 15%

    def test_most_likely_score_format(self, predictor: PoissonPredictor):
        """most_likely_score 应为 'X-Y' 格式。"""
        result = predictor.predict_score("Argentina", "Japan", 2100, 1600)
        parts = result.most_likely_score.split("-")
        assert len(parts) == 2
        assert int(parts[0]) >= 0
        assert int(parts[1]) >= 0

    def test_expected_goals_reasonable(self, predictor: PoissonPredictor):
        """预期进球应在合理范围 (0.1 - 10)。"""
        result = predictor.predict_score("Brazil", "China PR", 2100, 1350)
        assert 0.1 <= result.home_expected_goals <= 10
        assert 0.1 <= result.away_expected_goals <= 10

    def test_extreme_elo_gap(self, predictor: PoissonPredictor):
        """极大 ELO 差距时强队胜率应极高。"""
        result = predictor.predict_score("Brazil", "China PR", 2200, 800)
        assert result.home_win_prob > 0.85


# ── 模拟比赛 ──────────────────────────────────────────────

class TestSimulateMatch:
    """验证 simulate_match() 蒙特卡洛模拟。"""

    def test_return_format(self, predictor: PoissonPredictor):
        """返回 (home, away, home_goals, away_goals) 四元组。"""
        result = predictor.simulate_match("Brazil", "Germany", 2100, 1900, seed=42)
        assert len(result) == 4
        assert result[0] == "Brazil"
        assert result[1] == "Germany"
        assert isinstance(result[2], int)
        assert isinstance(result[3], int)

    def test_goals_non_negative(self, predictor: PoissonPredictor):
        """模拟进球不应为负数。"""
        for seed in range(50):
            _, _, h, a = predictor.simulate_match("A", "B", 1800, 1600, seed=seed)
            assert h >= 0
            assert a >= 0

    def test_reproducible_with_seed(self, predictor: PoissonPredictor):
        """相同 seed 应产生相同结果。"""
        r1 = predictor.simulate_match("A", "B", 1800, 1600, seed=123)
        r2 = predictor.simulate_match("A", "B", 1800, 1600, seed=123)
        assert r1 == r2

    def test_strong_team_wins_more(self, predictor: PoissonPredictor):
        """统计意义上强队应赢更多场次。"""
        strong_wins = 0
        n_simulations = 500
        for seed in range(n_simulations):
            _, _, h, a = predictor.simulate_match(
                "Strong", "Weak", 2100, 1200, seed=seed,
            )
            if h > a:
                strong_wins += 1
        # 强队胜率应超过 60%
        win_rate = strong_wins / n_simulations
        assert win_rate > 0.6, f"Strong team win rate {win_rate:.2%} too low"


# ── 边界情况 ──────────────────────────────────────────────

class TestEdgeCases:
    """极端输入和边界情况。"""

    def test_very_low_elo(self, predictor: PoissonPredictor):
        """极低 ELO（100）不应崩溃。"""
        result = predictor.predict_score("A", "B", 100, 100)
        assert result.home_win_prob >= 0
        assert result.draw_prob >= 0
        assert result.away_win_prob >= 0

    def test_very_high_elo(self, predictor: PoissonPredictor):
        """极高 ELO（3000）不应崩溃。"""
        result = predictor.predict_score("A", "B", 3000, 3000)
        total = result.home_win_prob + result.draw_prob + result.away_win_prob
        assert total == pytest.approx(1.0, abs=0.02)

    def test_same_elo_both_directions(self, predictor: PoissonPredictor):
        """同 ELO 互换主客场，主队概率应相同。"""
        r1 = predictor.predict_score("A", "B", 1800, 1800)
        r2 = predictor.predict_score("B", "A", 1800, 1800)
        assert r1.home_win_prob == pytest.approx(r2.home_win_prob, abs=0.01)

    def test_custom_parameters(self):
        """自定义参数应正常生效。"""
        p = PoissonPredictor(attack_factor=1.0, defense_factor=0.5, home_advantage=1.2)
        result = p.predict_score("A", "B", 1800, 1600)
        assert isinstance(result, ScorePrediction)
