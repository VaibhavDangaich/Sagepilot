import type {
  CreateRunRequest,
  CreateSupervisorRequest,
  RunDetail,
  RunSummary,
  SupervisorConfig,
  TimelineEntry,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${res.status}): ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listSupervisors: () => request<SupervisorConfig[]>("/api/supervisors"),
  getSupervisor: (id: string) => request<SupervisorConfig>(`/api/supervisors/${id}`),
  createSupervisor: (body: CreateSupervisorRequest) =>
    request<SupervisorConfig>("/api/supervisors", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listRuns: () => request<RunSummary[]>("/api/runs"),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  createRun: (body: CreateRunRequest) =>
    request<RunSummary>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  getTimeline: (runId: string) => request<TimelineEntry[]>(`/api/runs/${runId}/timeline`),
  getMemory: (runId: string) =>
    request<{ memory_summary: string; wake_policy: string }>(`/api/runs/${runId}/memory`),

  injectEvent: (runId: string, eventType: string, data: Record<string, string> = {}) =>
    request<{ status: string }>(`/api/runs/${runId}/events`, {
      method: "POST",
      body: JSON.stringify({ event: { event_type: eventType, data } }),
    }),
  addInstruction: (runId: string, instruction: string) =>
    request<{ status: string }>(`/api/runs/${runId}/instructions`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  interruptRun: (runId: string) =>
    request<{ status: string }>(`/api/runs/${runId}/interrupt`, { method: "POST" }),
  resumeRun: (runId: string) =>
    request<{ status: string }>(`/api/runs/${runId}/resume`, { method: "POST" }),
  terminateRun: (runId: string) =>
    request<{ status: string }>(`/api/runs/${runId}/terminate`, { method: "POST" }),
};
