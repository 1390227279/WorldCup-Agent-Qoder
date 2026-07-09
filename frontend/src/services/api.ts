const BASE_URL = "/api/v1";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`);
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
  recalculate: () =>
    fetchJSON<{ status: string }>("/predictions/recalculate", {
      method: "POST",
    } as unknown as string),

  // Bracket
  getBracket: () =>
    fetchJSON<import("../types").BracketNode>("/bracket"),
  getSimulation: () =>
    fetchJSON<import("../types").SimulationResult>("/bracket/simulation"),

  // Events
  getEvents: () => fetchJSON<import("../types").Event[]>("/events"),
};

async function fetchJSONWithMethod<T>(
  url: string,
  method: string,
  body?: unknown
): Promise<T> {
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);
  const res = await fetch(`${BASE_URL}${url}`, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
