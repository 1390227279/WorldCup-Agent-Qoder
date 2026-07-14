"""Pydantic contract for baseline and event-scenario simulations."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class SimulationTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    name_cn: str
    fifa_code: str
    confederation: str | None = None
    fifa_ranking: int | None = None
    elo_rating: float
    stats: dict[str, Any] | None = None


class SimulationMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    match_key: str
    stage: str
    round_name: str
    home_team: SimulationTeam
    away_team: SimulationTeam
    home_score: int
    away_score: int
    winner_team_id: int
    winner: str
    source_slots: list[str]
    decided_by: Literal["REGULAR_TIME", "PENALTIES"]
    is_simulated: bool
    match_order: int


class SimulationStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    matches: list[SimulationMatch]


class AdvancementProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: int
    team: SimulationTeam
    R32: float
    R16: float
    QF: float
    SF: float
    FINAL: float
    CHAMPION: float


class ProbabilityTeamEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: SimulationTeam
    probability: float


class SimulationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability_leader: ProbabilityTeamEntry
    top3: list[ProbabilityTeamEntry]
    advancement_probs: dict[int, AdvancementProbability]
    champion_probs_by_team_id: dict[int, float]


class AppliedScenarioEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    team_id: int
    team_code: str
    title: str
    impact: dict[str, float]


class IgnoredScenarioEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    reason: str


class ScenarioInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["BASELINE", "EVENT"]
    label: str
    requested_event_ids: list[int]
    applied_events: list[AppliedScenarioEvent]
    ignored_events: list[IgnoredScenarioEvent]
    team_impacts: dict[str, dict[str, float]]
    team_event_ids: dict[str, list[int]]
    event_content_fingerprint: str


class TournamentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    name_cn: str
    year: int
    status: str
    data_version: str
    rules_version: str
    is_official: bool


class SimulationModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    iterations: int
    seed: int
    input_fingerprint: str


class RepresentativePath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_type: str
    champion: SimulationTeam
    iteration_index: int
    iteration_seed: int
    log_likelihood: float
    stages: dict[str, SimulationStage]


class SimulationResponse(BaseModel):
    """Canonical baseline or event-scenario response."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    simulation_id: str
    baseline_simulation_id: str
    scenario: ScenarioInfo
    tournament: TournamentInfo
    model: SimulationModelInfo
    summary: SimulationSummary
    representative_path: RepresentativePath
