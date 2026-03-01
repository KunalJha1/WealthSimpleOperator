"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import type { AlertDetail, AlertSummary, FollowUpDraft, ReallocationPlan } from "../lib/types";
import {
  approveReallocationPlan,
  approveFollowUpDraft,
  createFollowUpDraft,
  executeReallocationPlan,
  fetchAlert,
  fetchFollowUpDraft,
  generateReallocationPlan,
  rejectFollowUpDraft,
  postAlertAction,
  queueReallocationPlan
} from "../lib/api";
import { PriorityPill } from "./StatusPills";
import { Button } from "./Buttons";
import { ClientDetailsPanel } from "./RiskBrief";
import { AlertTriangle, ArrowUpRight, UserRound, Settings2, FileText } from "lucide-react";

interface PriorityQueueProps {
  alerts: AlertSummary[];
  recentAlertIds?: number[];
  onAlertOpen?: (id: number) => void;
  onAlertAction?: (payload: {
    id: number;
    action: "reviewed" | "escalate" | "false_positive";
    previousStatus: string;
    updated: AlertDetail;
  }) => void;
  onFollowUpDraftEvent?: (payload: {
    type: "created" | "approved" | "rejected";
    draft: FollowUpDraft;
  }) => void;
}

type ClientProfileExtras = {
  investmentHorizon: string;
  lastAdvisorReviewLabel: string;
  advisorName: string;
};

type ChangeRow = {
  label: string;
  from: string;
  to: string;
};

function segmentLabel(segment: string): string {
  if (segment === "HNW") return "High Net Worth";
  return segment;
}

function formatPortfolioCode(id: number): string {
  const code = (10000 + id).toString();
  return `Portfolio PTF-${code}`;
}

function buildClientProfileExtras(detail: AlertDetail): ClientProfileExtras {
  const { client, id } = detail;

  let investmentHorizon = "Medium-term (7-15 years)";
  const risk = client.risk_profile.toLowerCase();
  if (risk.includes("conservative")) {
    investmentHorizon = "Short to medium-term (3-7 years)";
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

function parseMaybeNumber(value: string): number | null {
  const parsed = Number.parseFloat(value.replace(/[^0-9.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function capitalizeWords(str: string): string {
  return str.replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildChangeRows(detail: AlertDetail | null | undefined): ChangeRow[] {
  if (!detail) {
    return [];
  }

  const changeDetection = Array.isArray(detail.change_detection)
    ? detail.change_detection
    : [];

  if (changeDetection.length > 0) {
    return changeDetection.slice(0, 3).map((item) => ({
      label: item.metric.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      from: capitalizeWords(item.from),
      to: capitalizeWords(item.to)
    }));
  }

  const equityTo = Math.min(95, Math.max(5, Math.round(detail.portfolio.target_equity_pct + detail.concentration_score * 1.8)));
  const equityFrom = Math.max(0, equityTo - Math.round(Math.max(2, detail.drift_score)));
  const riskTo = detail.risk_score.toFixed(1);
  const riskFrom = Math.max(0, detail.risk_score - Math.max(0.6, detail.drift_score * 0.25)).toFixed(1);
  const priorityFrom =
    detail.priority === "HIGH" ? "MEDIUM" : detail.priority === "MEDIUM" ? "LOW" : "LOW";

  return [
    { label: "Equity Exposure", from: `${equityFrom}%`, to: `${equityTo}%` },
    { label: "Risk Score", from: riskFrom, to: riskTo },
    { label: "Priority Level", from: priorityFrom, to: detail.priority }
  ];
}

function minutesSince(value: string): number {
  const created = new Date(value).getTime();
  if (!Number.isFinite(created)) return 2;
  const diff = Date.now() - created;
  return Math.max(1, Math.round(diff / 60000));
}

export default function PriorityQueue({
  alerts,
  recentAlertIds = [],
  onAlertOpen,
  onAlertAction,
  onFollowUpDraftEvent
}: PriorityQueueProps) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(5);
  const [selectedDetail, setSelectedDetail] = useState<AlertDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRef = useRef<HTMLDivElement | null>(null);
  const [showClientDetails, setShowClientDetails] = useState(false);
  const [actionLoading, setActionLoading] = useState<null | "reviewed" | "escalate" | "false_positive">(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [followUpDraft, setFollowUpDraft] = useState<FollowUpDraft | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftActionLoading, setDraftActionLoading] = useState<null | "create" | "approve" | "reject" | "regenerate">(null);
  const [draftMessage, setDraftMessage] = useState<string | null>(null);
  const [portalReady, setPortalReady] = useState(false);
  const [reallocationPlan, setReallocationPlan] = useState<ReallocationPlan | null>(null);
  const [reallocationLoading, setReallocationLoading] = useState(false);
  const [planActionLoading, setPlanActionLoading] = useState<null | "queue" | "approve" | "execute">(null);
  const [planMessage, setPlanMessage] = useState<string | null>(null);

  const selected = useMemo(
    () => alerts.find((a) => a.id === selectedId) ?? null,
    [alerts, selectedId]
  );

  const visibleAlerts = useMemo(
    () => alerts.slice(0, visibleCount),
    [alerts, visibleCount]
  );
  const recentSet = useMemo(() => new Set(recentAlertIds), [recentAlertIds]);

  function openAlert(id: number) {
    setSelectedId(id);
    onAlertOpen?.(id);
  }

  useEffect(() => {
    if (selectedId == null) {
      setSelectedDetail(null);
      setDetailError(null);
      setShowClientDetails(false);
      setActionMessage(null);
      setFollowUpDraft(null);
      setDraftMessage(null);
      setReallocationPlan(null);
      setReallocationLoading(false);
      setPlanActionLoading(null);
      setPlanMessage(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    setReallocationPlan(null);
    setReallocationLoading(false);
    setPlanActionLoading(null);
    setPlanMessage(null);

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

    fetchFollowUpDraft(selectedId)
      .then((response) => {
        if (!cancelled) {
          setFollowUpDraft(response.draft);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFollowUpDraft(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    setPortalReady(true);
  }, []);

  async function handleCreateFollowUpDraft(forceRegenerate = false) {
    if (!selected) return;
    setDraftActionLoading(forceRegenerate ? "regenerate" : "create");
    setDraftLoading(true);
    setDraftMessage(null);
    try {
      const response = await createFollowUpDraft(selected.id, { forceRegenerate });
      setFollowUpDraft(response.draft);
      setDraftMessage(response.message);
      onFollowUpDraftEvent?.({ type: "created", draft: response.draft });
    } catch (e) {
      setDraftMessage((e as Error).message);
    } finally {
      setDraftLoading(false);
      setDraftActionLoading(null);
    }
  }

  async function handleApproveFollowUpDraft() {
    if (!followUpDraft) return;
    setDraftActionLoading("approve");
    setDraftMessage(null);
    try {
      const response = await approveFollowUpDraft(followUpDraft.id);
      setFollowUpDraft(response.draft);
      setDraftMessage(response.message);
      onFollowUpDraftEvent?.({ type: "approved", draft: response.draft });
    } catch (e) {
      setDraftMessage((e as Error).message);
    } finally {
      setDraftActionLoading(null);
    }
  }

  async function handleRejectFollowUpDraft() {
    if (!followUpDraft) return;
    setDraftActionLoading("reject");
    setDraftMessage(null);
    try {
      const response = await rejectFollowUpDraft(followUpDraft.id, "Advisor requested edits");
      setFollowUpDraft(response.draft);
      setDraftMessage(response.message);
      onFollowUpDraftEvent?.({ type: "rejected", draft: response.draft });
    } catch (e) {
      setDraftMessage((e as Error).message);
    } finally {
      setDraftActionLoading(null);
    }
  }

  async function handleAlertAction(action: "reviewed" | "escalate" | "false_positive") {
    if (!selected) return;

    const previousStatus = selectedDetail?.status ?? selected.status;
    setActionLoading(action);
    setActionMessage(null);
    try {
      const response = await postAlertAction(selected.id, action);
      const patchedDetail: AlertDetail = {
        ...response.alert,
        change_detection: [
          {
            metric: "status",
            from: previousStatus,
            to: response.alert.status
          },
          ...response.alert.change_detection
        ]
      };
      setSelectedDetail(patchedDetail);
      setActionMessage(response.message);
      onAlertAction?.({
        id: selected.id,
        action,
        previousStatus,
        updated: patchedDetail
      });
      setSelectedId(null);
    } catch (e) {
      setActionMessage((e as Error).message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleGenerateReallocationPlan() {
    if (!selectedDetail) return;
    setReallocationLoading(true);
    setPlanMessage(null);
    try {
      const plan = await generateReallocationPlan(selectedDetail.id, 266000);
      setReallocationPlan(plan);
      setPlanMessage("AI plan generated. Review assumptions, then queue for execution prep.");
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setReallocationLoading(false);
    }
  }

  async function handleQueuePlan() {
    if (!reallocationPlan) return;
    setPlanActionLoading("queue");
    setPlanMessage(null);
    try {
      const updated = await queueReallocationPlan(reallocationPlan.plan_id);
      setReallocationPlan(updated);
      setPlanMessage("Plan queued. Human approval is now required.");
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  async function handleApprovePlan() {
    if (!reallocationPlan) return;
    setPlanActionLoading("approve");
    setPlanMessage(null);
    try {
      const updated = await approveReallocationPlan(reallocationPlan.plan_id);
      setReallocationPlan(updated);
      setPlanMessage("Human approval recorded. Plan is ready for simulated execution.");
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  async function handleExecutePlan() {
    if (!reallocationPlan) return;
    setPlanActionLoading("execute");
    setPlanMessage(null);
    try {
      const updated = await executeReallocationPlan(reallocationPlan.plan_id);
      setReallocationPlan(updated);
      setPlanMessage(`Execution simulated and logged (${updated.execution_reference ?? "no reference"}).`);
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  // When an alert is selected, scroll the risk brief panel into view
  useEffect(() => {
    if (!selectedId || !detailRef.current) return;
    detailRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
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

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,0.8fr)] gap-3">
        <div className="space-y-3">
          {visibleAlerts.map((alert) => {
            const active = selected?.id === alert.id;
            const isRecent = recentSet.has(alert.id);
            const priorityAccent =
              alert.priority === "HIGH"
                ? "border-red-500 shadow-[0_0_0_1px_rgba(248,113,113,0.45)]"
                : alert.priority === "MEDIUM"
                  ? "border-amber-400 shadow-[0_0_0_1px_rgba(251,191,36,0.35)]"
                  : "border-emerald-400 shadow-[0_0_0_1px_rgba(52,211,153,0.35)]";

            return (
              <div
                key={`${alert.id}-${alert.portfolio.id}`}
                role="button"
                tabIndex={0}
                className={`w-full text-left card p-4 cursor-pointer transition-all duration-300 ${
                  active ? `${priorityAccent} bg-gray-50` : "hover:border-gray-400"
                } ${
                  isRecent
                    ? "border-sky-300 bg-sky-50/40 ring-1 ring-sky-200/80 animate-pulse"
                    : ""
                }`}
                onClick={() => openAlert(alert.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openAlert(alert.id);
                  }
                }}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <PriorityPill priority={alert.priority} />
                  {isRecent && (
                    <div className="text-xs font-semibold px-2 py-1 rounded-full border border-sky-200 bg-sky-100 text-sky-700">
                      RECENT
                    </div>
                  )}
                  {alert.scenario && (
                    <div className="text-xs font-semibold px-2 py-1 rounded-full bg-blue-100 text-blue-700">
                      {alert.scenario.replace(/_/g, " ")}
                    </div>
                  )}
                  <div className="text-sm font-medium text-gray-900">
                    {formatPortfolioCode(alert.portfolio.id)}
                  </div>
                  <div className="text-sm text-gray-600">{alert.client.name}</div>
                </div>

                <div className="mt-3">
                  <div className="mt-1 text-base font-semibold text-gray-900">{alert.event_title}</div>
                  <div className="mt-3 text-sm text-gray-700 leading-6">{alert.summary}</div>
                </div>

                <div className="mt-4">
                  <Button
                    type="button"
                    className="w-full text-sm font-semibold"
                    onClick={(e) => {
                      e.stopPropagation();
                      openAlert(alert.id);
                    }}
                  >
                    View Brief
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
          ref={detailRef}
          className="card p-4 space-y-4 self-start border-gray-200 bg-gray-50"
        >
          <div key={selected?.id ?? "empty-brief"} className="brief-enter">
          {!selected ? (
            <div className="flex flex-col items-center justify-center space-y-3 py-10 text-center max-w-sm mx-auto">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-gray-400">
                <svg
                  aria-hidden="true"
                  className="h-6 w-6"
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
              <div className="text-base font-semibold text-gray-900">No Brief Selected</div>
              <div className="text-sm text-ws-muted">
                Select a priority item to view the detailed risk brief.
              </div>
            </div>
          ) : (
            <>
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-xl font-semibold leading-none text-gray-900">Risk Brief</div>
                    <PriorityPill priority={selected.priority} />
                  </div>
                  <button
                    type="button"
                    aria-label="Close risk brief"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-400 hover:bg-white hover:text-gray-600"
                    onClick={() => setSelectedId(null)}
                  >
                    <svg
                      aria-hidden="true"
                      className="h-4 w-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M18 6 6 18" />
                      <path d="m6 6 12 12" />
                    </svg>
                  </button>
                </div>
                <div className="space-y-1.5 pb-2">
                  <div className="text-base font-semibold text-gray-900">{selected.portfolio.name}</div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-gray-600">
                    {formatPortfolioCode(selected.portfolio.id)}
                  </div>
                  <div className="text-sm text-gray-700">{selected.event_title}</div>
                  <div className="text-xs text-gray-600">
                    {selected.client.name} • {segmentLabel(selected.client.segment)} • {selected.client.risk_profile}
                  </div>
                </div>
                <div className="rounded-xl bg-gradient-to-r from-blue-400 to-cyan-400 p-px overflow-hidden mt-1 mb-4">
                  <div className="rounded-[13px] bg-white px-4 py-1 pb-8">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-blue-800">
                        AI Confidence
                      </div>
                      <div className="text-2xl font-bold text-blue-700">
                        {selected.confidence.toFixed(0)}%
                      </div>
                    </div>
                    <div className="h-3 rounded-full bg-blue-100 overflow-hidden">
                      <div
                        className="h-3 rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-300"
                        style={{ width: `${Math.max(4, Math.min(100, selected.confidence))}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {detailError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 font-medium">
                  Unable to load AI details for this alert. {detailError}
                </div>
              )}

              {detailLoading && !detailError && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-600">
                  Loading AI summary and client profile...
                </div>
              )}

              {selectedDetail && !detailLoading && !detailError && (
                <div className="mt-2 space-y-4">
                  <div className="space-y-1.5">
                    <div className="text-base font-semibold text-gray-900">
                      Event
                    </div>
                    <div className="text-xs text-gray-700 leading-relaxed">
                      {selectedDetail.event_title}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <div className="text-base font-semibold text-gray-900">
                      AI Summary
                    </div>
                    <p className="text-xs text-gray-700 leading-relaxed">{selectedDetail.summary}</p>
                  </div>
                  <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 space-y-2">
                    <div className="text-sm font-semibold text-amber-900">
                      Priority Justification
                    </div>
                    <p className="text-xs text-amber-900 leading-relaxed">
                      Ranked with {selectedDetail.priority.toLowerCase()} priority based on
                      concentration {selectedDetail.concentration_score.toFixed(1)}, drift{" "}
                      {selectedDetail.drift_score.toFixed(1)}, and volatility{" "}
                      {selectedDetail.volatility_proxy.toFixed(1)}. Combined risk score{" "}
                      {selectedDetail.risk_score.toFixed(1)} / 10.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-base font-semibold text-gray-900">AI Reasoning</div>
                      <div className="text-xs text-gray-500">AI-generated</div>
                    </div>
                    <ol className="space-y-1.5 text-xs text-gray-800">
                      {selectedDetail.reasoning_bullets.map((bullet, idx) => (
                        <li key={`${idx}-${bullet}`} className="flex gap-2">
                          <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-medium text-gray-700">
                            {idx + 1}
                          </span>
                          <span className="pt-0.5">{bullet}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 mt-2">
                    <div className="text-base font-semibold text-gray-900">Client Profile</div>
                    {(() => {
                      const extras = buildClientProfileExtras(selectedDetail);
                      return (
                        <dl className="space-y-2.5 text-xs">
                          <div className="flex justify-between gap-4">
                            <dt className="text-gray-600 font-semibold">Name</dt>
                            <dd className="font-semibold text-gray-900 text-right">
                              {selectedDetail.client.name}
                            </dd>
                          </div>
                          <div className="flex justify-between gap-4">
                            <dt className="text-gray-600 font-semibold">Risk Tolerance</dt>
                            <dd className="text-gray-900 text-right">
                              {selectedDetail.client.risk_profile}
                            </dd>
                          </div>
                          <div className="flex justify-between gap-4">
                            <dt className="text-gray-600 font-semibold">Investment Horizon</dt>
                            <dd className="text-gray-900 text-right">{extras.investmentHorizon}</dd>
                          </div>
                          <div className="flex justify-between gap-4">
                            <dt className="text-gray-600 font-semibold">Last Advisor Review</dt>
                            <dd className="text-gray-900 text-right">{extras.lastAdvisorReviewLabel}</dd>
                          </div>
                          <div className="flex justify-between gap-4">
                            <dt className="text-gray-600 font-semibold">Advisor Assigned</dt>
                            <dd className="text-gray-900 text-right">{extras.advisorName}</dd>
                          </div>
                        </dl>
                      );
                    })()}
                    <div className="pt-2">
                      <Button
                        type="button"
                        variant="secondary"
                        className="w-full text-xs px-3 py-1.5 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50"
                        onClick={() => setShowClientDetails(true)}
                      >
                        <UserRound className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                        View Client Details
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {selectedDetail && (
                <div className="mt-6"></div>
              )}

              {selectedDetail ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-4">
                    <div className="text-base font-semibold text-gray-900">Change Detection</div>
                    <div className="mt-3 space-y-2.5 text-xs">
                      {buildChangeRows(selectedDetail).map((row, idx) => {
                        const fromNum = parseMaybeNumber(row.from);
                        const toNum = parseMaybeNumber(row.to);
                        const movedUp = fromNum != null && toNum != null ? toNum > fromNum : true;
                        return (
                          <div key={`${idx}-${row.label}`} className="flex items-center justify-between gap-3">
                            <div className="text-gray-700 font-medium">{row.label}</div>
                            <div className="flex items-center gap-2 font-medium">
                              <span className="text-gray-600">{row.from}</span>
                              <span className="text-gray-400">{"->"}</span>
                              <span className={movedUp ? "text-orange-500" : "text-emerald-600"}>
                                {row.to}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>


                  <div className="border-t border-gray-200 pt-3 mb-2">
                    <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 uppercase tracking-wider">
                      Human Review Required
                    </span>
                  </div>

                </div>
              ) : (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-600">
                  Loading change detection and learning metrics...
                </div>
              )}

              {actionMessage && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
                  {actionMessage}
                </div>
              )}

              <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-base font-semibold text-gray-900">Proposed Client Email</div>
                  {followUpDraft && (
                    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      followUpDraft.status === "PENDING_APPROVAL"
                        ? "border-amber-200 bg-amber-50 text-amber-700"
                        : followUpDraft.status === "APPROVED_READY"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-gray-200 bg-gray-50 text-gray-600"
                    }`}>
                      {followUpDraft.status === "PENDING_APPROVAL"
                        ? "Pending Approval"
                        : followUpDraft.status === "APPROVED_READY"
                          ? "Approved Ready"
                          : "Rejected"}
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-700">
                  A proposed email which can be sent after advisor review and approval.
                </div>
                {followUpDraft ? (
                  <div className="space-y-2.5 text-xs">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-gray-600">To</div>
                      <div className="text-gray-900 mt-1">{followUpDraft.recipient_email}</div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-gray-600">Subject</div>
                      <div className="text-gray-900 mt-1">{followUpDraft.subject}</div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-gray-600">Body</div>
                      <div className="whitespace-pre-wrap rounded-md border border-gray-200 bg-white p-3 text-xs text-gray-800 mt-1">
                        {followUpDraft.body}
                      </div>
                    </div>
                    <div className="flex gap-2 pt-2">
                      <Button
                        type="button"
                        variant="secondary"
                        className="flex-1 text-xs px-3 py-1.5 border border-gray-300"
                        disabled={draftActionLoading !== null}
                        onClick={() => void handleCreateFollowUpDraft(true)}
                      >
                        Regenerate
                      </Button>
                      {followUpDraft.status === "PENDING_APPROVAL" && (
                        <>
                          <Button
                            type="button"
                            className="flex-1 text-xs px-3 py-1.5 bg-emerald-600 border-emerald-700 text-white hover:bg-emerald-700"
                            disabled={draftActionLoading !== null}
                            onClick={() => void handleApproveFollowUpDraft()}
                          >
                            Approve
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            className="flex-1 text-xs px-3 py-1.5 border-2 border-red-600 text-red-600 hover:bg-red-50"
                            disabled={draftActionLoading !== null}
                            onClick={() => void handleRejectFollowUpDraft()}
                          >
                            Reject
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-gray-600">
                    No follow-up draft yet. Use Schedule Follow-up to generate one.
                  </div>
                )}
                {(draftLoading || draftActionLoading !== null) && (
                  <div className="text-xs text-gray-600">Agent working on follow-up draft...</div>
                )}
                {draftMessage && (
                  <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-700">
                    {draftMessage}
                  </div>
                )}
              </div>

              <div className="border-t border-gray-200 pt-4"></div>

              <div className="space-y-3">
                <div className="flex gap-3">
                  <Button
                    type="button"
                    className="flex-1 text-sm py-2.5"
                    disabled={actionLoading !== null || draftActionLoading !== null}
                    onClick={() => void handleAlertAction("reviewed")}
                  >
                    Mark as Reviewed
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    className="flex-1 text-sm py-2.5 border border-gray-300 bg-white hover:bg-gray-50"
                    disabled={actionLoading !== null || draftActionLoading !== null}
                    onClick={() => void handleCreateFollowUpDraft(false)}
                  >
                    Schedule Follow-up
                  </Button>
                </div>
                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="flex-1 text-sm py-2.5 !border-2 !border-amber-400 !bg-white !text-amber-700 hover:!bg-amber-50"
                    disabled={actionLoading !== null || draftActionLoading !== null}
                    onClick={() => void handleAlertAction("escalate")}
                  >
                    <ArrowUpRight className="mr-1.5 h-4 w-4" aria-hidden="true" />
                    Escalate to Senior
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="flex-1 text-sm py-2.5 !border-2 !border-red-400 !bg-white !text-red-600 hover:!bg-red-50"
                    disabled={actionLoading !== null || draftActionLoading !== null}
                    onClick={() => void handleAlertAction("false_positive")}
                  >
                    <AlertTriangle className="mr-1.5 h-4 w-4" aria-hidden="true" />
                    False Positive
                  </Button>
                </div>
              </div>

              {selectedDetail && (
                <div className="border-t border-gray-200 pt-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-gray-600 mb-2">
                    Open Client In
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      className="text-xs px-3 py-2 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50"
                      onClick={() => router.push(`/auto-reallocation?portfolio=${selectedDetail.portfolio.id}`)}
                    >
                      <Settings2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                      Reallocation
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      className="text-xs px-3 py-2 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50"
                      onClick={() => router.push(`/meeting-notes?portfolio=${selectedDetail.portfolio.id}`)}
                    >
                      <FileText className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                      Meeting Notes
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
          </div>
        </div>
      </div>
      {portalReady && showClientDetails && selectedDetail
        ? createPortal(
            <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/55 backdrop-blur-sm p-4">
              <div className="relative w-full max-w-5xl max-h-[90vh] overflow-y-auto scrollbar-hidden rounded-2xl bg-white shadow-2xl">
                <div className="flex items-center justify-between border-b border-ws-border px-5 py-3 md:px-6 md:py-4">
                  <div className="space-y-0.5">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                      Client details
                    </div>
                    <div className="text-sm font-medium text-gray-900">
                      {selectedDetail.client.name} -{" "}
                      {formatPortfolioCode(selectedDetail.portfolio.id)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="rounded-full border border-ws-border bg-white px-4 py-1.5 text-xs font-medium text-ws-muted shadow-sm hover:bg-gray-50"
                    onClick={() => setShowClientDetails(false)}
                  >
                    Close
                  </button>
                </div>
                <div className="p-5 md:p-6">
                  <ClientDetailsPanel alert={selectedDetail} />
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </section>
  );
}
