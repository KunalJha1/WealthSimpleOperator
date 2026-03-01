"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { AlertSummary, ReallocationPlan, RebalancingSuggestion } from "../../lib/types";
import {
  approveReallocationPlan,
  executeReallocationPlan,
  fetchAlerts,
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
  BarChart3,
  Shield,
  Clock,
  Percent
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

  useEffect(() => {
    setPlan(null);
    setPlanMessage(null);
  }, [selectedAlertId]);

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
        <div className="flex gap-2 flex-wrap">
          <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700 font-semibold">
            <BarChart3 size={14} />
            Risk-Aware
          </div>
          <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs text-amber-700 font-semibold">
            <DollarSign size={14} />
            Tax Optimized
          </div>
          <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs text-emerald-700 font-semibold">
            <CheckCircle2 size={14} />
            Human Approval Required
          </div>
        </div>
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

              {/* ALLOCATION SNAPSHOT */}
              {!allocationLoading && !allocationError && allocationProjection && (
                <div className={`card p-4 space-y-3 transition ${plan?.status === "EXECUTED" ? "opacity-50" : ""}`}>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                    <Target size={16} className="text-blue-600" />
                    Current Allocation Snapshot
                  </h3>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-lg bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 p-3">
                      <div className="text-blue-700 font-semibold text-lg">{allocationProjection.current.equity}%</div>
                      <div className="text-blue-600 text-xs">Equity</div>
                    </div>
                    <div className="rounded-lg bg-gradient-to-br from-emerald-50 to-emerald-100 border border-emerald-200 p-3">
                      <div className="text-emerald-700 font-semibold text-lg">{allocationProjection.current.fixedIncome}%</div>
                      <div className="text-emerald-600 text-xs">Fixed Income</div>
                    </div>
                    <div className="rounded-lg bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200 p-3">
                      <div className="text-amber-700 font-semibold text-lg">{allocationProjection.current.cash}%</div>
                      <div className="text-amber-600 text-xs">Cash</div>
                    </div>
                  </div>
                </div>
              )}

              {/* TARGET CASH INPUT */}
              {!plan && (
                <div className="card p-4 space-y-3">
                  <label className="text-sm font-bold text-gray-900 flex items-center gap-2">
                    <DollarSign size={16} className="text-emerald-600" />
                    Target Cash Reserve
                  </label>
                  <input
                    type="number"
                    value={targetCashAmount}
                    onChange={(e) => setTargetCashAmount(parseInt(e.target.value, 10) || 0)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    placeholder="Enter target cash amount"
                  />
                  <p className="text-xs text-gray-600">Adjust the target cash reserve before generating the reallocation plan.</p>
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

              {/* PROJECTED ALLOCATION */}
              {plan && allocationProjection && (
                <div className={`card p-4 space-y-3 transition ${plan?.status === "EXECUTED" ? "opacity-50" : ""}`}>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                    <TrendingDown size={16} className="text-orange-600" />
                    Post-Reallocation Allocation
                  </h3>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-lg bg-gradient-to-br from-blue-50/50 to-blue-100/50 border border-blue-200 p-3 opacity-60">
                      <div className="text-blue-700 font-semibold text-lg">{allocationProjection.projected.equity}%</div>
                      <div className="text-blue-600 text-xs">Equity (Projected)</div>
                      <div className="text-[10px] text-blue-500 mt-1">↓ {(allocationProjection.current.equity - allocationProjection.projected.equity).toFixed(1)}%</div>
                    </div>
                    <div className="rounded-lg bg-gradient-to-br from-emerald-50/50 to-emerald-100/50 border border-emerald-200 p-3 opacity-60">
                      <div className="text-emerald-700 font-semibold text-lg">{allocationProjection.projected.fixedIncome}%</div>
                      <div className="text-emerald-600 text-xs">Fixed Income (Proj.)</div>
                      <div className="text-[10px] text-emerald-500 mt-1">↓ {(allocationProjection.current.fixedIncome - allocationProjection.projected.fixedIncome).toFixed(1)}%</div>
                    </div>
                    <div className="rounded-lg bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200 p-3">
                      <div className="text-amber-700 font-semibold text-lg">{allocationProjection.projected.cash}%</div>
                      <div className="text-amber-600 text-xs">Cash (Projected)</div>
                      <div className="text-[10px] text-amber-600 mt-1">↑ {(allocationProjection.projected.cash - allocationProjection.current.cash).toFixed(1)}%</div>
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
