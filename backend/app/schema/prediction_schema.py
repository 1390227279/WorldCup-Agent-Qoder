"""Contracts for deterministic match mathematics and optional AI explanations."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schema.simulation_schema import (
    AppliedScenarioEvent,
    NarrativeScenarioEvent,
    SimulationTeam,
)


class ToolCallRecord(BaseModel):
    tool_name: str
    input_params: dict = Field(default_factory=dict)
    output_summary: str = ""
    execution_time_ms: int = Field(default=0, ge=0)
    success: bool = True


class ReasoningStep(BaseModel):
    step_number: int = Field(ge=1)
    tool_used: Optional[str] = None
    finding: str
    analysis: Optional[str] = None


class AgentReportInput(BaseModel):
    key_factors: Optional[list[str]] = None
    risk_notes: Optional[list[str]] = None
    reasoning_chain: Optional[list[dict]] = None
    tool_calls_log: Optional[list[dict]] = None


class ValidatedAgentReport(BaseModel):
    key_factors: list[str] = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    tool_calls_log: list[ToolCallRecord] = Field(default_factory=list)


class AgentReportValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cleaned_data: Optional[ValidatedAgentReport] = None


class MatchOutcomeProbabilities(BaseModel):
    home_win: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away_win: float = Field(ge=0.0, le=1.0)
    home_advance: float = Field(ge=0.0, le=1.0)
    away_advance: float = Field(ge=0.0, le=1.0)


class MatchMathContext(BaseModel):
    simulation_id: str
    match_key: str
    scenario_type: Literal["BASELINE", "EVENT"]
    stage: str
    round_name: str
    home_team: SimulationTeam
    away_team: SimulationTeam
    predicted_score: str
    winner_team_id: int
    winner: str
    decided_by: Literal["REGULAR_TIME", "PENALTIES"]
    home_lambda: float = Field(gt=0.0)
    away_lambda: float = Field(gt=0.0)
    probabilities: MatchOutcomeProbabilities
    math_events: list[AppliedScenarioEvent]
    narrative_events: list[NarrativeScenarioEvent]


class MatchAgentAnalysis(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: Literal["available", "agent_unavailable"]
    model_used: Optional[str] = None
    message: Optional[str] = None
    key_factors: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    tool_calls_log: list[ToolCallRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SimulatedMatchAnalysisRequest(BaseModel):
    simulation_id: str = Field(min_length=1)
    match_key: str = Field(min_length=1)


class SimulatedMatchAnalysisResponse(BaseModel):
    simulation_id: str
    match_key: str
    math: MatchMathContext
    agent: MatchAgentAnalysis
    circuit_breaker: dict


class TournamentReportRequest(BaseModel):
    simulation_id: str = Field(min_length=1)


class TournamentMathSummary(BaseModel):
    simulation_id: str
    tournament_code: str
    tournament_name: str
    tournament_year: int
    scenario_type: Literal["BASELINE", "EVENT"]
    scenario_label: str
    champion: SimulationTeam
    final_score: str
    finalist: SimulationTeam
    probability_leader: SimulationTeam
    probability_leader_probability: float = Field(ge=0.0, le=1.0)
    top3: list[dict]
    group_qualifiers: list[dict]
    knockout_path: list[dict]
    math_events: list[AppliedScenarioEvent]
    narrative_events: list[NarrativeScenarioEvent]


class TournamentAgentReport(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: Literal["available", "agent_unavailable"]
    model_used: Optional[str] = None
    message: Optional[str] = None
    champion_summary: str = ""
    group_stage_reasoning: list[str] = Field(default_factory=list)
    knockout_reasoning: list[str] = Field(default_factory=list)
    final_reasoning: str = ""
    key_factors: list[str] = Field(default_factory=list)
    event_analysis: list[str] = Field(default_factory=list)
    alternative_outcomes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)


class TournamentReportResponse(BaseModel):
    simulation_id: str
    math: TournamentMathSummary
    agent: TournamentAgentReport
    circuit_breaker: dict


def validate_agent_report(data: AgentReportInput) -> AgentReportValidationResult:
    """Clean an explanation report and force continuous 1-based steps."""
    errors: list[str] = []
    warnings: list[str] = []
    key_factors = [
        factor.strip()
        for factor in (data.key_factors or [])
        if isinstance(factor, str) and len(factor.strip()) >= 5
    ][:10]
    if not key_factors:
        errors.append("key_factors 不能为空")
    risk_notes = [
        note.strip()
        for note in (data.risk_notes or [])
        if isinstance(note, str) and note.strip()
    ][:10]
    reasoning_chain: list[ReasoningStep] = []
    for item in data.reasoning_chain or []:
        if not isinstance(item, dict):
            warnings.append("reasoning_chain 中存在无效条目，已跳过")
            continue
        finding = item.get("finding")
        if not isinstance(finding, str) or not finding.strip():
            warnings.append("reasoning_chain 中某项缺少 finding，已跳过")
            continue
        reasoning_chain.append(ReasoningStep(
            step_number=len(reasoning_chain) + 1,
            tool_used=item.get("tool_used"),
            finding=finding.strip(),
            analysis=item.get("analysis"),
        ))
    if not reasoning_chain:
        errors.append("reasoning_chain 不能为空")
    tool_calls: list[ToolCallRecord] = []
    for item in data.tool_calls_log or []:
        try:
            tool_calls.append(ToolCallRecord.model_validate(item))
        except Exception:
            warnings.append("tool_calls_log 中存在无效条目，已跳过")
    if errors:
        return AgentReportValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
        )
    return AgentReportValidationResult(
        is_valid=True,
        warnings=warnings,
        cleaned_data=ValidatedAgentReport(
            key_factors=key_factors,
            risk_notes=risk_notes,
            reasoning_chain=reasoning_chain,
            tool_calls_log=tool_calls,
        ),
    )
