import {
  ApiError,
  HealthResponse,
  RunDetail,
  RunSummary,
} from "@/lib/types";

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  }
  return "";
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || response.statusText, response.status);
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/health");
}

export async function listRuns(): Promise<RunSummary[]> {
  return fetchJson<RunSummary[]>("/api/runs");
}

export async function getRun(date: string): Promise<RunDetail> {
  return fetchJson<RunDetail>(`/api/runs/${date}`);
}
