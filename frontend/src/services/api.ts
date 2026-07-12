const BASE_URL = "/api/v1";

async function throwAPIError(res: Response): Promise<never> {
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    // The server may return an empty or non-JSON error response.
  }
  throw new Error(detail || `API error: ${res.status}`);
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`);
  if (!res.ok) return throwAPIError(res);
  return res.json();
}

async function postJSON<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) return throwAPIError(res);
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
  predictMatch: (homeTeam: import("../types").Team, awayTeam: import("../types").Team) =>
    postJSON<import("../types").MatchPredictionResponse>("/predictions/match", {
      home_team_id: homeTeam.id,
      away_team_id: awayTeam.id,
      home_team_code: homeTeam.fifa_code,
      away_team_code: awayTeam.fifa_code,
    }),
  recalculate: () => postJSON<{ status: string }>("/predictions/recalculate"),

  // Bracket
  getBracket: () =>
    fetchJSON<import("../types").BracketResponse>("/bracket"),
  getBracketTeamPath: (teamId: number) =>
    fetchJSON<import("../types").TeamBracketPath>(`/bracket/team/${teamId}`),
  getSimulation: (params?: { event_ids?: string; refresh?: boolean }) => {
    const p = new URLSearchParams();
    if (params?.event_ids) p.set("event_ids", params.event_ids);
    if (params?.refresh) p.set("refresh", "true");
    return fetchJSON<import("../types").SimulationResult>(`/bracket/simulation?${p}`);
  },

  // Events
  getEvents: () => fetchJSON<import("../types").Event[]>("/events"),
  createEvent: (data: import("../types").EventCreate) =>
    postJSON<import("../types").Event>("/events", data),
  updateEvent: (id: number, data: import("../types").EventUpdate) =>
    putJSON<import("../types").Event>(`/events/${id}`, data),
  deleteEvent: (id: number) =>
    deleteJSON<{ deleted: boolean }>(`/events/${id}`),
  getEventTypes: () => fetchJSON<{ types: Record<string,string>; severities: Record<string,string> }>("/events/types"),
};

async function putJSON<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) return throwAPIError(res);
  return res.json();
}

async function deleteJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, { method: "DELETE" });
  if (!res.ok) return throwAPIError(res);
  return res.json();
}

// ── 具名导出（供 hooks 直接 import）─────────────────────
export const fetchBracket = api.getBracket;
export { postJSON, fetchJSON };
