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
  most_likely_path: BracketNode | null;
  iterations: number;
}
