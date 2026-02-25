"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { AlertDetail, AlertSummary } from "../lib/types";
import { formatDateTime } from "../lib/utils";
import { fetchAlert } from "../lib/api";
import { ConfidencePill, PriorityPill, StatusPill } from "./StatusPills";
import { Button } from "./Buttons";

interface PriorityQueueProps {
  alerts: AlertSummary[];
}

type QueueEvent = {
  timestamp: string;
  message: string;
};

type MiniHistoryEntry = {
  dateLabel: string;
  description: string;
};

type ClientProfileExtras = {
  investmentHorizon: string;
  lastAdvisorReviewLabel: string;
  advisorName: string;
};

function segmentLabel(segment: string): string {
  if (segment === "HNW") return "High Net Worth";
  return segment;
}

function pseudoRandomForAlert(id: number): number {
  const x = Math.sin(id * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function buildClientProfileExtras(detail: AlertDetail): ClientProfileExtras {
  const { client, id } = detail;

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

function buildMiniHistory(alert: AlertSummary): MiniHistoryEntry[] {
  const created = new Date(alert.created_at);
  const priorityLabel = alert.priority.charAt(0) + alert.priority.slice(1).toLowerCase();

  function dateWithOffset(offsetDays: number): string {
    const d = new Date(created.getTime() + offsetDays * 24 * 60 * 60 * 1000);
    return d.toISOString().slice(0, 10);
  }

  return [
    {
      dateLabel: dateWithOffset(-5),
      description: "Risk within tolerance"
    },
    {
      dateLabel: dateWithOffset(-3),
      description: "Minor drift detected"
    },
    {
      dateLabel: dateWithOffset(-1),
      description: `Escalated to ${priorityLabel} priority`
    }
  ];
  const priorityLabel = alert.priority.charAt(0) + alert.priority.slice(1).toLowerCase();
}

function buildEvents(alert: AlertSummary): QueueEvent[] {
  const baseMinutes = 2 + Math.floor(pseudoRandomForAlert(alert.id) * 5); // 2–6 minutes ago
  const offsets = [
    baseMinutes + 13, // earliest event
    baseMinutes + 9,
    baseMinutes + 5,
    baseMinutes // most recent event
  ];

  return [
    {
      timestamp: `T-${offsets[0]}m`,
      message: "Risk within tolerance"
    },
    {
      timestamp: `T-${offsets[1]}m`,
      message: "Minor drift detected"
    },
    {
      timestamp: `T-${offsets[2]}m`,
      message: `Escalated to ${priorityLabel} priority`
    },
    {
      timestamp: `T-${offsets[3]}m`,
      message: "Queued for operator review"
    }
  ];
}

export default function PriorityQueue({ alerts }: PriorityQueueProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(5);
  const [selectedDetail, setSelectedDetail] = useState<AlertDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const selected = useMemo(
    () => alerts.find((a) => a.id === selectedId) ?? null,
    [alerts, selectedId]
  );

  const visibleAlerts = useMemo(
    () => alerts.slice(0, visibleCount),
    [alerts, visibleCount]
  );

  useEffect(() => {
    if (selectedId == null) {
      setSelectedDetail(null);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);

    fetchAlert(selectedId)
      .then((detail) => {
        if (!cancelled) {
          setSelectedDetail(detail);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setSelectedDetail(null);
          setDetailError((e as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  if (!alerts.length) {
    return (
      <div className="card p-4 text-sm text-ws-muted">
        No alerts yet. Run the operator to generate a triage queue.
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="page-title">Priority queue</div>
          <div className="page-subtitle">
            Event-driven triage feed ranked by priority and confidence.
          </div>
        </div>
        <div className="text-xs text-ws-muted">{alerts.length} items in queue</div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,1fr)] gap-4">
        <div className="space-y-3">
          {visibleAlerts.map((alert, index) => {
            const active = selected?.id === alert.id;
            const priorityAccent =
              alert.priority === "HIGH"
                ? "border-red-500 shadow-[0_0_0_1px_rgba(248,113,113,0.45)]"
                : alert.priority === "MEDIUM"
                  ? "border-amber-400 shadow-[0_0_0_1px_rgba(251,191,36,0.35)]"
                  : "border-emerald-400 shadow-[0_0_0_1px_rgba(52,211,153,0.35)]";

            return (
              <div
                key={`${alert.id}-${index}`}
                role="button"
                tabIndex={0}
                className={`w-full text-left card p-4 transition-colors cursor-pointer ${
                  active ? `${priorityAccent} bg-gray-50` : "hover:border-gray-400"
                }`}
                onClick={() => setSelectedId(alert.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedId(alert.id);
                  }
                }}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <PriorityPill priority={alert.priority} />
                    <StatusPill status={alert.status} />
                  </div>
                  <div className="text-xs text-ws-muted">{formatDateTime(alert.created_at)}</div>
                </div>

                <div className="mt-3">
                  <div className="text-xs text-ws-muted">Portfolio {alert.portfolio.name}</div>
                  <div className="mt-1 text-base font-semibold text-gray-900">{alert.event_title}</div>
                  <div className="mt-1 text-sm text-ws-muted">
                    {alert.client.name} • {segmentLabel(alert.client.segment)} • {alert.client.risk_profile}
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between gap-2">
                  <ConfidencePill confidence={alert.confidence} />
                  <Button
                    type="button"
                    variant="secondary"
                    className="text-xs font-semibold rounded-full border border-purple-500 text-purple-700 bg-white hover:bg-purple-50 px-3 py-1 shadow-[0_0_0_1px_rgba(129,140,248,0.35)]"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId(alert.id);
                    }}
                  >
                    View brief
                  </Button>
                </div>
              </div>
            );
          })}
          {alerts.length > visibleCount && (
            <div className="pt-1">
              <Button
                type="button"
                variant="secondary"
                className="w-full text-xs"
                onClick={() =>
                  setVisibleCount((count) => Math.min(count + 5, alerts.length))
                }
              >
                Load more ({alerts.length - visibleCount} more)
              </Button>
            </div>
          )}
        </div>

        <div
          className={`card p-4 space-y-4 ${
            selected?.priority === "HIGH"
              ? "border-red-200 bg-red-50"
              : selected?.priority === "MEDIUM"
                ? "border-amber-200 bg-amber-50"
                : selected?.priority === "LOW"
                  ? "border-emerald-200 bg-emerald-50"
                  : ""
          }`}
        >
          {!selected ? (
            <div className="space-y-2 text-center md:text-left">
              <div className="flex md:inline-flex justify-center md:justify-start">
                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-dashed border-gray-300 text-gray-400">
                  <svg
                    aria-hidden="true"
                    className="h-5 w-5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M8 3.5h6.2L19 8.3V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 7 19V5a1.5 1.5 0 0 1 1-1.4Z" />
                    <path d="M14 3.5V8h4.5" />
                    <path d="M10 11h4" />
                    <path d="M10 14h4" />
                  </svg>
                </div>
              </div>
              <div className="text-sm font-semibold text-gray-900">No brief selected</div>
              <div className="text-xs text-ws-muted">
                Select a priority item to view the detailed risk brief.
              </div>
            </div>
          ) : (
            <>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="page-title">Risk brief</div>
                  <PriorityPill priority={selected.priority} />
                </div>
                <div className="text-sm font-medium text-gray-900">{selected.portfolio.name}</div>
                <div className="page-subtitle">{selected.event_title}</div>
                <div className="mt-1 text-xs text-ws-muted">
                  {selected.client.name} • {segmentLabel(selected.client.segment)} •{" "}
                  {selected.client.risk_profile}
                </div>
              </div>

              <div className="rounded-lg border bg-white/80 p-3 space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                  AI confidence
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="text-sm text-gray-900">Model confidence score</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {selected.confidence.toFixed(0)}%
                  </div>
                </div>
                <div className="mt-2 h-2 rounded-full bg-gray-200">
                  <div
                    className={`h-2 rounded-full ${
                      selected.priority === "HIGH"
                        ? "bg-red-400"
                        : selected.priority === "MEDIUM"
                          ? "bg-amber-400"
                          : "bg-emerald-400"
                    }`}
                    style={{ width: `${Math.max(4, Math.min(100, selected.confidence))}%` }}
                  />
                </div>
              </div>

              {detailError && (
                <div className="rounded-md border border-red-200 bg-red-50 p-2 text-[11px] text-red-700">
                  Unable to load AI details for this alert. {detailError}
                </div>
              )}

              {detailLoading && !detailError && (
                <div className="rounded-md border border-ws-border bg-white/80 p-2 text-[11px] text-ws-muted">
                  Loading AI summary and client profile…
                </div>
              )}

              {selectedDetail && !detailLoading && !detailError && (
                <div className="space-y-3 text-xs">
                  <div className="space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-ws-muted">
                      Event
                    </div>
                    <div className="text-gray-900">{selectedDetail.event_title}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-ws-muted">
                      AI summary
                    </div>
                    <p className="text-gray-800">{selectedDetail.summary}</p>
                  </div>
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-2 space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                      Priority justification
                    </div>
                    <p className="text-[11px] text-amber-900">
                      Ranked with {selectedDetail.priority.toLowerCase()} priority based on
                      concentration {selectedDetail.concentration_score.toFixed(1)}, drift{" "}
                      {selectedDetail.drift_score.toFixed(1)}, and volatility{" "}
                      {selectedDetail.volatility_proxy.toFixed(1)}. Combined risk score{" "}
                      {selectedDetail.risk_score.toFixed(1)} / 10.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="text-[11px] font-semibold text-gray-900">AI reasoning</div>
                      <div className="text-[10px] text-ws-muted">AI-generated reasoning</div>
                    </div>
                    <ol className="space-y-1 text-[11px] text-gray-800">
                      {selectedDetail.reasoning_bullets.map((bullet, idx) => (
                        <li key={`${idx}-${bullet}`} className="flex gap-2">
                          <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-medium text-gray-700">
                            {idx + 1}
                          </span>
                          <span>{bullet}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="rounded-md border border-ws-border bg-white p-2 space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-ws-muted">
                      Client profile
                    </div>
                    <div className="text-xs font-medium text-gray-900">
                      {selectedDetail.client.name}
                    </div>
                    {(() => {
                      const extras = buildClientProfileExtras(selectedDetail);
                      return (
                        <dl className="mt-1 space-y-0.5 text-[11px] text-gray-800">
                          <div className="flex justify-between gap-3">
                            <dt className="text-ws-muted">Risk tolerance</dt>
                            <dd className="text-gray-900">
                              {selectedDetail.client.risk_profile}
                            </dd>
                          </div>
                          <div className="flex justify-between gap-3">
                            <dt className="text-ws-muted">Investment horizon</dt>
                            <dd className="text-gray-900">{extras.investmentHorizon}</dd>
                          </div>
                          <div className="flex justify-between gap-3">
                            <dt className="text-ws-muted">Last advisor review</dt>
                            <dd className="text-gray-900">{extras.lastAdvisorReviewLabel}</dd>
                          </div>
                          <div className="flex justify-between gap-3">
                            <dt className="text-ws-muted">Advisor</dt>
                            <dd className="text-gray-900">{extras.advisorName}</dd>
                          </div>
                        </dl>
                      );
                    })()}
                  </div>
                </div>
              )}

              <div>
                <div className="text-sm font-semibold text-gray-900">Queue events</div>
                <ul className="mt-2 space-y-2">
                  {buildEvents(selected).map((event) => (
                    <li key={`${selected.id}-${event.label}`} className="rounded-lg border border-ws-border p-2">
                      <div className="text-xs font-medium text-gray-600">{event.timestamp}</div>
                      <div className="text-sm font-medium text-gray-900">{event.label}</div>
                      <div className="text-xs text-ws-muted">{event.detail}</div>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ws-muted">
                  Operator history
                </div>
                <div className="mt-1 relative pl-3">
                  <div className="absolute left-0 top-0 bottom-0 w-px bg-gray-200" />
                  <ul className="space-y-1 text-xs text-gray-800">
                    {buildMiniHistory(selected).map((entry) => (
                      <li
                        key={`${selected.id}-${entry.dateLabel}-${entry.description}`}
                        className="relative flex gap-2"
                      >
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

              <div className="flex gap-2">
                <Button type="button" className="flex-1">
                  Mark as reviewed
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="flex-1 border-dashed"
                >
                  Schedule follow-up
                </Button>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1 border border-amber-400 text-amber-800 hover:bg-amber-50"
                >
                  Escalate to senior
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1 border border-red-400 text-red-700 hover:bg-red-50"
                >
                  False positive
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
