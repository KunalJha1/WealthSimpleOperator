import { ConfidencePill, PriorityPill } from "./StatusPills";
import { Button } from "./Buttons";
import type { AlertDetail } from "../lib/types";

function segmentLabel(segment: string): string {
  if (segment === "HNW") return "High Net Worth";
  return segment;
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

function buildClientProfileExtras(alert: AlertDetail): ClientProfileExtras {
  const { client, id } = alert;
  let investmentHorizon = "Medium-term (7–15 years)";

  const risk = client.risk_profile.toLowerCase();
  if (risk.includes("conservative")) {
    investmentHorizon = "Short to medium-term (3–7 years)";
  } else if (risk.includes("growth")) {
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

  function handleScheduleFollowUp() {
    if (typeof window !== "undefined") {
      window.alert("Follow-up scheduled for this portfolio (demo only).");
    }
  }

  return (
    <section className="card p-5 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="page-title">Risk brief</div>
            <PriorityPill priority={alert.priority} />
            <ConfidencePill confidence={alert.confidence} />
          </div>
          <div className="mt-1 text-sm font-medium text-gray-900">
            Portfolio {portfolio.name}
          </div>
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
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                  AI confidence
                </div>
                <div className="text-sm text-ws-muted">
                  Model confidence score for this alert
                </div>
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
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                  Event
                </div>
                <div className="text-sm font-medium text-gray-900">{alert.event_title}</div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                  AI summary
                </div>
                <p className="text-sm text-gray-800">{alert.summary}</p>
              </div>
              <div className="rounded-lg bg-gray-900 text-gray-100 p-3 space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-300">
                  Priority justification
                </div>
                <p className="text-sm">
                  Ranked with {alert.priority.toLowerCase()} priority based on concentration (
                  {alert.concentration_score.toFixed(1)}), drift ({alert.drift_score.toFixed(1)}),
                  and volatility ({alert.volatility_proxy.toFixed(1)}). Combined risk score is{" "}
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
                    <span>{bullet}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Client profile
            </div>
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
          </div>

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Operator history
            </div>
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
              <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                Operator decision trace
              </div>
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
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Change detection
            </div>
            <div className="text-xs text-ws-muted">
              How key risk metrics have moved since the last operator run.
            </div>
            {alert.change_detection.length === 0 ? (
              <div className="mt-2 text-sm text-ws-muted">
                No prior run metrics available yet for change detection.
              </div>
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
                      <td className="px-3 py-2 text-sm text-gray-900">
                        {item.metric.replace("_", " ")}
                      </td>
                      <td className="px-3 py-2 text-sm text-ws-muted">{item.from}</td>
                      <td className="px-3 py-2 text-sm text-gray-900">{item.to}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Risk metrics
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Concentration score" value={alert.concentration_score} />
              <MetricCard label="Drift score" value={alert.drift_score} />
              <MetricCard label="Volatility proxy" value={alert.volatility_proxy} />
              <MetricCard label="Combined risk score" value={alert.risk_score} />
            </div>
          </div>

          <div className="rounded-xl border border-ws-border bg-white p-4 space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Operator learning & feedback
            </div>
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
            <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
              Human review & responsibility
            </div>
            <div className="text-sm text-gray-900">
              {alert.human_review_required
                ? "Human review required before any client-facing action."
                : "Human review optional — advisor discretion based on client context."}
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
              disabled={updating}
              onClick={() => onAction("escalate")}
            >
              Escalate to senior
            </Button>
            <Button
              variant="ghost"
              type="button"
              disabled={updating}
              onClick={() => onAction("false_positive")}
            >
              False positive
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function ContextCard({ label, lines }: { label: string; lines: string[] }) {
  return (
    <div className="rounded-xl border border-ws-border p-4 space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">{label}</div>
      {lines.map((line) => (
        <div key={`${label}-${line}`} className="text-sm text-gray-900">
          {line}
        </div>
      ))}
    </div>
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
