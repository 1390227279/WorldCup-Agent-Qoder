const BASE_URL = "/api/v1";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postJSON<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  // Teams
  getTeams: () => fetchJSON<import("../types").Team[]>("/teams"),
  getTeam: (id: number) =>
    fetchJSON<import("../types").Team & { events: import("../types").Event[] }>(
      `/teams/${id}`
    ),

  // Predictions
  getChampion: () =>
    fetchJSON<import("../types").ChampionPrediction>("/predictions/champion"),
  getMatchPrediction: (id: number) =>
    fetchJSON<import("../types").AgentPrediction>(`/predictions/match/${id}`),
  predictMatch: (homeTeamId: number, awayTeamId: number) =>
    postJSON<import("../types").MatchPredictionResponse>("/predictions/match", {
      home_team_id: homeTeamId,
      away_team_id: awayTeamId,
    }),
  recalculate: () => postJSON<{ status: string }>("/predictions/recalculate"),

  // Bracket
  getBracket: () =>
    fetchJSON<import("../types").BracketResponse>("/bracket"),
  getBracketTeamPath: (teamId: number) =>
    fetchJSON<import("../types").TeamBracketPath>(`/bracket/team/${teamId}`),
  getSimulation: () =>
    fetchJSON<import("../types").SimulationResult>("/bracket/simulation"),

  // Events
  getEvents: () => fetchJSON<import("../types").Event[]>("/events"),
};

// ── 具名导出（供 hooks 直接 import）─────────────────────
export const fetchBracket = api.getBracket;
export { postJSON };
