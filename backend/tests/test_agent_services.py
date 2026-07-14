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
from app.services.qwen_client import DashScopeResponse, ToolCall


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

    @pytest.mark.asyncio
    async def test_agent_prompt_requires_chinese_and_uses_chinese_team_names(self):
        class CapturingQwenClient:
            messages = None

            async def chat_with_tools(self, messages, tools):
                self.messages = messages
                return DashScopeResponse(tool_calls=[ToolCall(
                    id="submit-1",
                    name="submit_match_analysis",
                    arguments={
                        "key_factors": ["阿根廷中场控制力更稳定"],
                        "risk_notes": ["代表路径并非唯一比赛结果"],
                        "reasoning_chain": [{
                            "step_number": 1,
                            "finding": "读取既有数学结果",
                            "analysis": "仅解释结果，不修改比分。",
                        }],
                    },
                )])

        class EmptyToolRegistry:
            @staticmethod
            def get_tools():
                return []

        qwen_client = CapturingQwenClient()
        service = AgentService(
            qwen_client=qwen_client,
            tool_registry=EmptyToolRegistry(),
        )
        result = await service.analyze_simulated_match({
            "home_team": {"name": "Argentina", "name_cn": "阿根廷"},
            "away_team": {"name": "Brazil", "name_cn": "巴西"},
            "predicted_score": "2-1",
        }, None)

        assert result.is_valid is True
        assert "所有面向用户的输出必须使用简体中文" in qwen_client.messages[0]["content"]
        assert "请解释 阿根廷 对阵 巴西" in qwen_client.messages[1]["content"]

        tool = service._submit_match_analysis_tool_def()
        properties = tool["function"]["parameters"]["properties"]
        assert properties["key_factors"]["items"]["description"] == "必须使用简体中文"
        assert properties["reasoning_chain"]["items"]["properties"]["finding"]["description"] == "必须使用简体中文"

    @pytest.mark.asyncio
    async def test_plain_chinese_response_is_converted_to_stable_report(self):
        class PlainTextQwenClient:
            calls = 0

            async def chat_with_tools(self, messages, tools):
                self.calls += 1
                return DashScopeResponse(content=(
                    "阿根廷中场控制更加稳定。\n"
                    "西班牙仍可能通过高位压迫制造机会。\n"
                    "该代表路径并不是唯一可能结果。"
                ))

        class EmptyToolRegistry:
            @staticmethod
            def get_tools():
                return []

        client = PlainTextQwenClient()
        result = await AgentService(client, EmptyToolRegistry()).analyze_simulated_match({
            "home_team": {"name": "Spain", "name_cn": "西班牙"},
            "away_team": {"name": "Argentina", "name_cn": "阿根廷"},
            "predicted_score": "0-1",
        }, None)

        assert result.is_valid is True
        assert client.calls == 2
        assert result.cleaned_data.key_factors[0] == "阿根廷中场控制更加稳定。"
        assert result.cleaned_data.reasoning_chain[0].step_number == 1
        assert result.cleaned_data.reasoning_chain[0].tool_used == "qwen_text_fallback"

    @pytest.mark.asyncio
    async def test_final_submission_retry_accepts_submit_tool(self):
        class RetryQwenClient:
            calls = 0

            async def chat_with_tools(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    return DashScopeResponse(content="我已经完成分析，但暂未调用提交工具。")
                return DashScopeResponse(tool_calls=[ToolCall(
                    id="submit-final",
                    name="submit_match_analysis",
                    arguments={
                        "key_factors": ["阿根廷把握机会的能力更强"],
                        "risk_notes": ["单场淘汰赛仍有偶然性"],
                        "reasoning_chain": [{"step_number": 1, "finding": "读取数学比分"}],
                    },
                )])

        class EmptyToolRegistry:
            @staticmethod
            def get_tools():
                return []

        client = RetryQwenClient()
        result = await AgentService(client, EmptyToolRegistry()).analyze_simulated_match({
            "home_team": {"name": "Spain", "name_cn": "西班牙"},
            "away_team": {"name": "Argentina", "name_cn": "阿根廷"},
            "predicted_score": "0-1",
        }, None)
        assert result.is_valid is True
        assert client.calls == 2
        assert result.cleaned_data.key_factors == ["阿根廷把握机会的能力更强"]

    @pytest.mark.asyncio
    async def test_plain_text_survives_failed_final_retry(self):
        class FailingRetryClient:
            calls = 0

            async def chat_with_tools(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    return DashScopeResponse(content="阿根廷在既有数学路径中把握住了关键机会。")
                raise TimeoutError("最终结构化提交超时")

        class EmptyToolRegistry:
            @staticmethod
            def get_tools():
                return []

        result = await AgentService(FailingRetryClient(), EmptyToolRegistry()).analyze_simulated_match({
            "home_team": {"name": "Spain", "name_cn": "西班牙"},
            "away_team": {"name": "Argentina", "name_cn": "阿根廷"},
            "predicted_score": "0-1",
        }, None)
        assert result.is_valid is True
        assert result.cleaned_data.key_factors == ["阿根廷在既有数学路径中把握住了关键机会。"]
