export interface Team {
  id: number;
  name: string;
  name_cn: string;
  fifa_code: string;
  confederation: string;
  fifa_ranking: number | null;
  elo_rating: number | null;
  stats: TeamStats | null;
  tournament?: {
    id: number;
    code: string;
    name: string;
    name_cn: string;
    year: number;
    status: string;
    data_version: string;
    group_name: string | null;
    pot: number | null;
    qualification_status: string;
  };
}

export interface TeamStats {
  world_cup_titles: number;
  best_result: string;
  appearances: number;
}

export interface Match {
  id: number;
  stage: string;
  round_name: string | null;
  home_team: Team | null;
  away_team: Team | null;
  home_score: number | null;
  away_score: number | null;
  is_simulated: boolean;
  match_order?: number | null;
  match_key?: string;
  winner_team_id?: number | null;
  winner?: string;
  source_slots?: string[];
  decided_by?: "REGULAR_TIME" | "PENALTIES";
}

export interface ToolCallRecord {
  tool_name: string;
  input_params: Record<string, unknown>;
  output_summary: string;
  execution_time_ms: number;
  success: boolean;
}

export interface ReasoningStep {
  step_number: number;
  tool_used?: string | null;
  finding?: string;
  analysis?: string;
  conclusion?: string;
}

export interface Event {
  id: number;
  team_id: number;
  type: string;
  title: string;
  description: string | null;
  severity: string;
  impact: Record<string, number> | null;
  source: string | null;
  source_type?: string;
  source_url?: string | null;
  external_id?: string | null;
  effective_at?: string | null;
  expires_at?: string | null;
  active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  team_name?: string;
  fifa_code?: string;
  type_label?: string;
  severity_label?: string;
  status?: "ACTIVE" | "SCHEDULED" | "EXPIRED" | "INACTIVE";
  status_label?: string;
  legacy_impact_fields?: string[];
  needs_impact_migration?: boolean;
  impact_mode: "MATH" | "NARRATIVE" | "INVALID";
  affects_probability: boolean;
  tournament?: {
    id: number;
    code: string;
    name: string;
    name_cn: string;
    year: number;
  } | null;
}

export interface EventCreate {
  team_id: number;
  type: string;
  title: string;
  description?: string;
  severity?: string;
  impact?: Record<string, number>;
  impact_mode?: "MATH" | "NARRATIVE";
  source?: string;
  source_type?: string;
  source_url?: string;
  external_id?: string;
  effective_at?: string;
  expires_at?: string;
}

export interface EventUpdate {
  team_id?: number;
  type?: string;
  title?: string;
  description?: string | null;
  severity?: string;
  impact?: Record<string, number> | null;
  impact_mode?: "MATH" | "NARRATIVE";
  active?: boolean;
  source?: string | null;
  source_type?: string | null;
  source_url?: string | null;
  external_id?: string | null;
  effective_at?: string | null;
  expires_at?: string | null;
}

export interface EventImportResult {
  filename: string;
  total: number;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

export interface EventMetadata {
  types: Record<string, string>;
  severities: Record<string, string>;
  impact_fields: Record<string, string>;
  impact_range: { min: number; max: number };
  impact_modes: Record<"MATH" | "NARRATIVE", string>;
}

export interface SimulationProbabilityEntry {
  team: Team;
  probability: number;
}

export interface AdvancementProbability {
  team_id: number;
  team: Team;
  R32: number;
  R16: number;
  QF: number;
  SF: number;
  FINAL: number;
  CHAMPION: number;
}

export interface SimulationSummary {
  probability_leader: SimulationProbabilityEntry;
  top3: SimulationProbabilityEntry[];
  advancement_probs: Record<number, AdvancementProbability>;
  champion_probs_by_team_id: Record<number, number>;
}

export interface SimulationScenario {
  type: "BASELINE" | "EVENT";
  label: string;
  requested_event_ids: number[];
  math_events: Array<{
    event_id: number;
    team_id: number;
    team_code: string;
    title: string;
    impact: Record<string, number>;
  }>;
  narrative_events: Array<{
    event_id: number;
    team_id: number;
    team_code: string;
    type: string;
    severity: string;
    title: string;
    description: string | null;
    impact: Record<string, unknown>;
  }>;
  ignored_events: Array<{
    event_id: number;
    reason: string;
  }>;
  team_impacts: Record<string, Record<string, number>>;
  team_math_event_ids: Record<string, number[]>;
  team_narrative_event_ids: Record<string, number[]>;
  event_content_fingerprint: string;
}

export interface SimulationTournament {
  id: number;
  code: string;
  name: string;
  name_cn: string;
  year: number;
  status: string;
  data_version: string;
  rules_version: string;
  is_official: boolean;
}

export interface SimulationModel {
  version: string;
  iterations: number;
  seed: number;
  input_fingerprint: string;
}

export interface RepresentativePath {
  path_type: string;
  champion: Team;
  iteration_index: number;
  iteration_seed: number;
  log_likelihood: number;
  group_stage: Record<string, GroupStageGroup>;
  stages: Record<string, BracketStage>;
}

export interface GroupStageMatch extends Match {
  stage: "GROUP";
  group_name: string;
  home_team: Team;
  away_team: Team;
  home_score: number;
  away_score: number;
  winner_team_id: number | null;
  match_key: string;
  match_order: number;
}

export interface GroupStandingRow {
  position: number;
  team_id: number;
  team: Team;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  qualified: boolean;
  qualification_type: "GROUP_WINNER" | "RUNNER_UP" | "BEST_THIRD" | null;
}

export interface GroupStageGroup {
  label: string;
  matches: GroupStageMatch[];
  standings: GroupStandingRow[];
}

export interface SimulationResult {
  simulation_id: string;
  baseline_simulation_id: string;
  tournament: SimulationTournament;
  model: SimulationModel;
  scenario: SimulationScenario;
  summary: SimulationSummary;
  representative_path: RepresentativePath;
}

/* ── API Response types ── */

/** POST /predictions/match 响应 */
export interface MatchPredictionResponse {
  simulation_id: string;
  match_key: string;
  math: MatchMathContext;
  agent: MatchAgentAnalysis;
  circuit_breaker: Record<string, unknown>;
}

export interface MatchOutcomeProbabilities {
  home_win: number;
  draw: number;
  away_win: number;
  home_advance: number;
  away_advance: number;
}

export interface MatchMathContext {
  simulation_id: string;
  match_key: string;
  scenario_type: "BASELINE" | "EVENT";
  stage: string;
  round_name: string;
  home_team: Team;
  away_team: Team;
  predicted_score: string;
  winner_team_id: number;
  winner: string;
  decided_by: "REGULAR_TIME" | "PENALTIES";
  home_lambda: number;
  away_lambda: number;
  probabilities: MatchOutcomeProbabilities;
  math_events: Array<{
    event_id: number;
    team_id: number;
    team_code: string;
    title: string;
    impact: Record<string, number>;
  }>;
  narrative_events: Array<{
    event_id: number;
    team_id: number;
    team_code: string;
    type: string;
    severity: string;
    title: string;
    description: string | null;
    impact: Record<string, unknown>;
  }>;
}

export interface MatchAgentAnalysis {
  status: "available" | "agent_unavailable";
  model_used: string | null;
  message: string | null;
  key_factors: string[];
  risk_notes: string[];
  reasoning_chain: ReasoningStep[];
  tool_calls_log: ToolCallRecord[];
  warnings: string[];
}

export interface BracketStage {
  label: string;
  matches: Match[];
}
