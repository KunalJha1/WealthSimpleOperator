import { ConfidencePill, PriorityPill } from "./StatusPills";
import { Button } from "./Buttons";
import type { AlertDetail, ClientProfileView } from "../lib/types";
import { useState } from "react";
import { AlertTriangle, ArrowUpRight, UserRound, Loader2 } from "lucide-react";
import { summarizeTranscript } from "../lib/api";

function segmentLabel(segment: string): string {
  if (segment === "HNW") return "High Net Worth";
  return segment;
}

function formatPortfolioCode(id: number): string {
  const code = (10000 + id).toString();
  return `Portfolio PTF-${code}`;
}

type RiskBriefAction = "reviewed" | "escalate" | "false_positive";

type ClientProfileExtras = {
  investmentHorizon: string;
  lastAdvisorReviewLabel: string;
  advisorName: string;
};

type OperatorHistoryEntry = {
  dateLabel: string;
  description: string;
};

type OperatorLearningStats = {
  casesIncorporated: number;
  falsePositivesCorrected: number;
  calibrationStatus: string;
};

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0
  }).format(amount);
}

function formatDateISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function formatDateLabel(baseDate: Date, offsetDays: number): string {
  const value = new Date(baseDate);
  value.setDate(value.getDate() + offsetDays);
  return formatDateISO(value);
}

function buildClientProfileExtras(alert: AlertDetail): ClientProfileExtras {
  const { client, id } = alert;
  let investmentHorizon = "Medium-term (7-15 years)";

  const risk = client.risk_profile.toLowerCase();
  if (risk.includes("conservative")) {
    investmentHorizon = "Short to medium-term (3-7 years)";
  } else if (risk.includes("growth") || risk.includes("moderate")) {
    investmentHorizon = "Long-term (15+ years)";
  }

  const daysAgo = 20 + (id % 60);
  const lastAdvisorReviewLabel = `${daysAgo} days ago`;

  const advisors = ["Jordan Lee", "Sarah Chen", "Michael Patel", "Alex Martinez"];
  const advisorName = advisors[id % advisors.length];

  return {
    investmentHorizon,
    lastAdvisorReviewLabel,
    advisorName
  };
}

function buildOperatorHistory(alert: AlertDetail): OperatorHistoryEntry[] {
  const created = new Date(alert.created_at);
  const priorityLabel = alert.priority.charAt(0) + alert.priority.slice(1).toLowerCase();

  return [
    {
      dateLabel: formatDateLabel(created, -5),
      description: "Risk within tolerance"
    },
    {
      dateLabel: formatDateLabel(created, -3),
      description: "Minor drift detected"
    },
    {
      dateLabel: formatDateLabel(created, -1),
      description: `Escalated to ${priorityLabel} priority`
    }
  ];
}

function buildOperatorLearningStats(alert: AlertDetail): OperatorLearningStats {
  const seed = alert.id;
  const casesIncorporated = 30 + (seed % 50);
  const falsePositivesCorrected = 5 + (seed % 15);
  const calibrationStatus = seed % 3 === 0 ? "Stable" : "Improving";

  return {
    casesIncorporated,
    falsePositivesCorrected,
    calibrationStatus
  };
}

export default function RiskBrief({
  alert,
  onAction,
  updating
}: {
  alert: AlertDetail;
  onAction: (action: RiskBriefAction) => void;
  updating: boolean;
}) {
  const client = alert.client;
  const portfolio = alert.portfolio;
  const confidence = Math.max(0, Math.min(100, alert.confidence));
  const clientExtras = buildClientProfileExtras(alert);
  const operatorHistory = buildOperatorHistory(alert);
  const learningStats = buildOperatorLearningStats(alert);
  const [showClientProfile, setShowClientProfile] = useState(false);

  function notify(message: string) {
    if (typeof window !== "undefined") {
      window.alert(message);
    }
  }

  function handleScheduleFollowUp() {
    notify("Follow-up scheduled for this portfolio (demo only).");
  }

  function handleScheduleMeeting() {
    notify(`Meeting scheduled for ${alert.client.name}. Calendar invitation sent.`);
  }

  function handleSendEmail() {
    notify(`Email draft created for ${alert.client.name}. Opened in your email client.`);
  }

  return (
    <>
      <section className="card p-5 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="page-title">Risk brief</div>
            <PriorityPill priority={alert.priority} />
            <ConfidencePill confidence={alert.confidence} />
          </div>
          <div className="mt-1 text-sm font-medium text-gray-900">{formatPortfolioCode(portfolio.id)}</div>
          <div className="page-subtitle">{alert.event_title}</div>
        </div>
        <div className="text-right text-xs text-ws-muted space-y-1">
          <div>Client segment: {segmentLabel(client.segment)}</div>
          <div>Risk profile: {client.risk_profile}</div>
          <div>Investment horizon: {clientExtras.investmentHorizon}</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="rounded-xl border-[0.5px] border-gray-200 bg-gray-50 p-4 space-y-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">AI confidence</div>
                <div className="text-sm text-ws-muted">Model confidence score for this alert</div>
              </div>
              <div className="text-3xl font-semibold text-gray-900">{confidence}%</div>
            </div>
            <div className="h-2 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-gray-900"
                style={{ width: `${Math.max(confidence, 3)}%` }}
              />
            </div>
          </div>

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Event</div>
                <div className="text-sm text-gray-800">{alert.event_title}</div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">AI summary</div>
                <p className="text-sm text-gray-800">{alert.summary}</p>
              </div>
              <div className="rounded-lg bg-gray-900 text-gray-100 p-3 space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-300">
                  Priority justification
                </div>
                <p className="text-sm">
                  Ranked with {alert.priority.toLowerCase()} priority based on concentration (
                  {alert.concentration_score.toFixed(1)}), drift ({alert.drift_score.toFixed(1)}), and
                  volatility ({alert.volatility_proxy.toFixed(1)}). Combined risk score is {" "}
                  {alert.risk_score.toFixed(1)} / 10. Human review is required before any client
                  action.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-baseline justify-between gap-2">
                <div className="text-sm font-semibold text-gray-900">AI reasoning</div>
                <div className="text-xs text-ws-muted">AI-generated reasoning</div>
              </div>
              <ol className="space-y-1 text-sm text-gray-800">
                {alert.reasoning_bullets.map((bullet, idx) => (
                  <li key={`${idx}-${bullet}`} className="flex gap-2">
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-700">
                      {idx + 1}
                    </span>
                    <span className="text-sm text-gray-800">{bullet}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Client profile</div>
            <div className="text-sm font-medium text-gray-900">{client.name}</div>
            <dl className="mt-1 space-y-1 text-xs text-gray-800">
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Risk tolerance</dt>
                <dd className="text-gray-900">{client.risk_profile}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Investment horizon</dt>
                <dd className="text-gray-900">{clientExtras.investmentHorizon}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Last advisor review</dt>
                <dd className="text-gray-900">{clientExtras.lastAdvisorReviewLabel}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Advisor</dt>
                <dd className="text-gray-900">{clientExtras.advisorName}</dd>
              </div>
            </dl>
            <Button
              type="button"
              variant="secondary"
              className="mt-3 inline-flex text-xs px-3 py-1.5 w-full justify-center"
              disabled={updating}
              onClick={() => setShowClientProfile(true)}
            >
              <UserRound className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Full Profile
            </Button>
          </div>

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Operator history</div>
            <div className="relative pl-3">
              <div className="absolute left-0 top-0 bottom-0 w-px bg-gray-200" />
              <ul className="space-y-2 text-xs text-gray-800">
                {operatorHistory.map((entry) => (
                  <li key={`${entry.dateLabel}-${entry.description}`} className="relative flex gap-2">
                    <span className="absolute -left-1.5 mt-1 h-2 w-2 rounded-full bg-gray-400" />
                    <div>
                      <div className="text-[11px] text-ws-muted">{entry.dateLabel}</div>
                      <div className="text-gray-900">{entry.description}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {alert.decision_trace_steps.length > 0 && (
            <div className="rounded-xl border border-ws-border bg-white p-4 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Operator decision trace</div>
              <div className="text-xs text-ws-muted">
                How the AI evaluated the portfolio, client constraints, and deviation severity
                before ranking this alert.
              </div>
              <ol className="mt-2 space-y-2 text-sm text-gray-800 list-decimal list-inside">
                {alert.decision_trace_steps.map((step, idx) => (
                  <li key={`${idx}-${step.step}`} className="space-y-0.5">
                    <div className="font-medium">{step.step}</div>
                    <div className="text-ws-muted text-xs">{step.detail}</div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Change detection</div>
            <div className="text-xs text-ws-muted">How key risk metrics have moved since the last operator run.</div>
            {alert.change_detection.length === 0 ? (
              <div className="mt-2 text-sm text-ws-muted">No prior run metrics available yet for change detection.</div>
            ) : (
              <table className="mt-3 min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <th className="px-3 py-2">Metric</th>
                    <th className="px-3 py-2">From</th>
                    <th className="px-3 py-2">To</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ws-border">
                  {alert.change_detection.map((item, idx) => (
                    <tr key={`${idx}-${item.metric}`}>
                      <td className="px-3 py-2 text-sm text-gray-900">{item.metric.replace("_", " ")}</td>
                      <td className="px-3 py-2 text-sm text-ws-muted">{item.from}</td>
                      <td className="px-3 py-2 text-sm text-gray-900">{item.to}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {alert.scenario && (
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-blue-900">Scenario match</div>
              <div className="text-sm text-blue-900 font-medium">{alert.scenario.replace(/_/g, " ")}</div>
              <div className="text-xs text-blue-700">This alert was matched to a specific client scenario detected from meeting notes.</div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Risk metrics</div>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Concentration score" value={alert.concentration_score} />
              <MetricCard label="Drift score" value={alert.drift_score} />
              <MetricCard label="Volatility proxy" value={alert.volatility_proxy} />
              <MetricCard label="Combined risk score" value={alert.risk_score} />
            </div>
          </div>

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Operator learning & feedback</div>
            <dl className="mt-1 space-y-1 text-xs text-gray-800">
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Human feedback incorporated</dt>
                <dd className="text-gray-900">{learningStats.casesIncorporated} cases</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">False positives corrected</dt>
                <dd className="text-gray-900">{learningStats.falsePositivesCorrected}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ws-muted">Confidence calibration</dt>
                <dd className="text-gray-900">{learningStats.calibrationStatus}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-ws-border bg-gray-50 p-4 space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Human review & responsibility</div>
            <div className="text-sm text-gray-900">
              {alert.human_review_required
                ? "Human review required before any client-facing action."
                : "Human review optional - advisor discretion based on client context."}
            </div>
            <div className="text-xs text-ws-muted">
              <span className="font-medium">AI responsibility:</span> detection, triage, and
              explanation of portfolio risk signals.
            </div>
            <div className="text-xs text-ws-muted">
              <span className="font-medium">Human responsibility:</span> all investment
              decisions, client communication, escalation, and interpretation of these signals.
            </div>
          </div>
          <div className="flex flex-wrap gap-2 justify-start md:justify-end">
            <Button
              variant="secondary"
              type="button"
              disabled={updating}
              onClick={() => onAction("reviewed")}
            >
              Mark as reviewed
            </Button>
            <Button
              variant="secondary"
              type="button"
              disabled={updating}
              onClick={handleScheduleFollowUp}
            >
              Schedule follow-up
            </Button>
            <Button
              variant="secondary"
              type="button"
              className="!border-2 !border-amber-400 !bg-white !text-amber-700 hover:!bg-amber-50"
              disabled={updating}
              onClick={() => onAction("escalate")}
            >
              <ArrowUpRight className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Escalate to senior
            </Button>
            <Button
              variant="ghost"
              type="button"
              className="!border-2 !border-red-300 !bg-white !text-red-600 hover:!bg-red-50"
              disabled={updating}
              onClick={() => onAction("false_positive")}
            >
              <AlertTriangle className="mr-1.5 h-4 w-4" aria-hidden="true" />
              False positive
            </Button>
          </div>
        </div>
      </div>

      </section>
      {showClientProfile && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
          <div className="relative w-full max-w-5xl max-h-[90vh] rounded-2xl bg-white shadow-2xl flex flex-col overflow-hidden">
            <div className="flex items-center justify-between border-b border-ws-border px-5 py-3 md:px-6 md:py-4 shrink-0">
              <div className="space-y-0.5">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Client details
                </div>
                <div className="text-sm font-medium text-gray-900">
                  {alert.client.name} • {formatPortfolioCode(alert.portfolio.id)}
                </div>
              </div>
              <button
                type="button"
                className="rounded-full border border-ws-border bg-white px-4 py-1.5 text-xs font-medium text-ws-muted shadow-sm hover:bg-gray-50 shrink-0"
                onClick={() => setShowClientProfile(false)}
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              <div className="p-5 md:p-6">
                <ClientDetailsPanel alert={alert} />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-ws-border p-3">
      <div className="text-xs text-ws-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold text-gray-900">{value.toFixed(1)} / 10</div>
    </div>
  );
}

function buildFallbackClientProfileView(alert: AlertDetail): ClientProfileView {
  const { client, portfolio, risk_score } = alert;
  const aum = portfolio.total_value;
  const ytdReturnPct = 4 + (alert.id % 9);
  const unrealizedPL = (aum * ytdReturnPct) / 100;
  const realizedPL = (aum * (1 + (alert.id % 5))) / 100;

  const equityDrift = Math.min(7, Math.max(0, Math.round(alert.drift_score)));
  const equities = Math.min(90, Math.max(0, portfolio.target_equity_pct + equityDrift));
  const fixedIncome = Math.max(0, portfolio.target_fixed_income_pct - Math.round(equityDrift * 0.6));
  const cash = Math.max(2, portfolio.target_cash_pct);
  const alternatives = Math.max(0, 100 - equities - fixedIncome - cash);

  const referenceDate = new Date(alert.created_at);
  const lastMeetingDaysAgo = 20 + (alert.id % 40);
  const nextReviewInDays = 10 + (alert.id % 30);
  const lastEmailDaysAgo = 5 + (alert.id % 10);

  const lastMeeting = new Date(referenceDate);
  const nextReview = new Date(referenceDate);
  const lastEmail = new Date(referenceDate);
  lastMeeting.setDate(referenceDate.getDate() - lastMeetingDaysAgo);
  nextReview.setDate(referenceDate.getDate() + nextReviewInDays);
  lastEmail.setDate(referenceDate.getDate() - lastEmailDaysAgo);

  const callsLast90Days = 2 + (alert.id % 4);
  const avgCallDuration = 14 + (alert.id % 8);

  const homeGoalAmount = 350_000 + (alert.id % 5) * 25_000;
  const retirementTarget = 2_000_000 + (alert.id % 6) * 250_000;
  const retirementCurrent = retirementTarget * (0.4 + risk_score / 25);
  const retirementProgress = Math.min(100, Math.max(0, Math.round((retirementCurrent / retirementTarget) * 100)));

  return {
    header: {
      client_name: client.name,
      portfolio_code: formatPortfolioCode(portfolio.id)
    },
    portfolio_performance: {
      total_aum: formatCurrency(aum),
      ytd_return_pct: ytdReturnPct,
      unrealized_pl: formatCurrency(unrealizedPL),
      unrealized_gain_pct: Number(((unrealizedPL / aum) * 100).toFixed(1)),
      realized_pl_ytd: formatCurrency(realizedPL),
      realized_pl_note: "From rebalancing"
    },
    current_asset_allocation: {
      equities_pct: Number(equities.toFixed(1)),
      fixed_income_pct: Number(fixedIncome.toFixed(1)),
      alternatives_pct: Number(alternatives.toFixed(1)),
      cash_pct: Number(cash.toFixed(1))
    },
    outreach_engagement: {
      last_meeting: formatDateISO(lastMeeting),
      last_meeting_days_ago: lastMeetingDaysAgo,
      next_scheduled_review: formatDateISO(nextReview),
      next_review_in_days: nextReviewInDays,
      last_email_contact: formatDateISO(lastEmail),
      last_email_days_ago: lastEmailDaysAgo,
      phone_calls_last_90_days: callsLast90Days,
      avg_call_duration_minutes: avgCallDuration
    },
    recent_meeting_notes: [
      {
        title: "Q4 2025 Portfolio Review",
        date: formatDateISO(lastMeeting),
        note:
          "Client expressed satisfaction with performance. Discussed upcoming home purchase and need for liquidity planning. Client wants reduced equity exposure before withdrawal.",
        action_required: ["Tax planning"]
      },
      {
        title: "Annual Planning Meeting",
        date: formatDateLabel(lastMeeting, -43),
        note:
          "Reviewed financial goals and risk questionnaire. Confirmed current profile and retirement timeline. Estate planning updates were completed.",
        action_required: []
      }
    ],
    financial_goals: [
      {
        goal: "Home Purchase",
        target_date: "Late 2026",
        status: "In Progress",
        target_amount: formatCurrency(homeGoalAmount)
      },
      {
        goal: "Retirement Savings",
        target_date: "2041",
        status: "On Track",
        current_vs_target: `${formatCurrency(retirementCurrent)} / ${formatCurrency(retirementTarget)}`,
        progress_pct: retirementProgress
      },
      {
        goal: "Emergency Fund",
        target_date: "6 months expenses",
        status: "Complete",
        amount: formatCurrency(45_000)
      }
    ],
    actions: ["Schedule Meeting", "Send Email", "Add Note"]
  };
}

export function ClientDetailsPanel({ alert }: { alert: AlertDetail }) {
  const profile = alert.client_profile_view ?? buildFallbackClientProfileView(alert);
  const [localNotes, setLocalNotes] = useState(profile.recent_meeting_notes);
  const [activeNoteTab, setActiveNoteTab] = useState<Record<number, "notes" | "transcript" | "ai_summary">>({});
  const [summarizing, setSummarizing] = useState<Record<number, boolean>>({});
  const [localGoals, setLocalGoals] = useState(profile.financial_goals);
  const [showAddGoalForm, setShowAddGoalForm] = useState(false);
  const [newGoal, setNewGoal] = useState({ goal: "", target_date: "", status: "In Progress", target_amount: "" });
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [newNote, setNewNote] = useState({ title: "", note: "" });

  const allocationRows = [
    { label: "Equities", value: profile.current_asset_allocation.equities_pct, color: "bg-gray-900" },
    {
      label: "Fixed Income",
      value: profile.current_asset_allocation.fixed_income_pct,
      color: "bg-emerald-500"
    },
    {
      label: "Alternatives",
      value: profile.current_asset_allocation.alternatives_pct,
      color: "bg-amber-500"
    },
    { label: "Cash", value: profile.current_asset_allocation.cash_pct, color: "bg-gray-400" }
  ];

  function notifyUser(message: string) {
    if (typeof window !== "undefined") {
      window.alert(message);
    }
  }

  function handleScheduleMeeting() {
    notifyUser(`Meeting scheduled for ${alert.client.name}. Calendar invitation sent.`);
  }

  function handleSendEmail() {
    notifyUser(`Email draft created for ${alert.client.name}. Opened in your email client.`);
  }

  async function handleSummarize(noteId: number | undefined) {
    if (!noteId) return;
    try {
      setSummarizing(prev => ({ ...prev, [noteId]: true }));
      const res = await summarizeTranscript(noteId);
      setLocalNotes(prev =>
        prev.map(n => n.id === noteId ? { ...n, ...res.note } : n)
      );
    } catch (err) {
      notifyUser(`Failed to summarize: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSummarizing(prev => ({ ...prev, [noteId]: false }));
    }
  }

  function handleAddNote() {
    if (!newNote.title.trim() || !newNote.note.trim()) {
      notifyUser("Please fill in both title and note");
      return;
    }
    const addedNote = {
      id: Date.now(),
      title: newNote.title,
      date: new Date().toISOString().slice(0, 10),
      note: newNote.note,
      action_required: [],
      meeting_type: "meeting" as const,
      has_transcript: false,
      call_transcript: ""
    };
    setLocalNotes(prev => [addedNote, ...prev]);
    setNewNote({ title: "", note: "" });
    setShowNoteForm(false);
    notifyUser("Note added successfully!");
  }

  function handleAddGoal() {
    if (!newGoal.goal.trim() || !newGoal.target_date.trim() || !newGoal.target_amount.trim()) {
      notifyUser("Please fill in all fields");
      return;
    }
    const addedGoal = {
      goal: newGoal.goal,
      target_date: newGoal.target_date,
      status: newGoal.status as "In Progress" | "On Track" | "Complete",
      target_amount: newGoal.target_amount
    };
    setLocalGoals(prev => [addedGoal, ...prev]);
    setNewGoal({ goal: "", target_date: "", status: "In Progress", target_amount: "" });
    setShowAddGoalForm(false);
    notifyUser("Goal added successfully!");
  }

  return (
    <div className="rounded-xl border border-ws-border bg-white p-4 space-y-4">
      <div className="space-y-1">
        <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">Client profile</div>
        <div className="text-sm font-medium text-gray-900">{profile.header.client_name}</div>
        <div className="text-xs text-ws-muted">{profile.header.portfolio_code}</div>
      </div>

      <div className="space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wide text-ws-muted">Portfolio Performance</h3>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-2 hover:border-gray-300 transition-colors">
            <div className="text-xs font-medium text-ws-muted uppercase tracking-wide">Total AUM</div>
            <div className="text-2xl font-bold text-gray-900">{profile.portfolio_performance.total_aum}</div>
            <div className="flex items-center gap-1">
              <span className="text-xs font-semibold text-emerald-600">↑ +{profile.portfolio_performance.ytd_return_pct.toFixed(1)}%</span>
              <span className="text-[10px] text-ws-muted">YTD</span>
            </div>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4 space-y-2 hover:border-emerald-300 transition-colors">
            <div className="text-xs font-medium text-emerald-700 uppercase tracking-wide">Unrealized P/L</div>
            <div className="text-2xl font-bold text-emerald-700">{profile.portfolio_performance.unrealized_pl}</div>
            <div className="flex items-center gap-1">
              <span className="text-xs font-semibold text-emerald-600">+{profile.portfolio_performance.unrealized_gain_pct.toFixed(1)}%</span>
              <span className="text-[10px] text-emerald-600">gain</span>
            </div>
          </div>
          <div className="rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 space-y-2 hover:border-blue-300 transition-colors">
            <div className="text-xs font-medium text-blue-700 uppercase tracking-wide">Realized P/L (YTD)</div>
            <div className="text-2xl font-bold text-blue-700">{profile.portfolio_performance.realized_pl_ytd}</div>
            <div className="text-xs text-blue-600 font-medium">{profile.portfolio_performance.realized_pl_note}</div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wide text-ws-muted">Current Asset Allocation</h3>
        <div className="space-y-2 text-xs text-gray-900">
          {allocationRows.map((row) => (
            <div key={row.label}>
              <div className="flex items-center justify-between">
                <span>{row.label}</span>
                <span className="text-ws-muted">{row.value.toFixed(0)}%</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-gray-200">
                <div
                  className={`h-1.5 rounded-full ${row.color}`}
                  style={{ width: `${Math.min(100, Math.max(0, row.value))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wide text-ws-muted">Outreach & Engagement</h4>
          <dl className="space-y-1 text-xs text-gray-800">
            <div className="flex justify-between gap-3">
              <dt className="text-ws-muted">Last meeting</dt>
              <dd className="text-gray-900">
                {profile.outreach_engagement.last_meeting} ({profile.outreach_engagement.last_meeting_days_ago} days ago)
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ws-muted">Next scheduled review</dt>
              <dd className="text-gray-900">
                {profile.outreach_engagement.next_scheduled_review} (in {profile.outreach_engagement.next_review_in_days} days)
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ws-muted">Last email contact</dt>
              <dd className="text-gray-900">
                {profile.outreach_engagement.last_email_contact} ({profile.outreach_engagement.last_email_days_ago} days ago)
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ws-muted">Phone calls (last 90 days)</dt>
              <dd className="text-gray-900">
                {profile.outreach_engagement.phone_calls_last_90_days} {profile.outreach_engagement.phone_calls_last_90_days === 1 ? "call" : "calls"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ws-muted">Avg duration</dt>
              <dd className="text-gray-900">{profile.outreach_engagement.avg_call_duration_minutes} min</dd>
            </div>
          </dl>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wide text-ws-muted">Financial Goals</h4>
            <button
              type="button"
              onClick={() => setShowAddGoalForm(!showAddGoalForm)}
              className="text-xs font-medium text-emerald-600 hover:text-emerald-700 hover:underline"
            >
              + Add Goal
            </button>
          </div>

          {showAddGoalForm && (
            <div className="rounded-lg border-2 border-emerald-200 bg-emerald-50 p-3 space-y-2">
              <input
                type="text"
                placeholder="Goal name (e.g., Home Purchase)"
                value={newGoal.goal}
                onChange={(e) => setNewGoal(prev => ({ ...prev, goal: e.target.value }))}
                className="w-full rounded border border-emerald-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-emerald-500"
              />
              <input
                type="text"
                placeholder="Target date (e.g., Late 2026)"
                value={newGoal.target_date}
                onChange={(e) => setNewGoal(prev => ({ ...prev, target_date: e.target.value }))}
                className="w-full rounded border border-emerald-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-emerald-500"
              />
              <input
                type="text"
                placeholder="Target amount (e.g., $350,000)"
                value={newGoal.target_amount}
                onChange={(e) => setNewGoal(prev => ({ ...prev, target_amount: e.target.value }))}
                className="w-full rounded border border-emerald-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-emerald-500"
              />
              <select
                value={newGoal.status}
                onChange={(e) => setNewGoal(prev => ({ ...prev, status: e.target.value }))}
                className="w-full rounded border border-emerald-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-emerald-500"
              >
                <option value="In Progress">In Progress</option>
                <option value="On Track">On Track</option>
                <option value="Complete">Complete</option>
              </select>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleAddGoal}
                  className="flex-1 rounded bg-emerald-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                >
                  Add Goal
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddGoalForm(false)}
                  className="flex-1 rounded border border-gray-300 bg-white px-2 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="space-y-3 text-xs text-gray-900">
            {localGoals.map((goal, idx) => {
              const isComplete = goal.status === "Complete";
              const isOnTrack = goal.status === "On Track";
              const statusClasses = isComplete
                ? "bg-emerald-100 text-emerald-800"
                : isOnTrack
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-amber-100 text-amber-800";
              const barColor =
                goal.goal === "Home Purchase" ? "bg-purple-500" : "bg-emerald-500";

              return (
                <div
                  key={`${goal.goal}-${goal.target_date}-${idx}`}
                  className="rounded-xl border border-gray-200 bg-gradient-to-br from-gray-50 to-white p-3 md:p-4 space-y-3 hover:border-gray-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="text-xs font-bold text-gray-900">{goal.goal}</div>
                      <div className="mt-1 text-[11px] text-ws-muted">
                        Target: {goal.target_date}
                      </div>
                    </div>
                    <span
                      className={`inline-block rounded-full px-2.5 py-1 text-[10px] font-semibold whitespace-nowrap ${statusClasses}`}
                    >
                      {goal.status}
                    </span>
                  </div>
                  {goal.target_amount && (
                    <div className="text-sm font-semibold text-gray-900">{goal.target_amount}</div>
                  )}
                  {goal.current_vs_target && (
                    <div className="text-sm font-semibold text-gray-900">{goal.current_vs_target}</div>
                  )}
                  {typeof goal.progress_pct === "number" && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-ws-muted">Progress</span>
                        <span className="text-[11px] font-semibold text-gray-900">{goal.progress_pct}%</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-gray-200">
                        <div
                          className={`h-2 rounded-full transition-all ${barColor}`}
                          style={{
                            width: `${Math.min(100, Math.max(0, goal.progress_pct))}%`
                          }}
                        />
                      </div>
                    </div>
                  )}
                  {goal.amount && <div className="text-sm font-semibold text-gray-900">{goal.amount}</div>}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wide text-ws-muted">Recent Meeting Notes</h3>
          <button
            type="button"
            onClick={() => setShowNoteForm(!showNoteForm)}
            className="text-xs font-medium text-emerald-600 hover:text-emerald-700 hover:underline"
          >
            + Add Note
          </button>
        </div>

        {showNoteForm && (
          <div className="rounded-lg border-2 border-blue-200 bg-blue-50 p-3 space-y-2">
            <input
              type="text"
              placeholder="Meeting title"
              value={newNote.title}
              onChange={(e) => setNewNote(prev => ({ ...prev, title: e.target.value }))}
              className="w-full rounded border border-blue-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-blue-500"
            />
            <textarea
              placeholder="Meeting notes"
              value={newNote.note}
              onChange={(e) => setNewNote(prev => ({ ...prev, note: e.target.value }))}
              className="w-full rounded border border-blue-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-blue-500 min-h-20"
            />
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleAddNote}
                className="flex-1 rounded bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
              >
                Add Note
              </button>
              <button
                type="button"
                onClick={() => setShowNoteForm(false)}
                className="flex-1 rounded border border-gray-300 bg-white px-2 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {localNotes.map((note) => {
            const hasTranscript = note.has_transcript && note.call_transcript;
            const noteId = note.id || 0;
            const activeTab = activeNoteTab[noteId] || "notes";

            return (
              <div key={`${note.title}-${note.date}`} className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 hover:border-gray-300 transition-colors">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <div className="text-xs font-semibold text-gray-900">{note.title}</div>
                      {note.meeting_type === "phone_call" && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-800">
                          Phone call
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-ws-muted mt-1">{note.date}</div>
                  </div>
                </div>

                {hasTranscript ? (
                  <>
                    {/* Tab bar for notes with transcript */}
                    <div className="flex gap-1 border-b border-ws-border">
                      {["notes", "transcript", "ai_summary"].map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setActiveNoteTab(prev => ({ ...prev, [noteId]: tab as any }))}
                          className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                            activeTab === tab
                              ? "border-gray-900 text-gray-900"
                              : "border-transparent text-ws-muted hover:text-gray-900"
                          }`}
                        >
                          {tab === "notes" ? "Notes" : tab === "transcript" ? "Transcript" : "AI Summary"}
                        </button>
                      ))}
                    </div>

                    {/* Notes tab */}
                    {activeTab === "notes" && (
                      <div className="space-y-2">
                        <p className="text-xs text-gray-700">{note.note}</p>
                        {note.action_required && note.action_required.length > 0 && (
                          <div className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                            Action required: {note.action_required.join(", ")}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Transcript tab */}
                    {activeTab === "transcript" && (
                      <div className="bg-white rounded border border-ws-border p-3">
                        <pre className="text-[11px] text-gray-700 overflow-x-auto whitespace-pre-wrap break-words max-h-48">
                          {note.call_transcript}
                        </pre>
                      </div>
                    )}

                    {/* AI Summary tab */}
                    {activeTab === "ai_summary" && (
                      <div className="space-y-2">
                        {note.ai_summary ? (
                          <>
                            <p className="text-xs text-gray-700">{note.ai_summary}</p>
                            {note.ai_action_items && note.ai_action_items.length > 0 && (
                              <div className="space-y-1">
                                <div className="text-xs font-semibold text-gray-900">Action items:</div>
                                <ul className="list-disc list-inside space-y-1">
                                  {note.ai_action_items.map((item, idx) => (
                                    <li key={idx} className="text-xs text-gray-700">{item}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            <div className="text-[10px] text-ws-muted italic">
                              AI-generated summary. Advisor judgment required.
                            </div>
                          </>
                        ) : (
                          <div className="space-y-2">
                            <p className="text-xs text-ws-muted">No AI summary yet.</p>
                            <Button
                              type="button"
                              variant="secondary"
                              className="text-xs px-3 py-1.5"
                              disabled={summarizing[noteId]}
                              onClick={() => handleSummarize(noteId)}
                            >
                              {summarizing[noteId] && (
                                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" aria-hidden="true" />
                              )}
                              {summarizing[noteId] ? "Summarizing..." : "Generate AI Summary"}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  /* Non-transcript notes: simple rendering */
                  <div className="space-y-2">
                    <p className="text-xs text-gray-700">{note.note}</p>
                    {note.action_required && note.action_required.length > 0 && (
                      <div className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                        Action required: {note.action_required.join(", ")}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-t border-ws-border pt-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted mb-3">Quick Actions</div>
        <div className="grid gap-2 md:grid-cols-3">
          <Button
            type="button"
            variant="secondary"
            className="text-xs px-3 py-2 flex items-center justify-center gap-2 bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100"
            onClick={handleScheduleMeeting}
          >
            <span>📅</span>
            Schedule Meeting
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="text-xs px-3 py-2 flex items-center justify-center gap-2 bg-green-50 border-green-200 text-green-700 hover:bg-green-100"
            onClick={handleSendEmail}
          >
            <span>✉️</span>
            Send Email
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="text-xs px-3 py-2 flex items-center justify-center gap-2 bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100"
            onClick={() => notify(`Task added to follow-up queue`)}
          >
            <span>✓</span>
            Create Task
          </Button>
        </div>
      </div>
    </div>
  );
}
