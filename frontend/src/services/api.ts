const BASE_URL = "/api/v1";

export interface SimulationParams {
  event_ids?: number[] | string;
  baseline_simulation_id?: string;
  iterations?: number;
  seed?: number;
  refresh?: boolean;
}

export const simulationQueryKeys = {
  baseline: ["simulation", "baseline"] as const,
  scenario: (baselineSimulationId: string, eventIds: number[]) => [
    "simulation",
    "scenario",
    baselineSimulationId,
    [...eventIds].sort((a, b) => a - b).join(","),
  ] as const,
};

async function throwAPIError(res: Response): Promise<never> {
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    // The server may return an empty or non-JSON error response.
  }
  throw new Error(detail || `请求失败，状态码：${res.status}`);
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
  predictMatch: (simulationId: string, matchKey: string) =>
    postJSON<import("../types").MatchPredictionResponse>("/predictions/match", {
      simulation_id: simulationId,
      match_key: matchKey,
    }),
  getTournamentReport: (simulationId: string) =>
    postJSON<import("../types").TournamentReportResponse>("/predictions/tournament-report", {
      simulation_id: simulationId,
    }),
  // Simulation
  getSimulation: (params?: SimulationParams) => {
    const p = new URLSearchParams();
    if (params?.event_ids) {
      const eventIds = Array.isArray(params.event_ids)
        ? params.event_ids.join(",")
        : params.event_ids;
      if (eventIds) p.set("event_ids", eventIds);
    }
    if (params?.baseline_simulation_id) {
      p.set("baseline_simulation_id", params.baseline_simulation_id);
    }
    if (params?.iterations != null) p.set("iterations", String(params.iterations));
    if (params?.seed != null) p.set("seed", String(params.seed));
    if (params?.refresh) p.set("refresh", "true");
    const suffix = p.size ? `?${p}` : "";
    return fetchJSON<import("../types").SimulationResult>(`/bracket/simulation${suffix}`);
  },

  // Events
  getEvents: (params?: { active_only?: boolean; current_only?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.active_only) search.set("active_only", "true");
    if (params?.current_only) search.set("current_only", "true");
    const suffix = search.size ? `?${search}` : "";
    return fetchJSON<import("../types").Event[]>(`/events${suffix}`);
  },
  createEvent: (data: import("../types").EventCreate) =>
    postJSON<import("../types").Event>("/events", data),
  updateEvent: (id: number, data: import("../types").EventUpdate) =>
    putJSON<import("../types").Event>(`/events/${id}`, data),
  deleteEvent: (id: number) =>
    deleteJSON<{ deleted: boolean }>(`/events/${id}`),
  getEventTypes: () => fetchJSON<import("../types").EventMetadata>("/events/types"),
  importEvents: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/events/import`, { method: "POST", body: form });
    if (!res.ok) return throwAPIError(res);
    return res.json() as Promise<import("../types").EventImportResult>;
  },
  eventImportTemplateUrl: `${BASE_URL}/events/import/template`,
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

export { postJSON, fetchJSON };
