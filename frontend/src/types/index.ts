export interface Team {
  id: number;
  name: string;
  name_cn: string;
  fifa_code: string;
  confederation: string;
  fifa_ranking: number | null;
  elo_rating: number | null;
  group_name: string | null;
  pot: number | null;
  stats: TeamStats | null;
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
  prediction?: AgentPrediction | null;
}

export interface AgentPrediction {
  id: number;
  match_id: number;
  winner: string | null;
  predicted_score: string | null;
  confidence: number | null;
  key_factors: string[] | null;
  reasoning_chain: ReasoningStep[] | null;
  is_agent: boolean;
  model_used: string | null;
  tool_calls_log?: ToolCallRecord[] | null;
  created_at?: string | null;
}

export interface ToolCallRecord {
  tool_name: string;
  input_params: Record<string, unknown>;
  output_summary: string;
  execution_time_ms: number;
  success: boolean;
}

export interface ReasoningStep {
  step: number;
  tool?: string;
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
  active: boolean;
  created_at?: string | null;
  team_name?: string;
  fifa_code?: string;
  type_label?: string;
  severity_label?: string;
}

export interface EventCreate {
  team_id: number;
  type: string;
  title: string;
  description?: string;
  severity?: string;
  impact?: Record<string, number>;
  source?: string;
}

export interface EventUpdate {
  title?: string;
  description?: string;
  severity?: string;
  impact?: Record<string, number>;
  active?: boolean;
}

export interface BracketNode {
  match: Match;
  prediction: AgentPrediction | null;
  left: BracketNode | null;
  right: BracketNode | null;
  depth: number;
  children?: [BracketNode, BracketNode] | null;
}

export interface ChampionPrediction {
  team: Team;
  probability: number;
  key_factors: string[];
}

export interface SimulationResult {
  champion_probs: Record<string, number>;
  top3: [string, number][];
  most_likely_path?: BracketNode | null;
  iterations: number;
}

/* ── API Response types ── */

/** POST /predictions/match 响应 */
export interface MatchPredictionResponse {
  home_team: string;
  away_team: string;
  is_valid: boolean;
  is_agent: boolean;
  model_used: string;
  errors: string[];
  warnings: string[];
  prediction: ValidatedPredictionData | null;
  circuit_breaker: Record<string, unknown>;
}

export interface ValidatedPredictionData {
  winner: string;
  predicted_score: string;
  confidence: number;
  key_factors: string[];
  reasoning_chain: ReasoningStep[];
  tool_calls_log: ToolCallRecord[];
}

/** GET /bracket 响应 */
export interface BracketResponse {
  stages: Record<string, BracketStage>;
  total_matches: number;
}

export interface BracketStage {
  label: string;
  matches: Match[];
}

/** GET /bracket/team/{id} 响应 */
export interface TeamBracketPath {
  team: Team;
  knockout_path: KnockoutStep[];
}

export interface KnockoutStep {
  stage: string;
  round_name: string;
  opponent: Team | null;
  result: "W" | "L" | "D" | null;
  score: string | null;
  match_id: number;
}
