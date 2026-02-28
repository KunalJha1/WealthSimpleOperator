"use client";

import type { ReallocationPlan } from "../lib/types";
import { Button } from "./Buttons";

interface RebalancingSuggestionPanelProps {
  plan: ReallocationPlan | null;
  loading?: boolean;
  actionLoading?: "queue" | "approve" | "execute" | null;
  onGenerate: () => void;
  onQueue: () => void;
  onApprove: () => void;
  onExecute: () => void;
  message?: string | null;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0
  }).format(value);
}

function stageLabel(status: ReallocationPlan["status"]): string {
  if (status === "PLANNED") return "AI Plan";
  if (status === "QUEUED") return "AI Queue";
  if (status === "APPROVED") return "Human Approve";
  return "Execute + Audit";
}

export function RebalancingSuggestionPanel({
  plan,
  loading = false,
  actionLoading = null,
  onGenerate,
  onQueue,
  onApprove,
  onExecute,
  message
}: RebalancingSuggestionPanelProps) {
  return (
    <div className="space-y-3 border-t border-gray-200 pt-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-gray-900">
          AI Auto-Reallocation Proposal (Simulated Execution)
        </div>
        <span className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700">
          SIMULATED - NOT SENT
        </span>
      </div>

      {!plan ? (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
          <div className="text-xs text-gray-700">
            Generate an AI plan to raise a CAD 266k down payment reserve with tax-aware liquidation and staged approval controls.
          </div>
          <Button onClick={onGenerate} disabled={loading}>
            {loading ? "Generating AI plan..." : "Generate AI Plan"}
          </Button>
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold text-gray-700">Current Stage</div>
              <div className="text-xs font-semibold text-gray-900">{stageLabel(plan.status)}</div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Target Cash</div>
                <div className="font-semibold text-gray-900">{formatCurrency(plan.target_cash_amount)}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Additional Needed</div>
                <div className="font-semibold text-gray-900">{formatCurrency(plan.additional_cash_needed)}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Estimated Tax Impact</div>
                <div className="font-semibold text-gray-900">{formatCurrency(plan.estimated_tax_impact)}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Liquidity Timeline</div>
                <div className="font-semibold text-gray-900">T+{plan.liquidity_days} days</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Volatility</div>
                <div className="font-semibold text-gray-900">
                  {plan.volatility_before.toFixed(2)}% {"->"} {plan.volatility_after.toFixed(2)}%
                </div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-gray-500">Volatility Reduction</div>
                <div className="font-semibold text-emerald-700">{plan.volatility_reduction_pct.toFixed(2)}%</div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-3">
            <div className="mb-2 text-xs font-semibold text-gray-700">What would be sold</div>
            <div className="space-y-1.5">
              {plan.trades.map((trade) => (
                <div
                  key={`${trade.ticker}-${trade.asset_class}`}
                  className="grid grid-cols-[1.2fr_1fr_1fr] items-center gap-2 rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs"
                >
                  <div className="font-medium text-gray-900">
                    {trade.action} {trade.ticker} ({trade.asset_class})
                  </div>
                  <div className="text-gray-700">{formatCurrency(trade.amount)}</div>
                  <div className="text-right text-gray-500">Tax {formatCurrency(trade.estimated_tax_cost)}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
            <div className="text-xs font-semibold text-gray-700">Why this plan over alternatives</div>
            {plan.alternatives_considered.map((alt) => (
              <div key={alt.name} className="rounded border border-gray-200 bg-gray-50 p-2">
                <div className="text-xs font-medium text-gray-900">{alt.name}</div>
                <div className="text-[11px] text-gray-700">
                  Tax {formatCurrency(alt.estimated_tax_impact)}, Liquidity T+{alt.estimated_liquidity_days}, Vol {alt.volatility_after.toFixed(2)}%
                </div>
                <div className="text-[11px] text-amber-700">{alt.rejected_reason}</div>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
            {plan.ai_rationale}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Button
              onClick={onQueue}
              disabled={loading || actionLoading !== null || plan.status !== "PLANNED"}
              variant="secondary"
            >
              {actionLoading === "queue" ? "Queueing..." : "2. Queue Plan"}
            </Button>
            <Button
              onClick={onApprove}
              disabled={loading || actionLoading !== null || plan.status !== "QUEUED"}
              variant="secondary"
            >
              {actionLoading === "approve" ? "Approving..." : "3. Human Approve"}
            </Button>
            <Button
              onClick={onExecute}
              disabled={loading || actionLoading !== null || plan.status !== "APPROVED"}
              className="col-span-2"
            >
              {actionLoading === "execute" ? "Executing..." : "4. Execute + Audit (Simulated)"}
            </Button>
          </div>
        </>
      )}

      {message && <div className="rounded border border-gray-200 bg-white p-2 text-xs text-gray-700">{message}</div>}
    </div>
  );
}
