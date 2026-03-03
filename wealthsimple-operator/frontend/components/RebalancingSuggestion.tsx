"use client";

import { useState } from "react";
import type { ReallocationPlan } from "../lib/types";
import { Button } from "./Buttons";
import {
  DollarSign,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Clock,
  Percent,
  Shield,
  FileText,
  BarChart3,
  Zap,
  Target,
  ChevronDown,
  ChevronUp
} from "lucide-react";

interface RebalancingSuggestionPanelProps {
  plan: ReallocationPlan | null;
  loading?: boolean;
  actionLoading?: "queue" | "approve" | "execute" | null;
  onGenerate: () => void;
  onQueue: () => void;
  onApprove: () => void;
  onExecute: () => void;
  message?: string | null;
  projection?: any;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0
  }).format(value);
}

function stageLabel(status: ReallocationPlan["status"]): string {
  if (status === "PLANNED") return "AI Plan Generated";
  if (status === "QUEUED") return "Queued for Review";
  if (status === "APPROVED") return "Approved";
  return "Executed";
}

function stageColor(status: ReallocationPlan["status"]): string {
  if (status === "PLANNED") return "bg-blue-50 border-blue-200 text-blue-900";
  if (status === "QUEUED") return "bg-amber-50 border-amber-200 text-amber-900";
  if (status === "APPROVED") return "bg-green-50 border-green-200 text-green-900";
  return "bg-emerald-50 border-emerald-200 text-emerald-900";
}

export function RebalancingSuggestionPanel({
  plan,
  loading = false,
  actionLoading = null,
  onGenerate,
  onQueue,
  onApprove,
  onExecute,
  message,
  projection
}: RebalancingSuggestionPanelProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-bold text-gray-900 flex items-center gap-2">
          <Zap size={18} className="text-orange-500" />
          AI Auto-Reallocation Plan
        </div>
        <span className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700">
          SIMULATED - NOT EXECUTED
        </span>
      </div>

      {!plan && loading ? (
        <div className="card rounded-lg border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 space-y-3 text-center">
          <div className="space-y-2">
            <div className="font-semibold text-blue-900">Generating AI Reallocation Plan...</div>
            <div className="text-xs text-blue-600">Analyzing portfolio and calculating optimal liquidation strategy</div>
            <div className="flex justify-center mt-3">
              <div className="inline-flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse"></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: "0.2s" }}></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: "0.4s" }}></div>
              </div>
            </div>
          </div>
        </div>
      ) : !plan ? (
        <div className="card rounded-lg border border-gray-200 bg-gradient-to-br from-gray-50 to-white p-4 space-y-3">
          <div className="flex items-start gap-3">
            <Target size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="space-y-2">
              <div className="font-semibold text-gray-900">Unable to Generate Plan</div>
              <div className="text-xs text-gray-600">
                The AI plan should have generated automatically. Try clicking the button below or refreshing the alert.
              </div>
              <Button onClick={onGenerate} disabled={loading} className="mt-3">
                {loading ? "Generating..." : "Generate Plan Manually"}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* SECTION 1: STAGE INDICATOR + APPROVAL BUTTONS AT TOP */}
          <div className={`card rounded-lg border p-4 ${stageColor(plan.status)}`}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                {plan.status === "EXECUTED" && <CheckCircle2 size={18} />}
                {plan.status !== "EXECUTED" && <AlertCircle size={18} />}
                <div>
                  <div className="font-semibold">{stageLabel(plan.status)}</div>
                </div>
              </div>
            </div>

            {/* Approval workflow buttons - right after stage indicator */}
            <div className="grid grid-cols-2 gap-2">
              <Button
                onClick={onQueue}
                disabled={loading || actionLoading !== null || plan.status !== "PLANNED"}
                variant={plan.status === "PLANNED" ? "primary" : "secondary"}
                className="text-xs"
              >
                {actionLoading === "queue" ? (
                  <>
                    <Clock size={14} />
                    Queueing...
                  </>
                ) : (
                  <>
                    <Clock size={14} />
                    1. Queue
                  </>
                )}
              </Button>
              <Button
                onClick={onApprove}
                disabled={loading || actionLoading !== null || plan.status !== "QUEUED"}
                variant={plan.status === "QUEUED" ? "primary" : "secondary"}
                className="text-xs"
              >
                {actionLoading === "approve" ? (
                  <>
                    <Shield size={14} />
                    Approving...
                  </>
                ) : (
                  <>
                    <Shield size={14} />
                    2. Approve
                  </>
                )}
              </Button>
              <Button
                onClick={onExecute}
                disabled={loading || actionLoading !== null || plan.status !== "APPROVED"}
                className="col-span-2 text-xs"
                variant={plan.status === "APPROVED" ? "primary" : "secondary"}
              >
                {actionLoading === "execute" ? (
                  <>
                    <CheckCircle2 size={14} />
                    Executing...
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={14} />
                    3. Execute & Audit
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* SECTION 2: KEY METRICS - COMPACT SINGLE ROW */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4">
            <div className="grid grid-cols-4 gap-3">
              <div className="text-center">
                <div className="text-xs text-gray-600 font-semibold uppercase tracking-wider">Target Cash</div>
                <div className="font-bold text-sm text-gray-900 mt-1">{formatCurrency(plan.target_cash_amount)}</div>
              </div>
              <div className="text-center border-l border-gray-200">
                <div className="text-xs text-gray-600 font-semibold uppercase tracking-wider">Tax Impact</div>
                <div className="font-bold text-sm text-red-700 mt-1">{formatCurrency(plan.estimated_tax_impact)}</div>
              </div>
              <div className="text-center border-l border-gray-200">
                <div className="text-xs text-gray-600 font-semibold uppercase tracking-wider">Volatility ↓</div>
                <div className="font-bold text-sm text-emerald-700 mt-1">{plan.volatility_reduction_pct.toFixed(2)}%</div>
              </div>
              <div className="text-center border-l border-gray-200">
                <div className="text-xs text-gray-600 font-semibold uppercase tracking-wider">Settlement</div>
                <div className="font-bold text-sm text-gray-900 mt-1">T+{plan.liquidity_days}</div>
              </div>
            </div>
          </div>

          {/* SECTION 2B: IMPACT DASHBOARD - Before/After Risk Metrics */}
          <div className="card rounded-lg border border-gray-200 bg-gradient-to-br from-blue-50 to-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Risk Reduction Impact</h4>
            <div className="grid grid-cols-3 gap-3">
              {/* Volatility Impact */}
              <div className="space-y-2">
                <div className="text-[11px] font-semibold text-gray-700">Volatility</div>
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <div className="text-[10px] text-gray-500 mb-1">Before</div>
                    <div className="text-sm font-bold text-gray-900">{plan.volatility_before.toFixed(2)}%</div>
                  </div>
                  <div className="text-gray-400 text-xs">→</div>
                  <div className="flex-1">
                    <div className="text-[10px] text-emerald-600 mb-1">After</div>
                    <div className="text-sm font-bold text-emerald-700">{plan.volatility_after.toFixed(2)}%</div>
                  </div>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, (plan.volatility_reduction_pct / plan.volatility_before * 100))}%` }} />
                </div>
              </div>

              {/* Realized Gains */}
              <div className="space-y-2">
                <div className="text-[11px] font-semibold text-gray-700">Realized Gains</div>
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <div className="text-[10px] text-gray-500 mb-1">Taxable</div>
                    <div className="text-sm font-bold text-orange-700">{formatCurrency(plan.estimated_realized_gains)}</div>
                  </div>
                  <div className="text-gray-400 text-xs flex-shrink-0">@ {((plan.estimated_realized_gains > 0 ? plan.estimated_tax_impact / plan.estimated_realized_gains : 0) * 100).toFixed(0)}%</div>
                </div>
                <div className="text-[10px] text-gray-600 italic">Tax cost built-in</div>
              </div>

              {/* Coverage */}
              <div className="space-y-2">
                <div className="text-[11px] font-semibold text-gray-700">Cash Coverage</div>
                <div className="text-sm font-bold text-blue-700">
                  {((plan.additional_cash_needed > 0 ? (plan.target_cash_amount - (plan.target_cash_amount - plan.additional_cash_needed)) / plan.additional_cash_needed : 1) * 100).toFixed(0)}%
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, 100)}%` }} />
                </div>
                <div className="text-[10px] text-gray-600">Of target raised</div>
              </div>
            </div>
          </div>

          {/* SECTION 2C: PROJECTED ALLOCATION - Visual before/after */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Projected Portfolio Composition</h4>
            <div className="space-y-3">
              {/* Current Allocation */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-gray-700">Before Plan</span>
                  <span className="text-gray-500">100%</span>
                </div>
                <div className="flex gap-1 h-5 rounded border border-gray-300 bg-gray-50 overflow-hidden">
                  <div className="bg-blue-500" style={{ width: "45%" }} />
                  <div className="bg-emerald-500" style={{ width: "35%" }} />
                  <div className="bg-amber-400" style={{ width: "20%" }} />
                </div>
              </div>

              {/* After Allocation */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-emerald-700">After Plan</span>
                  <span className="text-emerald-600">100%</span>
                </div>
                <div className="flex gap-1 h-5 rounded border border-emerald-300 bg-emerald-50 overflow-hidden">
                  <div className="bg-blue-600" style={{ width: "35%" }} />
                  <div className="bg-emerald-600" style={{ width: "28%" }} />
                  <div className="bg-amber-500" style={{ width: "37%" }} />
                </div>
              </div>

              {/* Legend */}
              <div className="flex gap-4 text-[10px] pt-2 border-t border-gray-200">
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 bg-blue-500 rounded" />
                  <span>Equity</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 bg-emerald-500 rounded" />
                  <span>Fixed Income</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 bg-amber-400 rounded" />
                  <span>Cash</span>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 3: PROPOSED TRADES */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 flex items-center gap-2 uppercase tracking-wider">
              <FileText size={14} className="text-orange-600" />
              Proposed Liquidations
            </h4>
            <div className="space-y-2">
              {plan.trades.length === 0 ? (
                <div className="text-xs text-gray-600 italic p-2">No trades required for this scenario.</div>
              ) : (
                plan.trades.map((trade) => (
                  <div
                    key={`${trade.ticker}-${trade.asset_class}`}
                    className="rounded-lg border border-gray-200 bg-gradient-to-r from-gray-50 to-white p-3 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-semibold text-gray-900 text-sm">{trade.action} {trade.ticker}</div>
                        <div className="text-xs text-gray-600">{trade.asset_class}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-gray-900">{formatCurrency(trade.amount)}</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <div className="text-gray-600">Est. Tax Cost</div>
                      <div className="font-semibold text-red-700">{formatCurrency(trade.estimated_tax_cost)}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* SECTION 4: DETAILS (COLLAPSIBLE) */}
          <div className="card rounded-lg border border-gray-200 bg-white">
            <button
              onClick={() => setDetailsOpen(!detailsOpen)}
              className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition"
            >
              <h4 className="text-xs font-bold text-gray-900 flex items-center gap-2 uppercase tracking-wider">
                <Shield size={14} className="text-slate-600" />
                Alternative Strategies & AI Reasoning
              </h4>
              {detailsOpen ? (
                <ChevronUp size={16} className="text-gray-500" />
              ) : (
                <ChevronDown size={16} className="text-gray-500" />
              )}
            </button>

            {detailsOpen && (
              <div className="border-t border-gray-200 p-4 space-y-4">
                {/* Alternatives */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Why We Didn't Choose These:</div>
                  <div className="space-y-2">
                    {plan.alternatives_considered.map((alt) => (
                      <div key={alt.name} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <div className="text-xs font-semibold text-gray-900 mb-2">{alt.name}</div>
                        <div className="bg-white rounded p-2 space-y-1 text-[11px]">
                          <div className="flex justify-between text-gray-700">
                            <span>Tax Impact:</span>
                            <span className="font-semibold">{formatCurrency(alt.estimated_tax_impact)}</span>
                          </div>
                          <div className="flex justify-between text-gray-700">
                            <span>Settlement:</span>
                            <span className="font-semibold">T+{alt.estimated_liquidity_days}</span>
                          </div>
                          <div className="mt-1 p-1.5 rounded bg-red-50 border border-red-200">
                            <div className="text-red-600 text-[10px]">{alt.rejected_reason}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Rationale */}
                <div className="border-t border-gray-200 pt-4 space-y-2">
                  <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    <Zap size={12} className="inline mr-1" />
                    AI Analysis & Reasoning
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed">{plan.ai_rationale}</p>
                </div>
              </div>
            )}
          </div>

          {/* SECTION 5: STATUS MESSAGE */}
          {message && (
            <div className="rounded-lg border border-gray-200 bg-white p-3 text-xs text-gray-700">
              {message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
