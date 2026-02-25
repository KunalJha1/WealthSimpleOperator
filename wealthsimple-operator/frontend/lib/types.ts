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
  status: AlertStatus;
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
  concentration_score: number;
  drift_score: number;
  volatility_proxy: number;
  risk_score: number;
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
  total_portfolios: number;
  alerts_by_priority: Record<Priority, number>;
  alerts_by_status: Record<AlertStatus, number>;
  total_runs: number;
  average_alerts_per_run: number;
  percent_alerts_human_review_required: number;
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

