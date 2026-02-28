"use client";

import { useEffect, useMemo, useState } from "react";
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

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0
  }).format(value);
}

export default function AutoReallocationPage() {
  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);

  const [plan, setPlan] = useState<ReallocationPlan | null>(null);
  const [planMessage, setPlanMessage] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planActionLoading, setPlanActionLoading] = useState<"queue" | "approve" | "execute" | null>(null);
  const [allocationSnapshot, setAllocationSnapshot] = useState<RebalancingSuggestion | null>(null);
  const [allocationLoading, setAllocationLoading] = useState(false);
  const [allocationError, setAllocationError] = useState<string | null>(null);

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
      const next = await generateReallocationPlan(selectedAlertId, 266000);
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
      <header>
        <h1 className="page-title">AI Auto-Reallocation</h1>
        <p className="page-subtitle max-w-3xl">
          High-stakes workflow: AI proposes exact trades to raise a CAD 266k down payment reserve
          with tax-aware liquidation and volatility impact analysis. Human approval is required before execution.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.8fr)]">
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-900">Select Alert Context</div>
            <div className="text-xs text-ws-muted">{alerts.length} alerts</div>
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

          <div className="space-y-2 max-h-[540px] overflow-y-auto">
            {alerts.map((alert) => {
              const active = alert.id === selectedAlertId;
              return (
                <button
                  key={alert.id}
                  type="button"
                  onClick={() => setSelectedAlertId(alert.id)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    active ? "border-ws-ink bg-ws-ink/5" : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <PriorityPill priority={alert.priority} />
                    <StatusPill status={alert.status} />
                  </div>
                  <div className="mt-2 text-sm font-semibold text-gray-900">{alert.event_title}</div>
                  <div className="mt-1 text-xs text-gray-600">
                    {alert.client.name} - {alert.portfolio.name}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Portfolio value: {formatCurrency(alert.portfolio.total_value)}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="card p-4 space-y-3">
          {selectedAlert ? (
            <>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-800">
                <div className="font-semibold text-gray-900">{selectedAlert.client.name}</div>
                <div className="text-xs text-gray-600 mt-1">{selectedAlert.summary}</div>
              </div>
              <RebalancingSuggestionPanel
                plan={plan}
                loading={planLoading}
                actionLoading={planActionLoading}
                onGenerate={() => void handleGeneratePlan()}
                onQueue={() => void handleQueuePlan()}
                onApprove={() => void handleApprovePlan()}
                onExecute={() => void handleExecutePlan()}
                message={planMessage}
              />
              <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">
                    Allocation Transition: Current{" -> "}Projected
                  </h3>
                  <p className="text-xs text-gray-600">
                    Shows how the proposed liquidation shifts risk exposure before execution.
                  </p>
                </div>

                {allocationLoading && (
                  <div className="text-xs text-ws-muted">Loading current allocation snapshot...</div>
                )}
                {allocationError && (
                  <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                    {allocationError}
                  </div>
                )}

                {allocationProjection && (
                  <>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="rounded border border-gray-200 bg-gray-50 p-2">
                        <div className="text-gray-500">Equity</div>
                        <div className="font-semibold text-gray-900">
                          {allocationProjection.current.equity}%{" -> "}{allocationProjection.projected.equity}%
                        </div>
                      </div>
                      <div className="rounded border border-gray-200 bg-gray-50 p-2">
                        <div className="text-gray-500">Fixed Income</div>
                        <div className="font-semibold text-gray-900">
                          {allocationProjection.current.fixedIncome}%{" -> "}{allocationProjection.projected.fixedIncome}%
                        </div>
                      </div>
                      <div className="rounded border border-gray-200 bg-gray-50 p-2">
                        <div className="text-gray-500">Cash</div>
                        <div className="font-semibold text-gray-900">
                          {allocationProjection.current.cash}%{" -> "}{allocationProjection.projected.cash}%
                        </div>
                      </div>
                    </div>

                    <div className="rounded border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
                      <div className="font-semibold mb-1">AI reasoning</div>
                      <div>
                        The proposal raises {formatCurrency(allocationProjection.soldTotal)} by selling
                        {` ${formatCurrency(allocationProjection.soldEquity)} `}from equities and
                        {` ${formatCurrency(allocationProjection.soldFixedIncome)} `}from fixed income,
                        redirecting proceeds to cash to improve near-term liquidity and reduce volatility.
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="text-sm text-ws-muted">Select an alert to begin.</div>
          )}
        </div>
      </div>
    </section>
  );
}
