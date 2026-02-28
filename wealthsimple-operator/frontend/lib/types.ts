export type Priority = "HIGH" | "MEDIUM" | "LOW";

export type AlertStatus =
  | "OPEN"
  | "REVIEWED"
  | "ESCALATED"
  | "FALSE_POSITIVE";

export interface ClientSummary {
  id: number;
  name: string;
  email: string;
  segment: string;
  risk_profile: string;
}

export interface PortfolioSummary {
  id: number;
  name: string;
  total_value: number;
  target_equity_pct: number;
  target_fixed_income_pct: number;
  target_cash_pct: number;
}

export interface DecisionTraceStep {
  step: string;
  detail: string;
}

export interface ChangeDetectionItem {
  metric: string;
  from: string;
  to: string;
}

export interface AlertSummary {
  id: number;
  created_at: string;
  priority: Priority;
  confidence: number;
  event_title: string;
  summary: string;
  status: AlertStatus;
  scenario?: string | null;
  client: ClientSummary;
  portfolio: PortfolioSummary;
}

export interface AlertDetail extends AlertSummary {
  summary: string;
  reasoning_bullets: string[];
  human_review_required: boolean;
  suggested_next_step: string;
  decision_trace_steps: DecisionTraceStep[];
  change_detection: ChangeDetectionItem[];
  scenario?: string | null;
  concentration_score: number;
  drift_score: number;
  volatility_proxy: number;
  risk_score: number;
  client_profile_view?: ClientProfileView;
}

export type FollowUpDraftStatus =
  | "PENDING_APPROVAL"
  | "APPROVED_READY"
  | "REJECTED";

export interface FollowUpDraft {
  id: number;
  alert_id: number;
  client_id: number;
  status: FollowUpDraftStatus;
  recipient_email: string;
  subject: string;
  body: string;
  generation_provider: string;
  generated_from: Record<string, unknown>;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export type MeetingNoteType = "meeting" | "phone_call" | "email" | "review";

export interface MeetingNote {
  id: number;
  client_id: number;
  title: string;
  meeting_date: string;
  note_body: string;
  meeting_type: MeetingNoteType;
  call_transcript: string | null;
  ai_summary: string | null;
  ai_action_items: string[] | null;
  ai_summarized_at: string | null;
  ai_provider_used: string | null;
  created_at: string;
}

export interface MeetingNotesListResponse {
  items: MeetingNote[];
  total: number;
}

export interface SummarizeTranscriptResponse {
  note: MeetingNote;
  message: string;
}

export interface MeetingNoteCreate {
  title: string;
  meeting_date: string;
  note_body: string;
  meeting_type?: MeetingNoteType;
  call_transcript?: string;
}

export interface ClientProfileView {
  header: {
    client_name: string;
    portfolio_code: string;
  };
  portfolio_performance: {
    total_aum: string;
    ytd_return_pct: number;
    unrealized_pl: string;
    unrealized_gain_pct: number;
    realized_pl_ytd: string;
    realized_pl_note: string;
  };
  current_asset_allocation: {
    equities_pct: number;
    fixed_income_pct: number;
    alternatives_pct: number;
    cash_pct: number;
  };
  outreach_engagement: {
    last_meeting: string;
    last_meeting_days_ago: number;
    next_scheduled_review: string;
    next_review_in_days: number;
    last_email_contact: string;
    last_email_days_ago: number;
    phone_calls_last_90_days: number;
    avg_call_duration_minutes: number;
  };
  recent_meeting_notes: Array<{
    id?: number;
    title: string;
    date: string;
    note: string;
    action_required: string[];
    meeting_type?: MeetingNoteType;
    call_transcript?: string | null;
    ai_summary?: string | null;
    ai_action_items?: string[] | null;
    ai_summarized_at?: string | null;
    has_transcript?: boolean;
  }>;
  financial_goals: Array<{
    goal: string;
    target_date: string;
    status: string;
    target_amount?: string;
    current_vs_target?: string;
    progress_pct?: number;
    amount?: string;
  }>;
  actions: string[];
}

export interface RunSummary {
  run_id: number;
  provider_used: string;
  created_alerts_count: number;
  priority_counts: Record<Priority, number>;
  top_alerts: AlertSummary[];
}

export interface AuditEventEntry {
  id: number;
  alert_id: number | null;
  run_id: number | null;
  event_type: string;
  actor: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface MonitoringUniverseSummary {
  total_clients: number;
  clients_created_this_year: number;
  total_portfolios: number;
  alerts_by_priority: Record<Priority, number>;
  alerts_by_status: Record<AlertStatus, number>;
  total_runs: number;
  percent_alerts_human_review_required: number;
}

export interface MonitoringClientRow {
  client_id: number;
  client_name: string;
  email: string;
  segment: string;
  risk_profile: string;
  account_tier?: string;
  client_since_year: number;
  portfolios_count: number;
  total_aum: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  ytd_performance_pct: number;
  open_alerts: number;
  queued_for_review: number;
  last_alert_at: string | null;
  last_alert_event?: string | null;
}

export interface MonitoringQueuedCase {
  alert_id: number;
  client_id: number;
  client_name: string;
  portfolio_name: string;
  priority: Priority;
  status: AlertStatus;
  confidence: number;
  human_review_required: boolean;
  event_title: string;
  scenario?: string | null;
  created_at: string;
}

export interface MonitoringUniverseDetail {
  generated_at: string;
  clients: MonitoringClientRow[];
  queued_cases: MonitoringQueuedCase[];
}

export interface AlertsListResponse {
  items: AlertSummary[];
  total: number;
}

export interface AuditListResponse {
  items: AuditEventEntry[];
  total: number;
}

export interface HealthResponse {
  provider: "Mock" | "Gemini";
  raw_provider: string;
  gemini_configured: boolean;
  db_ok: boolean;
  last_run_completed_at: string | null;
}

export type SimulationScenario =
  | "interest_rate_shock"
  | "bond_spread_widening"
  | "equity_drawdown"
  | "multi_asset_regime_change";

export type SimulationSeverity = "mild" | "moderate" | "severe";

export interface SimulationPortfolioImpact {
  client: ClientSummary;
  portfolio: PortfolioSummary;
  risk_before: number;
  risk_after: number;
  delta_risk: number;
  off_trajectory: boolean;
}

export interface SimulationSummary {
  scenario: SimulationScenario;
  severity: SimulationSeverity;
  total_clients: number;
  total_portfolios: number;
  clients_off_trajectory: number;
  portfolios_off_trajectory: number;
  portfolios_on_track: number;
  ai_summary: string;
  ai_checklist: string[];
  impacted_portfolios: SimulationPortfolioImpact[];
}

export interface RebalancingLineItem {
  ticker: string;
  asset_class: string;
  current_weight: number;
  suggested_weight: number;
  delta_weight: number;
  action: string;
}

export interface RebalancingSuggestion {
  alert_id: number;
  generated_at: string;
  current_equity_pct: number;
  target_equity_pct: number;
  current_fixed_income_pct: number;
  target_fixed_income_pct: number;
  current_cash_pct: number;
  target_cash_pct: number;
  line_items: RebalancingLineItem[];
  ai_rationale: string;
  requires_human_approval: boolean;
}

export type ReallocationPlanStatus = "PLANNED" | "QUEUED" | "APPROVED" | "EXECUTED";

export interface ReallocationTrade {
  ticker: string;
  asset_class: string;
  action: string;
  amount: number;
  estimated_units: number;
  settlement_days: number;
  estimated_gain_realized: number;
  estimated_tax_cost: number;
}

export interface ReallocationAlternative {
  name: string;
  estimated_tax_impact: number;
  estimated_liquidity_days: number;
  volatility_after: number;
  rejected_reason: string;
}

export interface ReallocationPlan {
  plan_id: number;
  alert_id: number;
  status: ReallocationPlanStatus;
  generated_at: string;
  target_cash_amount: number;
  current_cash_amount: number;
  additional_cash_needed: number;
  estimated_realized_gains: number;
  estimated_tax_impact: number;
  volatility_before: number;
  volatility_after: number;
  volatility_reduction_pct: number;
  liquidity_days: number;
  ai_rationale: string;
  assumptions: Record<string, unknown>;
  trades: ReallocationTrade[];
  alternatives_considered: ReallocationAlternative[];
  requires_human_approval: boolean;
  simulated_execution: boolean;
  queued_at: string | null;
  approved_at: string | null;
  approved_by: string | null;
  executed_at: string | null;
  execution_reference: string | null;
}

export interface PlaybookAction {
  rank: number;
  client_name: string;
  portfolio_name: string;
  action_type: string;
  urgency: string;
  draft_email_subject: string;
  draft_email_body: string;
}

export interface PlaybookSummary {
  scenario: SimulationScenario;
  severity: SimulationSeverity;
  actions: PlaybookAction[];
  ai_rationale: string;
}
