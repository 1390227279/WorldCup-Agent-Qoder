"""
Agent 预测结果的 Pydantic 校验模块 —— 第二层容错防线。

对 Qwen 返回的原始预测数据进行结构化校验、清洗和标准化，
确保下游消费方始终拿到合法、一致的数据结构。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.config import settings  # noqa: F401


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TEAM_NAMES: list[str] = [
    "Argentina", "Australia", "Austria", "Algeria",
    "Belgium", "Brazil", "Canada", "Chile",
    "China PR", "Cameroon", "Colombia", "Costa Rica",
    "Croatia", "Denmark", "Ecuador", "Egypt",
    "England", "Spain", "France", "Germany",
    "Ghana", "Hungary", "Iran", "Italy",
    "Japan", "Korea Republic", "Saudi Arabia", "Morocco",
    "Mexico", "Mali", "Netherlands", "Nigeria",
    "Norway", "New Zealand", "Paraguay", "Peru",
    "Poland", "Portugal", "Qatar", "South Africa",
    "Senegal", "Serbia", "Switzerland", "Sweden",
    "Tunisia", "Ukraine", "Uruguay", "USA",
]

"""大小写不敏感的球队名称查找表：key=lower, value=原始名称。"""
_TEAM_NAME_LOOKUP: dict[str, str] = {name.lower(): name for name in TEAM_NAMES}


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    """记录 Qwen 调用的单个工具详情。"""

    tool_name: str
    input_params: dict = Field(default_factory=dict)
    output_summary: str = ""
    execution_time_ms: int = Field(default=0, ge=0)
    success: bool = True


class ReasoningStep(BaseModel):
    """推理链中的一步。"""

    step_number: int
    tool_used: Optional[str] = None
    finding: str
    analysis: Optional[str] = None


class PredictionInput(BaseModel):
    """传入校验器的原始数据（Qwen 返回的），所有字段 Optional。"""

    winner: Optional[str] = None
    predicted_score: Optional[str] = None
    confidence: Optional[float] = None
    key_factors: Optional[list[str]] = None
    reasoning_chain: Optional[list[dict]] = None
    tool_calls_log: Optional[list[dict]] = None


class ValidatedPrediction(BaseModel):
    """清洗后的标准数据结构。"""

    winner: str
    predicted_score: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    key_factors: list[str] = Field(min_length=1)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    tool_calls_log: list[ToolCallRecord] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """校验结果。"""

    model_config = {"protected_namespaces": ()}  # 消除 model_used 命名空间冲突警告

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cleaned_data: Optional[ValidatedPrediction] = None
    model_used: str = "qwen-max"
    is_agent: bool = True


# ---------------------------------------------------------------------------
# 校验函数
# ---------------------------------------------------------------------------

def validate_prediction(data: PredictionInput) -> ValidationResult:
    """对 Qwen 返回的原始预测数据执行完整校验与清洗。

    按照 winner → confidence → key_factors → reasoning_chain →
    tool_calls_log → predicted_score 的顺序依次校验，最后汇总结果。

    Args:
        data: 来自 Qwen 的原始预测数据。

    Returns:
        包含校验状态、错误/警告列表以及清洗后数据的 ValidationResult。
    """
    try:
        errors: list[str] = []
        warnings: list[str] = []

        # ---- 中间变量 ----
        cleaned_winner: str = ""
        cleaned_confidence: float = 0.5
        cleaned_key_factors: list[str] = []
        cleaned_reasoning: list[ReasoningStep] = []
        cleaned_tool_calls: list[ToolCallRecord] = []
        cleaned_score: str = ""

        # ---------------------------------------------------------------
        # 1. winner 校验
        # ---------------------------------------------------------------
        raw_winner = data.winner
        if raw_winner is None or raw_winner.strip() == "":
            errors.append("winner 不能为空")
        elif raw_winner.strip().lower() == "draw":
            cleaned_winner = "draw"
        else:
            lookup_key = raw_winner.strip().lower()
            if lookup_key in _TEAM_NAME_LOOKUP:
                cleaned_winner = _TEAM_NAME_LOOKUP[lookup_key]
            else:
                errors.append(f"未知的球队名称: {raw_winner}")

        # ---------------------------------------------------------------
        # 2. confidence 校验
        # ---------------------------------------------------------------
        raw_confidence = data.confidence
        if raw_confidence is None:
            cleaned_confidence = 0.5
            warnings.append("confidence 缺失，使用默认值 0.5")
        elif raw_confidence < 0:
            warnings.append(f"confidence {raw_confidence} 超出范围，已修正为 0.0")
            cleaned_confidence = 0.0
        elif raw_confidence > 1:
            warnings.append(f"confidence {raw_confidence} 超出范围，已修正为 1.0")
            cleaned_confidence = 1.0
        else:
            cleaned_confidence = raw_confidence

        # ---------------------------------------------------------------
        # 3. key_factors 校验
        # ---------------------------------------------------------------
        raw_factors = data.key_factors
        if raw_factors is None or len(raw_factors) == 0:
            errors.append("key_factors 不能为空")
        else:
            filtered = [
                f for f in raw_factors
                if isinstance(f, str) and f.strip() != "" and len(f.strip()) >= 5
            ]
            if len(filtered) == 0:
                errors.append("key_factors 不能为空")
            else:
                if filtered != raw_factors:
                    warnings.append("已过滤无效的关键因素")
                if len(filtered) > 10:
                    filtered = filtered[:10]
                    warnings.append("key_factors 超过 10 条，已截断")
                cleaned_key_factors = filtered

        # ---------------------------------------------------------------
        # 4. reasoning_chain 校验
        # ---------------------------------------------------------------
        raw_chain = data.reasoning_chain
        if raw_chain is None or len(raw_chain) == 0:
            errors.append("reasoning_chain 不能为空")
        else:
            for item in raw_chain:
                try:
                    step_num = item.get("step_number") or item.get("step")
                    if step_num is None:
                        warnings.append("reasoning_chain 中某项缺少 step_number，已跳过")
                        continue
                    finding = item.get("finding")
                    if not finding or (isinstance(finding, str) and finding.strip() == ""):
                        warnings.append("reasoning_chain 中某项缺少 finding，已跳过")
                        continue
                    step = ReasoningStep(
                        step_number=int(step_num),
                        tool_used=item.get("tool_used"),
                        finding=str(finding),
                        analysis=item.get("analysis"),
                    )
                    cleaned_reasoning.append(step)
                except Exception:
                    warnings.append("reasoning_chain 中某项解析失败，已跳过")

            if len(cleaned_reasoning) == 0:
                errors.append("reasoning_chain 不能为空")

        # ---------------------------------------------------------------
        # 5. tool_calls_log 校验
        # ---------------------------------------------------------------
        raw_tools = data.tool_calls_log
        if raw_tools is not None:
            for item in raw_tools:
                try:
                    tool_name = item.get("tool_name") or item.get("name")
                    if tool_name is None:
                        warnings.append("tool_calls_log 中某项缺少 tool_name，已跳过")
                        continue
                    record = ToolCallRecord(
                        tool_name=str(tool_name),
                        input_params=item.get("input_params", {}),
                        output_summary=item.get("output_summary", ""),
                        execution_time_ms=item.get("execution_time_ms", 0),
                        success=item.get("success", True),
                    )
                    cleaned_tool_calls.append(record)
                except Exception:
                    warnings.append("tool_calls_log 中某项解析失败，已跳过")

        # ---------------------------------------------------------------
        # 6. predicted_score 校验
        # ---------------------------------------------------------------
        raw_score = data.predicted_score
        if raw_score is None or raw_score.strip() == "":
            cleaned_score = ""
            warnings.append("predicted_score 缺失")
        elif "-" not in raw_score:
            cleaned_score = raw_score
            warnings.append(f"predicted_score 格式异常: {raw_score}")
        else:
            cleaned_score = raw_score

        # ---------------------------------------------------------------
        # 汇总结果
        # ---------------------------------------------------------------
        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                cleaned_data=None,
            )

        cleaned_data = ValidatedPrediction(
            winner=cleaned_winner,
            predicted_score=cleaned_score,
            confidence=cleaned_confidence,
            key_factors=cleaned_key_factors,
            reasoning_chain=cleaned_reasoning,
            tool_calls_log=cleaned_tool_calls,
        )

        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
            cleaned_data=cleaned_data,
        )

    except Exception as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"校验过程发生异常: {exc}"],
            warnings=[],
            cleaned_data=None,
        )
