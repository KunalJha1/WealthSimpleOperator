import {
  AlertDetail,
  FollowUpDraft,
  AlertsListResponse,
  AuditListResponse,
  HealthResponse,
  MonitoringUniverseSummary,
  MonitoringUniverseDetail,
  RunSummary,
  SimulationScenario,
  SimulationSeverity,
  SimulationSummary,
  MeetingNote,
  MeetingNotesListResponse,
  SummarizeTranscriptResponse,
  MeetingNoteCreate,
  RebalancingSuggestion,
  ReallocationPlan,
  PlaybookSummary,
  ContactScheduleResponse,
  TaxLossResponse,
  RiskDashboardResponse
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

export async function runOperator(options?: {
  force?: boolean;
  maxAgeSeconds?: number;
}): Promise<RunSummary> {
  try {
    const url = new URL(`${API_BASE}/operator/run`);
    if (options?.force) {
      url.searchParams.set("force", "true");
    }
    if (typeof options?.maxAgeSeconds === "number") {
      url.searchParams.set("max_age_seconds", String(options.maxAgeSeconds));
    }

    const res = await fetch(url.toString(), {
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

export async function createFollowUpDraft(
  alertId: number,
  options?: { forceRegenerate?: boolean }
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/follow-up-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_regenerate: Boolean(options?.forceRegenerate) })
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function fetchFollowUpDraft(
  alertId: number
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/follow-up-draft`, {
    cache: "no-store"
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function approveFollowUpDraft(
  draftId: number
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(`${API_BASE}/alerts/follow-up-drafts/${draftId}/approve`, {
    method: "POST"
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function rejectFollowUpDraft(
  draftId: number,
  reason?: string
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(`${API_BASE}/alerts/follow-up-drafts/${draftId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason ?? "" })
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
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

export async function fetchMonitoringDetail(): Promise<MonitoringUniverseDetail> {
  const res = await fetch(`${API_BASE}/portfolios/monitoring-detail`, {
    cache: "no-store"
  });
  return handle<MonitoringUniverseDetail>(res);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return handle<HealthResponse>(res);
}

export async function runSimulation(input: {
  scenario: SimulationScenario;
  severity: SimulationSeverity;
}): Promise<SimulationSummary> {
  try {
    const res = await fetch(`${API_BASE}/simulations/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    return handle<SimulationSummary>(res);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : typeof err === "string" ? err : String(err);

    if (message.toLowerCase().includes("fetch") || message.toLowerCase().includes("network")) {
      throw new Error(
        `Failed to reach operator backend at ${API_BASE}/simulations/run. Is the FastAPI server running on ${API_BASE}?`
      );
    }

    throw err instanceof Error ? err : new Error(message);
  }
}

export async function fetchMeetingNotes(
  clientId: number,
  params?: { limit?: number; offset?: number }
): Promise<MeetingNotesListResponse> {
  const url = new URL(`${API_BASE}/meeting-notes`);
  url.searchParams.set("client_id", String(clientId));
  if (params?.limit) {
    url.searchParams.set("limit", String(params.limit));
  }
  if (params?.offset) {
    url.searchParams.set("offset", String(params.offset));
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  return handle<MeetingNotesListResponse>(res);
}

export async function summarizeTranscript(
  noteId: number,
  options?: { forceRegenerate?: boolean }
): Promise<SummarizeTranscriptResponse> {
  const res = await fetch(`${API_BASE}/meeting-notes/${noteId}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_regenerate: Boolean(options?.forceRegenerate) })
  });
  return handle<SummarizeTranscriptResponse>(res);
}

export async function createMeetingNote(
  clientId: number,
  payload: MeetingNoteCreate
): Promise<MeetingNote> {
  const res = await fetch(`${API_BASE}/meeting-notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, ...payload })
  });
  return handle<MeetingNote>(res);
}

export async function fetchRebalancingSuggestion(
  alertId: number
): Promise<RebalancingSuggestion> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/rebalance-suggestion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store"
  });
  return handle<RebalancingSuggestion>(res);
}

export async function fetchSimulationPlaybook(input: {
  scenario: SimulationScenario;
  severity: SimulationSeverity;
  portfolio_ids: number[];
}): Promise<PlaybookSummary> {
  const res = await fetch(`${API_BASE}/simulations/playbook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store"
  });
  return handle<PlaybookSummary>(res);
}

export async function generateReallocationPlan(
  alertId: number,
  targetCashAmount = 266000
): Promise<ReallocationPlan> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/reallocation-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_cash_amount: targetCashAmount }),
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function queueReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(`${API_BASE}/alerts/reallocation-plans/${planId}/queue`, {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function approveReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(`${API_BASE}/alerts/reallocation-plans/${planId}/approve`, {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function executeReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(`${API_BASE}/alerts/reallocation-plans/${planId}/execute`, {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function fetchContactSchedule(): Promise<ContactScheduleResponse> {
  const res = await fetch(`${API_BASE}/contacts/schedule`, {
    cache: "no-store"
  });
  return handle<ContactScheduleResponse>(res);
}

export async function fetchTaxLossOpportunities(): Promise<TaxLossResponse> {
  const res = await fetch(`${API_BASE}/tax-loss/opportunities`, {
    cache: "no-store"
  });
  return handle<TaxLossResponse>(res);
}

export async function fetchRiskDashboard(): Promise<RiskDashboardResponse> {
  const res = await fetch(`${API_BASE}/risk-dashboard/summary`, {
    cache: "no-store"
  });
  return handle<RiskDashboardResponse>(res);
}
