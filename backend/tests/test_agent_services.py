"""Circuit breaker, Poisson utility, and AI explanation contract tests."""

import time

import pytest

from app.services.circuit_breaker import CircuitBreaker, CircuitState
from app.services.poisson_predictor import PoissonPredictor
from app.schema.prediction_schema import (
    AgentReportInput,
    validate_agent_report,
)
from app.services.agent_service import AgentService


# ── CircuitBreaker ────────────────────────────────────────


class TestCircuitBreaker:
    """熔断器状态机测试。"""

    def test_initial_state_closed(self):
        """初始状态应为 CLOSED。"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_three_failures_open(self):
        """连续失败 3 次后状态应变为 OPEN。"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_is_open_returns_true_after_trip(self):
        """熔断后 is_open() 应返回 True。"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.is_open() is True

    def test_recovery_timeout_half_open(self):
        """超过恢复超时后应自动进入 HALF_OPEN（is_open 返回 False）。"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        # 模拟超时已过
        breaker._opened_at = time.time() - 2
        assert breaker.is_open() is False  # OPEN → HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

    def test_success_from_half_open_to_closed(self):
        """HALF_OPEN 状态下记录成功应恢复到 CLOSED。"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        for _ in range(3):
            breaker.record_failure()
        # 触发 OPEN → HALF_OPEN
        breaker._opened_at = time.time() - 2
        breaker.is_open()
        assert breaker.state == CircuitState.HALF_OPEN
        # HALF_OPEN + success → CLOSED
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


# ── PoissonPredictor ──────────────────────────────────────


class TestPoissonPredictor:
    """泊松分布预测器测试。"""

    def test_predict_score_format(self):
        """predict_score 返回的比分格式应为 'X-Y'。"""
        predictor = PoissonPredictor()
        result = predictor.predict_score("Argentina", "Brazil", 2120, 2100)
        parts = result.most_likely_score.split("-")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    def test_high_elo_more_expected_goals(self):
        """高 ELO 球队预期进球应高于低 ELO 球队。"""
        predictor = PoissonPredictor()
        # 强队主场 vs 弱队
        result = predictor.predict_score("Argentina", "Qatar", 2120, 1480)
        assert result.home_expected_goals > result.away_expected_goals

    def test_probabilities_sum_to_one(self):
        """主胜 + 平局 + 客胜概率之和应约等于 1。"""
        predictor = PoissonPredictor()
        result = predictor.predict_score("France", "Germany", 2080, 1970)
        total = result.home_win_prob + result.draw_prob + result.away_win_prob
        assert total == pytest.approx(1.0, abs=0.02)


class TestAgentReportContract:
    def test_agent_report_steps_are_renumbered_continuously(self):
        result = validate_agent_report(AgentReportInput(
            key_factors=["后端数学结果保持不变"],
            risk_notes=["代表路径不是唯一结果"],
            reasoning_chain=[
                {"step_number": 0, "finding": "读取数学上下文"},
                {"step_number": 9, "finding": "解释事件影响"},
            ],
        ))
        assert result.is_valid is True
        assert [
            step.step_number for step in result.cleaned_data.reasoning_chain
        ] == [1, 2]

    def test_agent_analysis_tool_cannot_submit_math_results(self):
        tool = AgentService._submit_match_analysis_tool_def()
        properties = tool["function"]["parameters"]["properties"]
        assert "winner" not in properties
        assert "predicted_score" not in properties
        assert "confidence" not in properties
