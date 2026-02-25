import {
  AlertDetail,
  AlertsListResponse,
  AuditListResponse,
  HealthResponse,
  MonitoringUniverseSummary,
  RunSummary
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `API error (${res.status} ${res.statusText}): ${text || "Unknown error"}`
    );
  }
  return res.json();
}

export async function runOperator(): Promise<RunSummary> {
  try {
    const res = await fetch(`${API_BASE}/operator/run`, {
      method: "POST"
    });
    return handle<RunSummary>(res);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : typeof err === "string" ? err : String(err);

    if (message.toLowerCase().includes("fetch") || message.toLowerCase().includes("network")) {
      throw new Error(
        `Failed to reach operator backend at ${API_BASE}/operator/run. Is the FastAPI server running on ${API_BASE}?`
      );
    }

    throw err instanceof Error ? err : new Error(message);
  }
}

export async function fetchAlerts(
  params?: URLSearchParams
): Promise<AlertsListResponse> {
  const url = new URL(`${API_BASE}/alerts`);
  if (params) {
    url.search = params.toString();
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  return handle<AlertsListResponse>(res);
}

export async function fetchAlert(id: number): Promise<AlertDetail> {
  const res = await fetch(`${API_BASE}/alerts/${id}`, { cache: "no-store" });
  return handle<AlertDetail>(res);
}

export async function postAlertAction(
  id: number,
  action: "reviewed" | "escalate" | "false_positive"
): Promise<{ alert: AlertDetail; message: string }> {
  const res = await fetch(`${API_BASE}/alerts/${id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action })
  });
  return handle<{ alert: AlertDetail; message: string }>(res);
}

export async function fetchAuditLog(
  params?: URLSearchParams
): Promise<AuditListResponse> {
  const url = new URL(`${API_BASE}/audit`);
  if (params) {
    url.search = params.toString();
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  return handle<AuditListResponse>(res);
}

export async function fetchMonitoringSummary(): Promise<MonitoringUniverseSummary> {
  const res = await fetch(`${API_BASE}/portfolios/summary`, {
    cache: "no-store"
  });
  return handle<MonitoringUniverseSummary>(res);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return handle<HealthResponse>(res);
}

