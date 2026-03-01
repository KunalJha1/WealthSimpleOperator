"use client";

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
  Target
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

      {!plan ? (
        <div className="card rounded-lg border border-gray-200 bg-gradient-to-br from-gray-50 to-white p-4 space-y-3">
          <div className="flex items-start gap-3">
            <Target size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="space-y-2">
              <div className="font-semibold text-gray-900">Generate Comprehensive Reallocation Plan</div>
              <div className="text-xs text-gray-600 space-y-1">
                <p>The AI will analyze this portfolio and generate a complete plan that includes:</p>
                <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                  <li>Tax-aware liquidation strategy</li>
                  <li>Volatility impact analysis</li>
                  <li>Risk profile alignment</li>
                  <li>Client communication guidance</li>
                  <li>Regulatory considerations</li>
                </ul>
              </div>
              <Button onClick={onGenerate} disabled={loading} className="mt-3">
                {loading ? "Generating AI plan..." : "Generate AI Plan"}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* STATUS STAGE INDICATOR */}
          <div className={`card rounded-lg border p-4 ${stageColor(plan.status)}`}>
            <div className="flex items-center gap-2">
              {plan.status === "EXECUTED" && <CheckCircle2 size={18} />}
              {plan.status !== "EXECUTED" && <AlertCircle size={18} />}
              <div>
                <div className="font-semibold">Current Stage</div>
                <div className="text-xs">{stageLabel(plan.status)}</div>
              </div>
            </div>
          </div>

          {/* KEY METRICS GRID */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 flex items-center gap-2 uppercase tracking-wider">
              <DollarSign size={14} className="text-blue-600" />
              Financial Impact
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 p-3">
                <div className="text-xs text-blue-600 uppercase font-semibold tracking-wider">Target Cash Raised</div>
                <div className="font-bold text-lg text-blue-900 mt-1">{formatCurrency(plan.target_cash_amount)}</div>
              </div>
              <div className="rounded-lg bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200 p-3">
                <div className="text-xs text-amber-600 uppercase font-semibold tracking-wider">Additional Needed</div>
                <div className="font-bold text-lg text-amber-900 mt-1">{formatCurrency(plan.additional_cash_needed)}</div>
              </div>
              <div className="rounded-lg bg-gradient-to-br from-red-50 to-red-100 border border-red-200 p-3">
                <div className="text-xs text-red-600 uppercase font-semibold tracking-wider">Est. Tax Impact</div>
                <div className="font-bold text-lg text-red-900 mt-1">{formatCurrency(plan.estimated_tax_impact)}</div>
              </div>
              <div className="rounded-lg bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 p-3">
                <div className="text-xs text-purple-600 uppercase font-semibold tracking-wider">Liquidity Timeline</div>
                <div className="font-bold text-lg text-purple-900 mt-1">T+{plan.liquidity_days}</div>
              </div>
            </div>
          </div>

          {/* VOLATILITY & RISK SECTION */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 flex items-center gap-2 uppercase tracking-wider">
              <BarChart3 size={14} className="text-emerald-600" />
              Risk & Volatility Profile
            </h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3">
                <div>
                  <div className="text-xs text-gray-600 font-semibold">Current Volatility</div>
                  <div className="text-sm text-gray-900 font-bold">{plan.volatility_before.toFixed(2)}%</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-600 font-semibold">Post-Reallocation</div>
                  <div className="text-sm text-gray-900 font-bold">{plan.volatility_after.toFixed(2)}%</div>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-gradient-to-r from-emerald-50 to-emerald-100 border border-emerald-200 p-3">
                <div>
                  <div className="text-xs text-emerald-600 font-semibold">Volatility Reduction</div>
                  <div className="text-sm text-emerald-900 font-bold">{plan.volatility_reduction_pct.toFixed(2)}%</div>
                </div>
                <div className="text-emerald-600">
                  <CheckCircle2 size={20} />
                </div>
              </div>
            </div>
          </div>

          {/* TRADES BREAKDOWN */}
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

          {/* ALTERNATIVES CONSIDERED - WHY THIS PLAN */}
          <div className="card rounded-lg border border-gray-200 bg-white p-4 space-y-3">
            <h4 className="text-xs font-bold text-gray-900 flex items-center gap-2 uppercase tracking-wider">
              <Shield size={14} className="text-slate-600" />
              Strategic Rationale: Why This Plan
            </h4>
            <div className="space-y-2">
              {plan.alternatives_considered.map((alt) => (
                <div key={alt.name} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="text-xs font-semibold text-gray-900">{alt.name}</div>
                      <div className="text-[11px] text-gray-600 mt-0.5">Alternative approach</div>
                    </div>
                  </div>
                  <div className="bg-white rounded p-2 space-y-1 text-[11px]">
                    <div className="flex justify-between text-gray-700">
                      <span>Tax Impact:</span>
                      <span className="font-semibold">{formatCurrency(alt.estimated_tax_impact)}</span>
                    </div>
                    <div className="flex justify-between text-gray-700">
                      <span>Settlement:</span>
                      <span className="font-semibold">T+{alt.estimated_liquidity_days}</span>
                    </div>
                    <div className="flex justify-between text-gray-700">
                      <span>Final Volatility:</span>
                      <span className="font-semibold">{alt.volatility_after.toFixed(2)}%</span>
                    </div>
                    <div className="mt-2 p-2 rounded bg-red-50 border border-red-200">
                      <div className="text-red-700 font-semibold text-[10px] mb-0.5">NOT SELECTED</div>
                      <div className="text-red-600">{alt.rejected_reason}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* AI RATIONALE - DETAILED REASONING */}
          <div className="card rounded-lg border border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100 p-4 space-y-2">
            <h4 className="text-xs font-bold text-blue-900 flex items-center gap-2 uppercase tracking-wider">
              <Zap size={14} className="text-blue-600" />
              AI Analysis & Reasoning
            </h4>
            <p className="text-sm text-blue-900 leading-relaxed">{plan.ai_rationale}</p>
          </div>

          {/* APPROVAL WORKFLOW BUTTONS */}
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
                  1. Queue Plan
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
                  2. Human Approve
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
                  Executing (Simulated)...
                </>
              ) : (
                <>
                  <CheckCircle2 size={14} />
                  3. Execute & Audit (Simulated)
                </>
              )}
            </Button>
          </div>

          {/* STATUS MESSAGE */}
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
