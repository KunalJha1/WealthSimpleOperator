"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { AlertSummary, AlertDetail, ReallocationPlan, RebalancingSuggestion } from "../../lib/types";
import {
  approveReallocationPlan,
  executeReallocationPlan,
  fetchAlerts,
  fetchAlert,
  fetchRebalancingSuggestion,
  generateReallocationPlan,
  queueReallocationPlan
} from "../../lib/api";
import { PriorityPill, StatusPill } from "../../components/StatusPills";
import { RebalancingSuggestionPanel } from "../../components/RebalancingSuggestion";
import {
  AlertTriangle,
  TrendingDown,
  Target,
  CheckCircle2,
  DollarSign,
  Zap,
  BarChart3
} from "lucide-react";
import { formatCurrency } from "../../lib/utils";


export default function AutoReallocationPage() {
  const searchParams = useSearchParams();
  const portfolioParam = searchParams.get("portfolio");

  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(
    portfolioParam ? parseInt(portfolioParam, 10) : null
  );

  const [plan, setPlan] = useState<ReallocationPlan | null>(null);
  const [planMessage, setPlanMessage] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planActionLoading, setPlanActionLoading] = useState<"queue" | "approve" | "execute" | null>(null);
  const [allocationSnapshot, setAllocationSnapshot] = useState<RebalancingSuggestion | null>(null);
  const [allocationLoading, setAllocationLoading] = useState(false);
  const [allocationError, setAllocationError] = useState<string | null>(null);
  const [alertDetail, setAlertDetail] = useState<AlertDetail | null>(null);
  const [alertDetailLoading, setAlertDetailLoading] = useState(false);
  const [targetCashAmount, setTargetCashAmount] = useState(266000);

  const selectedAlert = useMemo(
    () => alerts.find((a) => a.id === selectedAlertId) ?? null,
    [alerts, selectedAlertId]
  );

  useEffect(() => {
    async function loadAlerts() {
      setLoadingAlerts(true);
      setAlertsError(null);
      try {
        const params = new URLSearchParams();
        params.set("limit", "100");
        const data = await fetchAlerts(params);
        setAlerts(data.items);
        if (data.items.length > 0) {
          setSelectedAlertId(data.items[0].id);
        }
      } catch (e) {
        setAlertsError((e as Error).message);
      } finally {
        setLoadingAlerts(false);
      }
    }

    void loadAlerts();
  }, []);

  // Clear plan when alert changes
  useEffect(() => {
    setPlan(null);
    setPlanMessage(null);
  }, [selectedAlertId]);

  // Auto-generate plan when alert and allocation data are ready
  useEffect(() => {
    async function autoGeneratePlan() {
      if (!selectedAlertId || !allocationSnapshot || plan) return;
      setPlanLoading(true);
      try {
        const generated = await generateReallocationPlan(selectedAlertId, targetCashAmount);
        setPlan(generated);
      } catch (e) {
        // Silently fail on auto-generation, user can click generate manually
        console.error("Auto-generation failed:", e);
      } finally {
        setPlanLoading(false);
      }
    }

    void autoGeneratePlan();
  }, [selectedAlertId, allocationSnapshot]);

  // Auto-move to next alert when current plan is executed
  useEffect(() => {
    if (plan && plan.status === "EXECUTED" && selectedAlertId) {
      const currentIndex = alerts.findIndex((a) => a.id === selectedAlertId);
      const nextAlert = alerts.find((a, idx) => idx > currentIndex && a.id !== selectedAlertId);

      if (nextAlert) {
        setTimeout(() => {
          setSelectedAlertId(nextAlert.id);
        }, 1500);
      }
    }
  }, [plan?.status, selectedAlertId, alerts]);

  useEffect(() => {
    async function loadAllocationSnapshot() {
      if (!selectedAlertId) {
        setAllocationSnapshot(null);
        setAllocationError(null);
        return;
      }
      setAllocationLoading(true);
      setAllocationError(null);
      try {
        const snapshot = await fetchRebalancingSuggestion(selectedAlertId);
        setAllocationSnapshot(snapshot);
      } catch (e) {
        setAllocationSnapshot(null);
        setAllocationError((e as Error).message);
      } finally {
        setAllocationLoading(false);
      }
    }

    void loadAllocationSnapshot();
  }, [selectedAlertId]);

  // Load full alert detail (with risk scores) for Risk Profile card
  useEffect(() => {
    async function loadAlertDetail() {
      if (!selectedAlertId) {
        setAlertDetail(null);
        return;
      }
      setAlertDetailLoading(true);
      try {
        const detail = await fetchAlert(selectedAlertId);
        setAlertDetail(detail);
      } catch (e) {
        setAlertDetail(null);
      } finally {
        setAlertDetailLoading(false);
      }
    }

    void loadAlertDetail();
  }, [selectedAlertId]);

  const allocationProjection = useMemo(() => {
    if (!selectedAlert || !allocationSnapshot) {
      return null;
    }

    const totalValue = Math.max(1, selectedAlert.portfolio.total_value);
    const currentEquityAmount = (allocationSnapshot.current_equity_pct / 100) * totalValue;
    const currentFixedIncomeAmount = (allocationSnapshot.current_fixed_income_pct / 100) * totalValue;
    const currentCashAmount = (allocationSnapshot.current_cash_pct / 100) * totalValue;

    const soldEquity = plan
      ? plan.trades
          .filter((t) => t.asset_class === "Equity")
          .reduce((sum, t) => sum + t.amount, 0)
      : 0;
    const soldFixedIncome = plan
      ? plan.trades
          .filter((t) => t.asset_class === "Fixed Income")
          .reduce((sum, t) => sum + t.amount, 0)
      : 0;
    const soldTotal = soldEquity + soldFixedIncome;

    const projectedEquityAmount = Math.max(0, currentEquityAmount - soldEquity);
    const projectedFixedIncomeAmount = Math.max(0, currentFixedIncomeAmount - soldFixedIncome);
    const projectedCashAmount = currentCashAmount + soldTotal;

    const pct = (value: number) => Number(((value / totalValue) * 100).toFixed(1));

    return {
      current: {
        equity: Number(allocationSnapshot.current_equity_pct.toFixed(1)),
        fixedIncome: Number(allocationSnapshot.current_fixed_income_pct.toFixed(1)),
        cash: Number(allocationSnapshot.current_cash_pct.toFixed(1))
      },
      projected: {
        equity: pct(projectedEquityAmount),
        fixedIncome: pct(projectedFixedIncomeAmount),
        cash: pct(projectedCashAmount)
      },
      soldEquity,
      soldFixedIncome,
      soldTotal
    };
  }, [selectedAlert, allocationSnapshot, plan]);

  async function handleGeneratePlan() {
    if (!selectedAlertId) return;
    setPlanLoading(true);
    setPlanMessage(null);
    try {
      const next = await generateReallocationPlan(selectedAlertId, targetCashAmount);
      setPlan(next);
      setPlanMessage("AI plan generated. Queue it for approval workflow.");
    } catch (e) {
      const message = (e as Error).message;
      if (message.includes("404")) {
        setPlanMessage("Plan generation failed: the selected alert may no longer exist. Refresh alerts and try again.");
      } else {
        setPlanMessage(message);
      }
    } finally {
      setPlanLoading(false);
    }
  }

  async function handleQueuePlan() {
    if (!plan) return;
    setPlanActionLoading("queue");
    setPlanMessage(null);
    try {
      const next = await queueReallocationPlan(plan.plan_id);
      setPlan(next);
      setPlanMessage("Plan queued. Human approval required.");
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  async function handleApprovePlan() {
    if (!plan) return;
    setPlanActionLoading("approve");
    setPlanMessage(null);
    try {
      const next = await approveReallocationPlan(plan.plan_id);
      setPlan(next);
      setPlanMessage("Human approval recorded. Plan is ready for simulated execution.");
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  async function handleExecutePlan() {
    if (!plan) return;
    setPlanActionLoading("execute");
    setPlanMessage(null);
    try {
      const next = await executeReallocationPlan(plan.plan_id);
      setPlan(next);
      setPlanMessage(`Execution simulated and audited (${next.execution_reference ?? "no reference"}).`);
    } catch (e) {
      setPlanMessage((e as Error).message);
    } finally {
      setPlanActionLoading(null);
    }
  }

  return (
    <section className="space-y-5">
      <header className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-gradient-to-br from-orange-100 to-orange-50 border border-orange-200">
            <Zap size={24} className="text-orange-600" />
          </div>
          <div>
            <h1 className="page-title">AI Auto-Reallocation Engine</h1>
            <p className="text-xs text-gray-600 font-semibold tracking-wide">WEALTH ADVISOR TOOL</p>
          </div>
        </div>
        <p className="page-subtitle max-w-4xl">
          Intelligent portfolio reallocation workflow for wealth advisors. AI analyzes risk, proposes tax-aware trades,
          and generates client communication—all pending human review and approval.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,2fr)]">
        <div className="card p-4 space-y-3 flex flex-col">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-500" />
              Active Alerts
            </div>
            <div className="inline-flex items-center justify-center rounded-full bg-ws-ink text-white text-xs font-semibold w-6 h-6">
              {alerts.length}
            </div>
          </div>

          {loadingAlerts && <div className="text-sm text-ws-muted">Loading alerts...</div>}
          {alertsError && (
            <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              {alertsError}
            </div>
          )}

          {!loadingAlerts && !alertsError && alerts.length === 0 && (
            <div className="rounded border border-gray-200 bg-gray-50 p-3 text-sm text-ws-muted">
              No alerts available yet. Run the operator first.
            </div>
          )}

          <div className="space-y-2 flex-1 overflow-hidden">
            <style jsx>{`
              .scrollbar-hide {
                -ms-overflow-style: none;
                scrollbar-width: none;
              }
              .scrollbar-hide::-webkit-scrollbar {
                display: none;
              }
            `}</style>
            <div className="scrollbar-hide space-y-2 overflow-y-auto max-h-[620px]">
              {alerts.map((alert) => {
                const active = alert.id === selectedAlertId;
                const isExecuted = Boolean(active && plan && plan.status === "EXECUTED");
                return (
                  <button
                    key={alert.id}
                    type="button"
                    onClick={() => setSelectedAlertId(alert.id)}
                    disabled={isExecuted}
                    className={`w-full rounded-lg border-2 p-3 text-left transition ${
                      isExecuted
                        ? 'border-gray-200 bg-gray-100 opacity-50 cursor-not-allowed'
                        : active
                        ? 'border-ws-ink bg-gradient-to-r from-ws-ink/5 to-transparent shadow-md'
                        : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <PriorityPill priority={alert.priority} />
                      <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold ${
                        isExecuted
                          ? 'bg-gray-200 text-gray-500'
                          : active
                          ? 'bg-ws-ink/10 text-ws-ink'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {isExecuted ? (
                          <CheckCircle2 size={12} />
                        ) : (
                          <Zap size={12} />
                        )}
                      </div>
                    </div>
                    <div className={`mt-2 text-sm font-semibold line-clamp-1 ${
                      isExecuted ? 'text-gray-500' : 'text-gray-900'
                    }`}>
                      {alert.event_title}
                    </div>
                    <div className={`mt-1 text-xs line-clamp-1 ${
                      isExecuted ? 'text-gray-400' : 'text-gray-600'
                    }`}>
                      {alert.client.name}
                    </div>
                    <div className={`mt-1 text-xs ${
                      isExecuted ? 'text-gray-400' : 'text-gray-500'
                    }`}>
                      {alert.portfolio.name} • {formatCurrency(alert.portfolio.total_value)}
                    </div>
                    {isExecuted && (
                      <div className="mt-2 flex items-center gap-1 text-xs text-emerald-600 font-semibold">
                        <CheckCircle2 size={14} />
                        Executed
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-3 flex flex-col">
          {selectedAlert ? (
            <>
              {plan && plan.status === "EXECUTED" && (
                <div className="card rounded-lg border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-emerald-100 p-4 space-y-3 text-center">
                  <div className="flex justify-center">
                    <div className="p-3 rounded-full bg-emerald-200 text-emerald-600">
                      <CheckCircle2 size={32} />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-emerald-900">Plan Executed Successfully</h3>
                    <p className="text-sm text-emerald-700 mt-1">
                      Reallocation has been executed and audited. Moving to next alert...
                    </p>
                  </div>
                </div>
              )}

              {/* CONTEXT CARD */}
              <div className={`card p-4 space-y-3 transition ${plan?.status === "EXECUTED" ? "opacity-50" : ""}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <h2 className="text-lg font-bold text-gray-900">{selectedAlert.client.name}</h2>
                    <p className="text-sm text-gray-600 mt-1">{selectedAlert.portfolio.name}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Portfolio Value: <span className="font-semibold text-gray-900">{formatCurrency(selectedAlert.portfolio.total_value)}</span>
                    </p>
                  </div>
                  <div className="text-right">
                    <PriorityPill priority={selectedAlert.priority} />
                    <StatusPill status={selectedAlert.status} />
                  </div>
                </div>
                <p className="text-xs text-gray-700 border-l-2 border-amber-300 pl-2 py-1">
                  {selectedAlert.summary}
                </p>
              </div>

              {/* RISK PROFILE CARD - Shows metrics that drive target cash calculation */}
              {!alertDetailLoading && alertDetail && selectedAlert && (
                <div className="card p-4 space-y-4 border-l-4 border-blue-500">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                      <BarChart3 size={16} className="text-blue-600" />
                      Risk Profile & Target Cash Analysis
                    </h3>
                    <p className="text-xs text-gray-600 mt-1">Metrics that determine your recommended cash target:</p>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {/* Concentration Score */}
                    <div className="rounded-lg bg-gradient-to-br from-red-50 to-red-100 border border-red-200 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs font-bold text-red-700 uppercase tracking-wider">Concentration</div>
                        <div className="text-lg font-bold text-red-900">{(alertDetail.concentration_score ?? 0).toFixed(1)}</div>
                      </div>
                      <div className="w-full bg-red-200 rounded-full h-2">
                        <div
                          className="bg-red-600 h-2 rounded-full"
                          style={{ width: `${Math.min(100, ((alertDetail.concentration_score ?? 0) / 10) * 100)}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-red-600 mt-1 font-semibold">
                        {(alertDetail.concentration_score ?? 0) > 7 ? "High - boost cash needed" : "Moderate"}
                      </div>
                    </div>

                    {/* Drift Score */}
                    <div className="rounded-lg bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs font-bold text-amber-700 uppercase tracking-wider">Drift</div>
                        <div className="text-lg font-bold text-amber-900">{(alertDetail.drift_score ?? 0).toFixed(1)}</div>
                      </div>
                      <div className="w-full bg-amber-200 rounded-full h-2">
                        <div
                          className="bg-amber-600 h-2 rounded-full"
                          style={{ width: `${Math.min(100, ((alertDetail.drift_score ?? 0) / 10) * 100)}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-amber-600 mt-1 font-semibold">
                        {(alertDetail.drift_score ?? 0) > 7 ? "High - rebalancing needed" : "Moderate"}
                      </div>
                    </div>

                    {/* Volatility */}
                    <div className="rounded-lg bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs font-bold text-orange-700 uppercase tracking-wider">Volatility</div>
                        <div className="text-lg font-bold text-orange-900">{(alertDetail.volatility_proxy ?? 0).toFixed(1)}%</div>
                      </div>
                      <div className="w-full bg-orange-200 rounded-full h-2">
                        <div
                          className="bg-orange-600 h-2 rounded-full"
                          style={{ width: `${Math.min(100, ((alertDetail.volatility_proxy ?? 0) / 25) * 100)}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-orange-600 mt-1 font-semibold">
                        {(alertDetail.volatility_proxy ?? 0) > 12 ? "High - buffer needed" : "Moderate"}
                      </div>
                    </div>
                  </div>

                  {/* Portfolio Allocation Flow */}
                  <div className="border-t border-gray-200 pt-4 space-y-3">
                    <div className="text-xs font-bold text-gray-700 uppercase tracking-wider">Portfolio Shift: Current → Target</div>

                    {/* Current State */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="text-[11px] font-semibold text-gray-600">Current Allocation</div>
                        <div className="text-[10px] text-gray-500">100%</div>
                      </div>
                      <div className="flex gap-1 h-6 rounded-lg overflow-hidden border border-gray-200 bg-white">
                        <div className="bg-blue-500 flex items-center justify-center"
                          style={{ width: `${Math.max(5, (parseFloat(selectedAlert.portfolio.target_equity_pct.toString()) * 0.7))}%` }}>
                          <span className="text-[8px] font-bold text-white">E</span>
                        </div>
                        <div className="bg-emerald-500 flex items-center justify-center"
                          style={{ width: `${Math.max(5, (parseFloat(selectedAlert.portfolio.target_fixed_income_pct.toString()) * 0.8))}%` }}>
                          <span className="text-[8px] font-bold text-white">F</span>
                        </div>
                        <div className="bg-amber-400 flex items-center justify-center"
                          style={{ width: `${Math.max(5, (parseFloat(selectedAlert.portfolio.target_cash_pct.toString()) * 0.3))}%` }}>
                          <span className="text-[8px] font-bold text-gray-800">C</span>
                        </div>
                      </div>
                    </div>

                    {/* Arrow */}
                    <div className="flex items-center justify-center py-1">
                      <div className="text-gray-400 text-sm">↓</div>
                    </div>

                    {/* Target State */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="text-[11px] font-semibold text-emerald-700">Target Allocation</div>
                        <div className="text-[10px] text-emerald-600">100%</div>
                      </div>
                      <div className="flex gap-1 h-6 rounded-lg overflow-hidden border border-emerald-300 bg-emerald-50">
                        <div className="bg-blue-400 flex items-center justify-center"
                          style={{ width: `${Math.max(5, parseFloat(selectedAlert.portfolio.target_equity_pct.toString()) * 0.5)}%` }}>
                          <span className="text-[8px] font-bold text-white">E</span>
                        </div>
                        <div className="bg-emerald-400 flex items-center justify-center"
                          style={{ width: `${Math.max(5, parseFloat(selectedAlert.portfolio.target_fixed_income_pct.toString()) * 0.6)}%` }}>
                          <span className="text-[8px] font-bold text-white">F</span>
                        </div>
                        <div className="bg-amber-300 flex items-center justify-center"
                          style={{ width: `${Math.max(5, parseFloat(selectedAlert.portfolio.target_cash_pct.toString()))}%` }}>
                          <span className="text-[8px] font-bold text-gray-700">C</span>
                        </div>
                      </div>
                    </div>

                    {/* Legend & Gap Explanation */}
                    <div className="grid grid-cols-3 gap-2 text-[10px] pt-2 border-t border-gray-100">
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-3 bg-blue-500 rounded"></div>
                        <span className="text-gray-600">Equity</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-3 bg-emerald-500 rounded"></div>
                        <span className="text-gray-600">Fixed Inc</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-3 bg-amber-400 rounded"></div>
                        <span className="text-gray-600">Cash</span>
                      </div>
                    </div>

                    {/* Gap Explanation */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 text-[11px] text-blue-800">
                      <div className="font-semibold mb-0.5">Cash Raise Plan:</div>
                      <div>Liquidate overweight positions (E, F) to increase cash from current to target allocation. System prioritizes lowest-gain lots to minimize tax impact.</div>
                    </div>
                  </div>
                </div>
              )}

              {/* TARGET CASH INPUT - INLINE */}
              {!plan && (
                <div className="card p-4">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1 mb-2">
                        <DollarSign size={14} className="text-emerald-600" />
                        Target Cash Reserve
                      </label>
                      <input
                        type="number"
                        value={targetCashAmount}
                        onChange={(e) => setTargetCashAmount(parseInt(e.target.value, 10) || 0)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
                        placeholder="Enter target cash amount"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2">Leave at default (266k) to auto-derive from portfolio target. Or enter a custom amount.</p>
                </div>
              )}

              {/* AI REBALANCING PLAN */}
              <div className={`transition ${plan?.status === "EXECUTED" ? "opacity-50 pointer-events-none" : ""}`}>
                <RebalancingSuggestionPanel
                  plan={plan}
                  loading={planLoading}
                  actionLoading={planActionLoading}
                  onGenerate={() => void handleGeneratePlan()}
                  onQueue={() => void handleQueuePlan()}
                  onApprove={() => void handleApprovePlan()}
                  onExecute={() => void handleExecutePlan()}
                  message={planMessage}
                  projection={allocationProjection}
                />
              </div>

              {/* ALLOCATION: BEFORE → AFTER */}
              {plan && allocationProjection && (
                <div className={`card p-4 space-y-4 transition ${plan?.status === "EXECUTED" ? "opacity-50" : ""}`}>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                    <TrendingDown size={16} className="text-blue-600" />
                    Portfolio Allocation: Before → After
                  </h3>
                  <div className="grid grid-cols-3 gap-3">
                    {/* Equity */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-gray-600 uppercase">Equity</div>
                      <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
                        <div className="text-lg font-bold text-blue-900">{allocationProjection.current.equity}%</div>
                        <div className="text-xs text-blue-600 mt-1">Current</div>
                      </div>
                      <div className="text-xs text-gray-500 text-center">↓</div>
                      <div className="rounded-lg bg-blue-100 border border-blue-300 p-3">
                        <div className="text-lg font-bold text-blue-900">{allocationProjection.projected.equity}%</div>
                        <div className="text-xs text-blue-700 mt-1">Projected</div>
                        <div className="text-[10px] text-blue-600 mt-1 font-semibold">
                          Δ {(allocationProjection.projected.equity - allocationProjection.current.equity).toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    {/* Fixed Income */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-gray-600 uppercase">Fixed Income</div>
                      <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
                        <div className="text-lg font-bold text-emerald-900">{allocationProjection.current.fixedIncome}%</div>
                        <div className="text-xs text-emerald-600 mt-1">Current</div>
                      </div>
                      <div className="text-xs text-gray-500 text-center">↓</div>
                      <div className="rounded-lg bg-emerald-100 border border-emerald-300 p-3">
                        <div className="text-lg font-bold text-emerald-900">{allocationProjection.projected.fixedIncome}%</div>
                        <div className="text-xs text-emerald-700 mt-1">Projected</div>
                        <div className="text-[10px] text-emerald-600 mt-1 font-semibold">
                          Δ {(allocationProjection.projected.fixedIncome - allocationProjection.current.fixedIncome).toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    {/* Cash */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-gray-600 uppercase">Cash</div>
                      <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                        <div className="text-lg font-bold text-amber-900">{allocationProjection.current.cash}%</div>
                        <div className="text-xs text-amber-600 mt-1">Current</div>
                      </div>
                      <div className="text-xs text-gray-500 text-center">↑</div>
                      <div className="rounded-lg bg-amber-100 border border-amber-300 p-3">
                        <div className="text-lg font-bold text-amber-900">{allocationProjection.projected.cash}%</div>
                        <div className="text-xs text-amber-700 mt-1">Projected</div>
                        <div className="text-[10px] text-amber-600 mt-1 font-semibold">
                          Δ {(allocationProjection.projected.cash - allocationProjection.current.cash).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="card p-8 flex flex-col items-center justify-center text-center space-y-3 min-h-[400px]">
              <AlertTriangle size={40} className="text-gray-300" />
              <p className="text-base font-semibold text-gray-600">No Alert Selected</p>
              <p className="text-sm text-gray-500">Choose an alert from the list to begin reallocation planning</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
