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
  PreCallBriefResponse,
  MeetingNoteCreate,
  RebalancingSuggestion,
  ReallocationPlan,
  PlaybookSummary,
  ContactScheduleResponse,
  TaxLossResponse,
  RiskDashboardResponse
} from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api").replace(/\/+$/, "");

function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalizedPath}`;
}

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
    const params = new URLSearchParams();
    if (options?.force) {
      params.set("force", "true");
    }
    if (typeof options?.maxAgeSeconds === "number") {
      params.set("max_age_seconds", String(options.maxAgeSeconds));
    }
    const suffix = params.toString();
    const url = suffix ? `${apiUrl("/operator/run")}?${suffix}` : apiUrl("/operator/run");

    const res = await fetch(url, {
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
  const suffix = params?.toString() ?? "";
  const url = suffix ? `${apiUrl("/alerts")}?${suffix}` : apiUrl("/alerts");
  const res = await fetch(url, { cache: "no-store" });
  return handle<AlertsListResponse>(res);
}

export async function fetchAlertsByClient(clientId: number): Promise<AlertsListResponse> {
  // Use new dedicated endpoint with path parameter for better filtering
  const res = await fetch(`${apiUrl(`/alerts/client/${clientId}`)}?limit=5`, { cache: "no-store" });
  // Return empty list if endpoint doesn't exist (404)
  if (!res.ok) {
    return { items: [], total: 0 };
  }
  return handle<AlertsListResponse>(res);
}

export async function fetchAlert(id: number): Promise<AlertDetail> {
  const res = await fetch(apiUrl(`/alerts/${id}`), { cache: "no-store" });
  return handle<AlertDetail>(res);
}

export async function postAlertAction(
  id: number,
  action: "reviewed" | "escalate" | "false_positive"
): Promise<{ alert: AlertDetail; message: string }> {
  const res = await fetch(apiUrl(`/alerts/${id}/action`), {
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
  const res = await fetch(apiUrl(`/alerts/${alertId}/follow-up-draft`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_regenerate: Boolean(options?.forceRegenerate) })
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function fetchFollowUpDraft(
  alertId: number
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(apiUrl(`/alerts/${alertId}/follow-up-draft`), {
    cache: "no-store"
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function approveFollowUpDraft(
  draftId: number
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(apiUrl(`/alerts/follow-up-drafts/${draftId}/approve`), {
    method: "POST"
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function rejectFollowUpDraft(
  draftId: number,
  reason?: string
): Promise<{ draft: FollowUpDraft; message: string }> {
  const res = await fetch(apiUrl(`/alerts/follow-up-drafts/${draftId}/reject`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason ?? "" })
  });
  return handle<{ draft: FollowUpDraft; message: string }>(res);
}

export async function fetchAuditLog(
  params?: URLSearchParams
): Promise<AuditListResponse> {
  const suffix = params?.toString() ?? "";
  const url = suffix ? `${apiUrl("/audit")}?${suffix}` : apiUrl("/audit");
  const res = await fetch(url, { cache: "no-store" });
  return handle<AuditListResponse>(res);
}

export async function fetchMonitoringSummary(): Promise<MonitoringUniverseSummary> {
  const res = await fetch(apiUrl("/portfolios/summary"), {
    cache: "no-store"
  });
  return handle<MonitoringUniverseSummary>(res);
}

export async function fetchMonitoringDetail(): Promise<MonitoringUniverseDetail> {
  const res = await fetch(apiUrl("/portfolios/monitoring-detail"), {
    cache: "no-store"
  });
  return handle<MonitoringUniverseDetail>(res);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(apiUrl("/health"), { cache: "no-store" });
  return handle<HealthResponse>(res);
}

export async function runSimulation(input: {
  scenario: SimulationScenario;
  severity: SimulationSeverity;
}): Promise<SimulationSummary> {
  try {
    const res = await fetch(apiUrl("/simulations/run"), {
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
  options?: { limit?: number; offset?: number }
): Promise<MeetingNotesListResponse> {
  const query = new URLSearchParams();
  query.set("client_id", String(clientId));
  if (options?.limit) {
    query.set("limit", String(options.limit));
  }
  if (options?.offset) {
    query.set("offset", String(options.offset));
  }
  const res = await fetch(`${apiUrl("/meeting-notes")}?${query.toString()}`, { cache: "no-store" });
  return handle<MeetingNotesListResponse>(res);
}

export async function summarizeTranscript(
  noteId: number,
  options?: { forceRegenerate?: boolean }
): Promise<SummarizeTranscriptResponse> {
  const res = await fetch(apiUrl(`/meeting-notes/${noteId}/summarize`), {
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
  const res = await fetch(apiUrl("/meeting-notes"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, ...payload })
  });
  return handle<MeetingNote>(res);
}

export async function fetchPreCallBrief(clientId: number): Promise<PreCallBriefResponse> {
  const res = await fetch(apiUrl("/meeting-notes/pre-call-brief"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId })
  });
  return handle<PreCallBriefResponse>(res);
}

export async function updateActionItem(
  noteId: number,
  index: number,
  completed: boolean
): Promise<{ note: MeetingNote; message: string }> {
  const res = await fetch(apiUrl(`/meeting-notes/${noteId}/action-items`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index, completed })
  });
  return handle<{ note: MeetingNote; message: string }>(res);
}

export async function fetchRebalancingSuggestion(
  alertId: number
): Promise<RebalancingSuggestion> {
  const res = await fetch(apiUrl(`/alerts/${alertId}/rebalance-suggestion`), {
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
  const res = await fetch(apiUrl("/simulations/playbook"), {
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
  const res = await fetch(apiUrl(`/alerts/${alertId}/reallocation-plan`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_cash_amount: targetCashAmount }),
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function queueReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(apiUrl(`/alerts/reallocation-plans/${planId}/queue`), {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function approveReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(apiUrl(`/alerts/reallocation-plans/${planId}/approve`), {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function executeReallocationPlan(planId: number): Promise<ReallocationPlan> {
  const res = await fetch(apiUrl(`/alerts/reallocation-plans/${planId}/execute`), {
    method: "POST",
    cache: "no-store"
  });
  return handle<ReallocationPlan>(res);
}

export async function fetchContactSchedule(): Promise<ContactScheduleResponse> {
  const res = await fetch(apiUrl("/contacts/schedule"), {
    cache: "no-store"
  });
  return handle<ContactScheduleResponse>(res);
}

export async function generateCallScript(clientId: number): Promise<{
  client_id: number;
  client_name: string;
  script: string;
  key_talking_points: string[];
  provider: string;
}> {
  const res = await fetch(`${apiUrl("/contacts/generate-call-script")}?client_id=${clientId}`, {
    method: "POST",
    cache: "no-store"
  });
  return handle(res);
}

export async function generateEmailDraft(clientId: number): Promise<{
  client_id: number;
  client_name: string;
  subject: string;
  body: string;
  key_points: string[];
  provider: string;
}> {
  const res = await fetch(`${apiUrl("/contacts/generate-email-draft")}?client_id=${clientId}`, {
    method: "POST",
    cache: "no-store"
  });
  return handle(res);
}

export async function approveCallScheduled(clientId: number, actor: string = "advisor"): Promise<{
  success: boolean;
  message: string;
  meeting_note_id?: number;
}> {
  const res = await fetch(apiUrl("/contacts/approve-call-scheduled"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, actor }),
    cache: "no-store"
  });
  return handle(res);
}

export async function approveEmailSent(clientId: number, actor: string = "advisor"): Promise<{
  success: boolean;
  message: string;
  meeting_note_id?: number;
}> {
  const res = await fetch(apiUrl("/contacts/approve-email-sent"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, actor }),
    cache: "no-store"
  });
  return handle(res);
}

export async function approveActivityLogged(clientId: number, actor: string = "advisor", notes?: string): Promise<{
  success: boolean;
  message: string;
  meeting_note_id?: number;
}> {
  const res = await fetch(apiUrl("/contacts/approve-activity-logged"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, actor, notes: notes || undefined }),
    cache: "no-store"
  });
  return handle(res);
}

export async function fetchTaxLossOpportunities(): Promise<TaxLossResponse> {
  const res = await fetch(apiUrl("/tax-loss/opportunities"), {
    cache: "no-store"
  });
  return handle<TaxLossResponse>(res);
}

export async function fetchRiskDashboard(): Promise<RiskDashboardResponse> {
  const res = await fetch(apiUrl("/risk-dashboard/summary"), {
    cache: "no-store"
  });
  return handle<RiskDashboardResponse>(res);
}
