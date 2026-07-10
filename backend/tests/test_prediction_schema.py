"""
Pydantic 校验模块 (prediction_schema) 的完整测试套件。

覆盖 TEAM_NAMES / _TEAM_NAME_LOOKUP 常量、所有 Pydantic 模型、
validate_prediction 六项校验规则以及各种边界与异常场景。

Run: pytest tests/test_prediction_schema.py -v
"""

import pytest

from app.schema.prediction_schema import (
    PredictionInput,
    ReasoningStep,
    ToolCallRecord,
    ValidatedPrediction,
    ValidationResult,
    validate_prediction,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_input(**overrides) -> PredictionInput:
    """构造一个合法的最小 PredictionInput，可按需覆盖字段。"""
    defaults = dict(
        winner="Brazil",
        predicted_score="2-1",
        confidence=0.75,
        key_factors=["Recent form is strong", "Key player available"],
        reasoning_chain=[
            {"step_number": 1, "finding": "Brazil won last 5 matches"},
            {"step_number": 2, "finding": "Opponent has injury concerns", "tool_used": "search"},
        ],
        tool_calls_log=[
            {"tool_name": "get_rankings", "input_params": {"team": "Brazil"}},
        ],
    )
    defaults.update(overrides)
    return PredictionInput(**defaults)


# ===========================================================================
# Pydantic 模型单元测试
# ===========================================================================

class TestToolCallRecord:
    """ToolCallRecord 模型字段与默认值。"""

    def test_required_fields(self):
        record = ToolCallRecord(tool_name="search")
        assert record.tool_name == "search"

    def test_defaults(self):
        record = ToolCallRecord(tool_name="x")
        assert record.input_params == {}
        assert record.output_summary == ""
        assert record.execution_time_ms == 0
        assert record.success is True

    def test_custom_values(self):
        record = ToolCallRecord(
            tool_name="calc",
            input_params={"a": 1},
            output_summary="result=42",
            execution_time_ms=120,
            success=False,
        )
        assert record.execution_time_ms == 120
        assert record.success is False

    def test_negative_execution_time_rejected(self):
        with pytest.raises(Exception):
            ToolCallRecord(tool_name="x", execution_time_ms=-1)

    def test_missing_tool_name_rejected(self):
        with pytest.raises(Exception):
            ToolCallRecord()  # type: ignore[call-arg]


class TestReasoningStep:
    """ReasoningStep 模型字段与默认值。"""

    def test_required_fields(self):
        step = ReasoningStep(step_number=1, finding="something")
        assert step.step_number == 1
        assert step.finding == "something"

    def test_optional_defaults(self):
        step = ReasoningStep(step_number=1, finding="x")
        assert step.tool_used is None
        assert step.analysis is None

    def test_full_fields(self):
        step = ReasoningStep(
            step_number=3,
            tool_used="search",
            finding="team is strong",
            analysis="based on Elo",
        )
        assert step.tool_used == "search"
        assert step.analysis == "based on Elo"

    def test_missing_step_number_rejected(self):
        with pytest.raises(Exception):
            ReasoningStep(finding="x")  # type: ignore[call-arg]

    def test_missing_finding_rejected(self):
        with pytest.raises(Exception):
            ReasoningStep(step_number=1)  # type: ignore[call-arg]


class TestPredictionInput:
    """PredictionInput 所有字段均为 Optional。"""

    def test_all_none_by_default(self):
        p = PredictionInput()
        assert p.winner is None
        assert p.predicted_score is None
        assert p.confidence is None
        assert p.key_factors is None
        assert p.reasoning_chain is None
        assert p.tool_calls_log is None

    def test_partial_construction(self):
        p = PredictionInput(winner="Brazil", confidence=0.8)
        assert p.winner == "Brazil"
        assert p.confidence == 0.8


class TestValidatedPrediction:
    """ValidatedPrediction 约束校验。"""

    def test_valid_construction(self):
        vp = ValidatedPrediction(
            winner="Brazil",
            confidence=0.8,
            key_factors=["form"],
        )
        assert vp.winner == "Brazil"
        assert vp.predicted_score == ""
        assert vp.reasoning_chain == []
        assert vp.tool_calls_log == []

    def test_confidence_too_low(self):
        with pytest.raises(Exception):
            ValidatedPrediction(winner="X", confidence=-0.1, key_factors=["a"])

    def test_confidence_too_high(self):
        with pytest.raises(Exception):
            ValidatedPrediction(winner="X", confidence=1.5, key_factors=["a"])

    def test_empty_key_factors_rejected(self):
        with pytest.raises(Exception):
            ValidatedPrediction(winner="X", confidence=0.5, key_factors=[])


class TestValidationResult:
    """ValidationResult 模型默认值。"""

    def test_defaults(self):
        vr = ValidationResult(is_valid=True)
        assert vr.errors == []
        assert vr.warnings == []
        assert vr.cleaned_data is None
        assert vr.model_used == "qwen-max"
        assert vr.is_agent is True


# ===========================================================================
# validate_prediction — 1. winner 校验
# ===========================================================================

class TestValidateWinner:
    """winner 字段的各种场景。"""

    def test_none_winner_invalid(self):
        result = validate_prediction(_valid_input(winner=None))
        assert result.is_valid is False
        assert any("winner" in e for e in result.errors)

    def test_empty_winner_invalid(self):
        result = validate_prediction(_valid_input(winner=""))
        assert result.is_valid is False
        assert any("winner" in e for e in result.errors)

    def test_whitespace_winner_invalid(self):
        result = validate_prediction(_valid_input(winner="   "))
        assert result.is_valid is False

    def test_draw_lowercase(self):
        result = validate_prediction(_valid_input(winner="draw"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "draw"

    def test_draw_uppercase(self):
        result = validate_prediction(_valid_input(winner="DRAW"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "draw"

    def test_draw_mixed_case(self):
        result = validate_prediction(_valid_input(winner="Draw"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "draw"

    def test_known_team_exact_case(self):
        result = validate_prediction(_valid_input(winner="Brazil"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "Brazil"

    def test_known_team_lowercase(self):
        result = validate_prediction(_valid_input(winner="brazil"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "Brazil"

    def test_known_team_uppercase(self):
        result = validate_prediction(_valid_input(winner="BRAZIL"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "Brazil"

    def test_known_team_with_leading_trailing_spaces(self):
        result = validate_prediction(_valid_input(winner="  Brazil  "))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "Brazil"

    def test_china_pr(self):
        result = validate_prediction(_valid_input(winner="china pr"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "China PR"

    def test_korea_republic(self):
        result = validate_prediction(_valid_input(winner="korea republic"))
        assert result.is_valid is True
        assert result.cleaned_data.winner == "Korea Republic"

    def test_unknown_team(self):
        result = validate_prediction(_valid_input(winner="Atlantis"))
        assert result.is_valid is False
        assert any("未知的球队名称" in e for e in result.errors)


# ===========================================================================
# validate_prediction — 2. confidence 校验
# ===========================================================================

class TestValidateConfidence:
    """confidence 字段的各种场景。"""

    def test_none_defaults_to_half(self):
        result = validate_prediction(_valid_input(confidence=None))
        assert result.is_valid is True
        assert result.cleaned_data.confidence == 0.5
        assert any("confidence" in w for w in result.warnings)

    def test_normal_value_unchanged(self):
        result = validate_prediction(_valid_input(confidence=0.85))
        assert result.cleaned_data.confidence == 0.85

    def test_zero_is_valid(self):
        result = validate_prediction(_valid_input(confidence=0.0))
        assert result.cleaned_data.confidence == 0.0

    def test_one_is_valid(self):
        result = validate_prediction(_valid_input(confidence=1.0))
        assert result.cleaned_data.confidence == 1.0

    def test_negative_clamped_to_zero(self):
        result = validate_prediction(_valid_input(confidence=-0.3))
        assert result.cleaned_data.confidence == 0.0
        assert any("修正为 0.0" in w for w in result.warnings)

    def test_above_one_clamped_to_one(self):
        result = validate_prediction(_valid_input(confidence=1.5))
        assert result.cleaned_data.confidence == 1.0
        assert any("修正为 1.0" in w for w in result.warnings)

    def test_large_negative(self):
        result = validate_prediction(_valid_input(confidence=-999))
        assert result.cleaned_data.confidence == 0.0

    def test_large_positive(self):
        result = validate_prediction(_valid_input(confidence=999))
        assert result.cleaned_data.confidence == 1.0


# ===========================================================================
# validate_prediction — 3. key_factors 校验
# ===========================================================================

class TestValidateKeyFactors:
    """key_factors 字段的各种场景。"""

    def test_none_invalid(self):
        result = validate_prediction(_valid_input(key_factors=None))
        assert result.is_valid is False
        assert any("key_factors" in e for e in result.errors)

    def test_empty_list_invalid(self):
        result = validate_prediction(_valid_input(key_factors=[]))
        assert result.is_valid is False

    def test_all_empty_strings_invalid(self):
        result = validate_prediction(_valid_input(key_factors=["", "", ""]))
        assert result.is_valid is False

    def test_all_short_strings_invalid(self):
        result = validate_prediction(_valid_input(key_factors=["ab", "cd", "ef"]))
        assert result.is_valid is False

    def test_filters_short_entries(self):
        result = validate_prediction(
            _valid_input(key_factors=["Good form", "ab", "Strong defense"])
        )
        assert result.is_valid is True
        assert len(result.cleaned_data.key_factors) == 2
        assert any("已过滤" in w for w in result.warnings)

    def test_filters_empty_strings(self):
        result = validate_prediction(
            _valid_input(key_factors=["Good form", "", "Strong defense"])
        )
        assert result.is_valid is True
        assert len(result.cleaned_data.key_factors) == 2

    def test_truncates_at_ten(self):
        factors = [f"Factor number {i:02d} description" for i in range(15)]
        result = validate_prediction(_valid_input(key_factors=factors))
        assert result.is_valid is True
        assert len(result.cleaned_data.key_factors) == 10
        assert any("截断" in w for w in result.warnings)

    def test_exactly_ten_not_truncated(self):
        factors = [f"Factor number {i:02d} description" for i in range(10)]
        result = validate_prediction(_valid_input(key_factors=factors))
        assert result.is_valid is True
        assert len(result.cleaned_data.key_factors) == 10
        assert not any("截断" in w for w in result.warnings)

    def test_single_valid_factor(self):
        result = validate_prediction(_valid_input(key_factors=["Excellent attack"]))
        assert result.is_valid is True
        assert result.cleaned_data.key_factors == ["Excellent attack"]


# ===========================================================================
# validate_prediction — 4. reasoning_chain 校验
# ===========================================================================

class TestValidateReasoningChain:
    """reasoning_chain 字段的各种场景。"""

    def test_none_invalid(self):
        result = validate_prediction(_valid_input(reasoning_chain=None))
        assert result.is_valid is False
        assert any("reasoning_chain" in e for e in result.errors)

    def test_empty_list_invalid(self):
        result = validate_prediction(_valid_input(reasoning_chain=[]))
        assert result.is_valid is False

    def test_valid_chain(self):
        chain = [
            {"step_number": 1, "finding": "Team A is strong"},
            {"step_number": 2, "finding": "Team B has injuries", "tool_used": "search"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 2
        assert result.cleaned_data.reasoning_chain[0].step_number == 1
        assert result.cleaned_data.reasoning_chain[1].tool_used == "search"

    def test_step_alias_accepted(self):
        """'step' 字段应被接受并转换为 step_number。"""
        chain = [{"step": 1, "finding": "something"}]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert result.cleaned_data.reasoning_chain[0].step_number == 1

    def test_missing_step_number_skipped(self):
        chain = [
            {"finding": "no step number here"},
            {"step_number": 1, "finding": "valid step"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 1
        assert any("step_number" in w for w in result.warnings)

    def test_missing_finding_skipped(self):
        chain = [
            {"step_number": 1},
            {"step_number": 2, "finding": "valid"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 1
        assert any("finding" in w for w in result.warnings)

    def test_empty_finding_skipped(self):
        chain = [
            {"step_number": 1, "finding": ""},
            {"step_number": 2, "finding": "valid"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 1

    def test_all_items_invalid_becomes_fatal(self):
        chain = [
            {"finding": "no step"},
            {"step_number": 1},  # no finding
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is False
        assert any("reasoning_chain" in e for e in result.errors)

    def test_with_analysis_field(self):
        chain = [
            {"step_number": 1, "finding": "data", "analysis": "deep analysis"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.cleaned_data.reasoning_chain[0].analysis == "deep analysis"

    def test_malformed_item_skipped_with_warning(self):
        chain = [
            {"step_number": "not_a_number_will_fail", "finding": "x"},
            {"step_number": 1, "finding": "valid"},
        ]
        # "not_a_number_will_fail" can't be cast to int → skipped
        # Actually let's check: int("not_a_number_will_fail") raises ValueError → caught
        # But int() on a string that looks like a number works; let's use a truly bad value
        chain = [
            {"step_number": None, "finding": "x"},  # None → step_num is falsy → skipped
            {"step_number": 1, "finding": "valid"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 1


# ===========================================================================
# validate_prediction — 5. tool_calls_log 校验
# ===========================================================================

class TestValidateToolCallsLog:
    """tool_calls_log 字段的各种场景。"""

    def test_none_is_fine(self):
        result = validate_prediction(_valid_input(tool_calls_log=None))
        assert result.is_valid is True
        assert result.cleaned_data.tool_calls_log == []

    def test_empty_list_is_fine(self):
        result = validate_prediction(_valid_input(tool_calls_log=[]))
        assert result.is_valid is True
        assert result.cleaned_data.tool_calls_log == []

    def test_valid_record(self):
        logs = [
            {
                "tool_name": "search",
                "input_params": {"q": "Brazil"},
                "output_summary": "found data",
                "execution_time_ms": 200,
                "success": True,
            }
        ]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert result.is_valid is True
        assert len(result.cleaned_data.tool_calls_log) == 1
        assert result.cleaned_data.tool_calls_log[0].tool_name == "search"

    def test_name_alias_accepted(self):
        """'name' 字段应被接受并转换为 tool_name。"""
        logs = [{"name": "get_elo"}]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert result.is_valid is True
        assert result.cleaned_data.tool_calls_log[0].tool_name == "get_elo"

    def test_missing_tool_name_skipped(self):
        logs = [
            {"input_params": {}},  # no tool_name or name
            {"tool_name": "valid"},
        ]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert result.is_valid is True
        assert len(result.cleaned_data.tool_calls_log) == 1
        assert any("tool_name" in w for w in result.warnings)

    def test_defaults_applied(self):
        logs = [{"tool_name": "minimal"}]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        record = result.cleaned_data.tool_calls_log[0]
        assert record.input_params == {}
        assert record.output_summary == ""
        assert record.execution_time_ms == 0
        assert record.success is True

    def test_bad_execution_time_skipped(self):
        logs = [
            {"tool_name": "bad", "execution_time_ms": "not_int"},
            {"tool_name": "good"},
        ]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert result.is_valid is True
        assert len(result.cleaned_data.tool_calls_log) == 1
        assert result.cleaned_data.tool_calls_log[0].tool_name == "good"
        assert any("解析失败" in w or "缺少" in w for w in result.warnings)

    def test_multiple_valid_records(self):
        logs = [
            {"tool_name": "a"},
            {"tool_name": "b"},
            {"tool_name": "c"},
        ]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert len(result.cleaned_data.tool_calls_log) == 3


# ===========================================================================
# validate_prediction — 6. predicted_score 校验
# ===========================================================================

class TestValidatePredictedScore:
    """predicted_score 字段的各种场景。"""

    def test_none_defaults_empty(self):
        result = validate_prediction(_valid_input(predicted_score=None))
        assert result.is_valid is True
        assert result.cleaned_data.predicted_score == ""
        assert any("predicted_score" in w for w in result.warnings)

    def test_empty_string_defaults_empty(self):
        result = validate_prediction(_valid_input(predicted_score=""))
        assert result.cleaned_data.predicted_score == ""
        assert any("predicted_score" in w for w in result.warnings)

    def test_whitespace_only(self):
        result = validate_prediction(_valid_input(predicted_score="   "))
        assert result.cleaned_data.predicted_score == ""
        assert any("predicted_score" in w for w in result.warnings)

    def test_valid_score_format(self):
        result = validate_prediction(_valid_input(predicted_score="3-2"))
        assert result.cleaned_data.predicted_score == "3-2"

    def test_no_dash_warning(self):
        result = validate_prediction(_valid_input(predicted_score="2:1"))
        assert result.is_valid is True  # not fatal
        assert result.cleaned_data.predicted_score == "2:1"
        assert any("格式异常" in w for w in result.warnings)

    def test_score_never_fatal(self):
        """predicted_score 校验永远不会导致 is_valid=False。"""
        result = validate_prediction(_valid_input(predicted_score="garbage"))
        assert result.is_valid is True


# ===========================================================================
# validate_prediction — 综合 / 边界场景
# ===========================================================================

class TestValidateEdgeCases:
    """组合场景与全局异常兜底。"""

    def test_fully_valid_input(self):
        result = validate_prediction(_valid_input())
        assert result.is_valid is True
        assert result.errors == []
        assert result.cleaned_data is not None
        assert result.cleaned_data.winner == "Brazil"
        assert result.cleaned_data.confidence == 0.75
        assert result.model_used == "qwen-max"
        assert result.is_agent is True

    def test_all_empty_input(self):
        """全部字段 None → 多个致命错误。"""
        result = validate_prediction(PredictionInput())
        assert result.is_valid is False
        assert result.cleaned_data is None
        assert len(result.errors) >= 3  # winner, key_factors, reasoning_chain

    def test_multiple_errors_accumulated(self):
        """同时缺少 winner 和 key_factors 应累积多个错误。"""
        result = validate_prediction(
            _valid_input(winner=None, key_factors=None)
        )
        assert result.is_valid is False
        assert any("winner" in e for e in result.errors)
        assert any("key_factors" in e for e in result.errors)

    def test_warnings_present_on_valid_result(self):
        """合法数据也可以伴随 warning（如 confidence 缺失）。"""
        result = validate_prediction(_valid_input(confidence=None))
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_cleaned_data_none_when_invalid(self):
        result = validate_prediction(_valid_input(winner=None))
        assert result.cleaned_data is None

    def test_reasoning_chain_mixed_valid_and_invalid(self):
        """混合有效/无效条目时，只保留有效的。"""
        chain = [
            {"step_number": 1, "finding": "good"},
            {"step_number": 2},  # missing finding
            {"step_number": 3, "finding": "also good", "analysis": "deep"},
        ]
        result = validate_prediction(_valid_input(reasoning_chain=chain))
        assert result.is_valid is True
        assert len(result.cleaned_data.reasoning_chain) == 2
        assert result.cleaned_data.reasoning_chain[1].analysis == "deep"

    def test_tool_calls_with_name_and_tool_name_mixed(self):
        logs = [
            {"tool_name": "search_api"},
            {"name": "get_rankings"},
        ]
        result = validate_prediction(_valid_input(tool_calls_log=logs))
        assert len(result.cleaned_data.tool_calls_log) == 2

    def test_result_metadata_defaults(self):
        result = validate_prediction(_valid_input())
        assert result.model_used == "qwen-max"
        assert result.is_agent is True
