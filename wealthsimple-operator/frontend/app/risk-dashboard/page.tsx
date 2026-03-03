"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchRiskDashboard, postAlertAction, fetchAlert } from "../../lib/api";
import type { RiskDashboardResponse, RiskClientRow, AlertDetail } from "../../lib/types";
import {
  TrendingUp,
  AlertTriangle,
  Activity,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  LineChart,
  BarChart3,
  Clock,
  Brain,
  CheckCircle2,
  Eye,
  Shuffle,
  Phone,
  CheckSquare,
  Square,
  ChevronRight,
  Zap
} from "lucide-react";

type ActionType = "rebalance_now" | "review_alert" | "contact_client" | "monitor";

interface RecommendedAction {
  type: ActionType;
  label: string;
  reason: string;
  color: "red" | "amber" | "green" | "gray";
}

export default function RiskDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<RiskDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"predicted_30d_risk" | "current_risk" | "days_without_review">(
    "predicted_30d_risk"
  );
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const response = await fetchRiskDashboard();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load risk dashboard");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const getRecommendedAction = (row: RiskClientRow): RecommendedAction => {
    if (row.predicted_30d_risk >= 7 && row.trend === "RISING") {
      return {
        type: "rebalance_now",
        label: "Rebalance Now",
        reason: "High risk + rising trend",
        color: "red"
      };
    }
    if (row.days_without_review > 30) {
      return {
        type: "review_alert",
        label: "Review Alert",
        reason: `No review for ${row.days_without_review} days`,
        color: "red"
      };
    }
    if (row.trend === "RISING" && row.predicted_30d_risk >= 5) {
      return {
        type: "contact_client",
        label: "Contact Client",
        reason: "Rising risk trend",
        color: "amber"
      };
    }
    if (row.days_without_review > 14) {
      return {
        type: "review_alert",
        label: "Review Alert",
        reason: `No review for ${row.days_without_review} days`,
        color: "amber"
      };
    }
    if (row.trend === "FALLING") {
      return {
        type: "monitor",
        label: "Monitor",
        reason: "Positive trend",
        color: "green"
      };
    }
    return {
      type: "monitor",
      label: "Monitor",
      reason: "Stable condition",
      color: "gray"
    };
  };

  const getSortedRows = () => {
    if (!data) return [];
    const sorted = [...data.rows];
    if (sortBy === "predicted_30d_risk") {
      sorted.sort((a, b) => b.predicted_30d_risk - a.predicted_30d_risk);
    } else if (sortBy === "current_risk") {
      sorted.sort((a, b) => b.current_risk - a.current_risk);
    } else if (sortBy === "days_without_review") {
      sorted.sort((a, b) => b.days_without_review - a.days_without_review);
    }
    return sorted;
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case "RISING":
        return <ArrowUp size={16} className="text-red-600" />;
      case "FALLING":
        return <ArrowDown size={16} className="text-emerald-600" />;
      case "STABLE":
        return <ArrowRight size={16} className="text-gray-600" />;
      default:
        return null;
    }
  };

  const getRiskBgColor = (risk: number) => {
    if (risk >= 7) return "bg-red-50 border-l-4 border-red-500";
    if (risk >= 5) return "bg-amber-50 border-l-4 border-amber-500";
    return "bg-blue-50 border-l-4 border-blue-500";
  };

  const getRiskTextColor = (risk: number) => {
    if (risk >= 7) return "text-red-700 font-semibold";
    if (risk >= 5) return "text-amber-700 font-semibold";
    return "text-blue-700 font-semibold";
  };

  const getDaysBadgeColor = (days: number) => {
    if (days > 30) return "bg-red-100 text-red-700 border-red-300";
    if (days > 14) return "bg-amber-100 text-amber-700 border-amber-300";
    return "bg-emerald-100 text-emerald-700 border-emerald-300";
  };

  const getActionBadgeColor = (color: string) => {
    switch (color) {
      case "red":
        return "bg-red-100 text-red-700 border-red-300";
      case "amber":
        return "bg-amber-100 text-amber-700 border-amber-300";
      case "green":
        return "bg-emerald-100 text-emerald-700 border-emerald-300";
      default:
        return "bg-gray-100 text-gray-700 border-gray-300";
    }
  };

  const toggleSelect = (alertId: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(alertId)) {
      newSelected.delete(alertId);
    } else {
      newSelected.add(alertId);
    }
    setSelectedIds(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === sortedRows.length && sortedRows.length > 0) {
      setSelectedIds(new Set());
    } else {
      const allIds = new Set(sortedRows.map(r => r.alert_id));
      setSelectedIds(allIds);
    }
  };

  const handleMarkAllReviewed = async () => {
    setBatchLoading(true);
    try {
      const alerts = Array.from(selectedIds);
      await Promise.all(alerts.map(id => postAlertAction(id, "reviewed")));

      // Refresh the dashboard
      const response = await fetchRiskDashboard();
      setData(response);
      setSelectedIds(new Set());
    } catch (err) {
      console.error("Failed to mark alerts as reviewed:", err);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleRunPlaybook = () => {
    const portfolioIds = Array.from(selectedIds);
    const params = new URLSearchParams();
    params.set("portfolio_ids", portfolioIds.join(","));
    router.push(`/simulations?${params.toString()}`);
  };

  const sortedRows = getSortedRows();

  if (loading) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <TrendingUp size={24} className="text-blue-600" />
            </div>
            <div>
              <h1 className="page-title">Risk Dashboard</h1>
              <p className="text-xs text-ws-muted font-semibold tracking-wide">30-DAY FORWARD PREDICTION</p>
            </div>
          </div>
        </header>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Activity className="w-8 h-8 text-ws-muted mx-auto mb-2 animate-spin" />
            <p className="text-sm text-ws-muted">Analyzing portfolio risk...</p>
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertTriangle size={24} className="text-red-600" />
            </div>
            <div>
              <h1 className="page-title">Error</h1>
              <p className="text-xs text-ws-muted font-semibold tracking-wide">Unable to load dashboard</p>
            </div>
          </div>
        </header>
        <div className="card p-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <TrendingUp size={24} className="text-blue-600" />
            </div>
            <div>
              <h1 className="page-title">Risk Dashboard</h1>
              <p className="page-subtitle">No data available</p>
            </div>
          </div>
        </header>
      </section>
    );
  }

  return (
    <section className="space-y-5 page-enter pb-32">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-gradient-to-br from-blue-100 to-blue-50 border border-blue-200">
            <TrendingUp size={24} className="text-blue-600" />
          </div>
          <div>
            <h1 className="page-title">Risk Dashboard</h1>
            <p className="text-xs text-ws-muted font-semibold tracking-wide">PREDICTIVE TREND ANALYSIS FOR PORTFOLIO MONITORING</p>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="card p-4 border-l-4 border-l-gray-400 stat-enter stagger-1">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 size={14} className="text-gray-600" />
              <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Avg Current Risk</div>
            </div>
            <div className="text-3xl font-semibold text-gray-900">{data.avg_current_risk.toFixed(1)}</div>
            <p className="text-xs text-ws-muted mt-1">out of 10</p>
          </div>

          <div className="card p-4 border-l-4 border-l-blue-500 stat-enter stagger-2">
            <div className="flex items-center gap-2 mb-2">
              <LineChart size={14} className="text-blue-600" />
              <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Predicted 30d</div>
            </div>
            <div className="text-3xl font-semibold text-blue-600">{data.avg_predicted_risk.toFixed(1)}</div>
            <p className="text-xs text-ws-muted mt-1">Trend-adjusted forecast</p>
          </div>

          <div className="card p-4 border-l-4 border-l-red-500 stat-enter stagger-3">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUp size={14} className="text-red-600" />
              <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Rising Trend</div>
            </div>
            <div className="text-3xl font-semibold text-red-600">{data.rising_count}</div>
            <p className="text-xs text-ws-muted mt-1">Portfolios at risk</p>
          </div>

          <div className="card p-4 border-l-4 border-l-orange-500 stat-enter stagger-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={14} className="text-orange-600" />
              <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider">High Risk ≥7</div>
            </div>
            <div className="text-3xl font-semibold text-orange-600">{data.high_risk_count}</div>
            <p className="text-xs text-ws-muted mt-1">Urgent attention</p>
          </div>
        </div>
      </header>

      {/* Sort Controls + Select All */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Sort by:</span>
          <div className="flex gap-2">
            <button
              onClick={() => setSortBy("predicted_30d_risk")}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
                sortBy === "predicted_30d_risk"
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
              }`}
            >
              <LineChart size={14} />
              Predicted
            </button>
            <button
              onClick={() => setSortBy("current_risk")}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
                sortBy === "current_risk"
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
              }`}
            >
              <BarChart3 size={14} />
              Current
            </button>
            <button
              onClick={() => setSortBy("days_without_review")}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
                sortBy === "days_without_review"
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
              }`}
            >
              <Clock size={14} />
              Review Age
            </button>
          </div>
        </div>

        {/* Select All Control */}
        <button
          onClick={toggleSelectAll}
          className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-gray-600 hover:text-blue-600 rounded-lg hover:bg-blue-50 transition"
        >
          {selectedIds.size === sortedRows.length && sortedRows.length > 0 ? (
            <>
              <CheckSquare size={16} className="text-blue-600" />
              Clear All
            </>
          ) : (
            <>
              <Square size={16} />
              Select All
            </>
          )}
        </button>
      </div>

      {/* Portfolio Rows */}
      <div className="space-y-3">
        {sortedRows.length === 0 ? (
          <div className="card p-12 text-center">
            <TrendingUp className="w-8 h-8 text-ws-muted mx-auto mb-2" />
            <p className="text-sm text-ws-muted">No portfolios with risk data</p>
          </div>
        ) : (
          sortedRows.map((row, index) => {
            const action = getRecommendedAction(row);
            const isSelected = selectedIds.has(row.alert_id);

            return (
              <div
                key={`${row.alert_id}-${row.portfolio_id}`}
                className={`card p-5 space-y-4 transition row-enter ${getRiskBgColor(row.predicted_30d_risk)} ${
                  isSelected ? "ring-2 ring-blue-500" : ""
                }`}
                style={{ animationDelay: `${Math.min(index * 40, 240)}ms` }}
              >
                {/* Row: Checkbox + Client Info + Risk Scores */}
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-start">
                  {/* Checkbox */}
                  <div className="flex items-center pt-1">
                    <button
                      onClick={() => toggleSelect(row.alert_id)}
                      className="text-gray-600 hover:text-blue-600 transition"
                    >
                      {isSelected ? (
                        <CheckSquare size={20} className="text-blue-600" />
                      ) : (
                        <Square size={20} />
                      )}
                    </button>
                  </div>

                  {/* Client Info */}
                  <div className="md:col-span-2">
                    <h3 className="font-semibold text-gray-900">{row.client_name}</h3>
                    <p className="text-sm text-gray-600 mt-1">{row.portfolio_name}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-600 mt-2">
                      <span>{row.segment}</span>
                      <span>•</span>
                      <span>{row.risk_profile}</span>
                    </div>
                  </div>

                  {/* Current Risk */}
                  <div className="text-sm">
                    <span className="text-xs text-gray-600 font-semibold block mb-1">CURRENT RISK</span>
                    <div className={`text-2xl font-semibold ${getRiskTextColor(row.current_risk)}`}>
                      {row.current_risk.toFixed(1)}
                    </div>
                  </div>

                  {/* Predicted 30D */}
                  <div className="text-sm">
                    <span className="text-xs text-gray-600 font-semibold block mb-1">PREDICTED 30D</span>
                    <div className={`text-2xl font-semibold ${getRiskTextColor(row.predicted_30d_risk)}`}>
                      {row.predicted_30d_risk.toFixed(1)}
                    </div>
                  </div>
                </div>

                {/* Row: Trend + Days + Status + Recommended Action */}
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 pt-4 border-t border-gray-200">
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-white/50">
                    <div className="flex items-center gap-1">
                      {getTrendIcon(row.trend)}
                      <span className="text-sm font-semibold text-gray-900">{row.trend}</span>
                    </div>
                    {row.trend_pct !== null && row.trend_pct !== undefined && (
                      <span className="text-xs text-gray-600">
                        {(row.trend_pct ?? 0) > 0 ? "+" : ""}{row.trend_pct}%
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-lg bg-white/50">
                    <span className="text-xs text-gray-600 font-semibold block mb-1">TOTAL VALUE</span>
                    <div className="text-sm font-semibold text-gray-900">
                      ${(row.total_value / 1000).toFixed(1)}K
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-white/50">
                    <span className="text-xs text-gray-600 font-semibold block mb-1">DAYS SINCE REVIEW</span>
                    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold border ${getDaysBadgeColor(row.days_without_review)}`}>
                      {row.days_without_review}d
                    </span>
                  </div>

                  <div className="md:col-span-2">
                    <span className="text-xs text-gray-600 font-semibold block mb-2">RECOMMENDED ACTION</span>
                    <span className={`inline-block px-3 py-1 rounded-lg text-xs font-semibold border ${getActionBadgeColor(action.color)}`}>
                      {action.label} · {action.reason}
                    </span>
                  </div>
                </div>

                {/* Quick Action Buttons */}
                <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
                  <button
                    onClick={() => router.push(`/alerts/${row.alert_id}`)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-100 rounded-lg transition"
                  >
                    <Eye size={14} />
                    View Alert
                  </button>

                  <button
                    onClick={() => router.push(`/auto-reallocation?alert_id=${row.alert_id}`)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-emerald-600 hover:bg-emerald-100 rounded-lg transition"
                  >
                    <Shuffle size={14} />
                    Rebalance
                  </button>

                  <button
                    onClick={() => router.push(`/contact-scheduler`)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-amber-600 hover:bg-amber-100 rounded-lg transition"
                  >
                    <Phone size={14} />
                    Contact
                  </button>

                  <button
                    onClick={() => router.push(`/alerts/${row.alert_id}`)}
                    className="ml-auto flex items-center gap-1 px-2 py-2 text-gray-500 hover:text-gray-900 rounded-lg hover:bg-gray-200 transition"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* AI Responsibility Boundary */}
      <div className="space-y-3">
        {/* Purpose Card */}
        <div className="card p-4 bg-gradient-to-r from-blue-50 to-blue-100 border border-blue-200">
          <div className="flex items-start gap-3">
            <Brain size={18} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-blue-900 mb-1">What This Dashboard Does</h3>
              <p className="text-xs text-blue-900 leading-relaxed">
                Forward-looking risk intelligence for your portfolio. AI identifies which clients need attention based on trend direction—rising, falling, or stable—and predicts 30-day risk trajectory. Surfaces stale alerts that may need re-review.
              </p>
            </div>
          </div>
        </div>

        {/* Responsibility Boundary */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* AI Responsibility */}
          <div className="card p-4 bg-blue-50 border border-blue-200">
            <div className="flex items-start gap-3">
              <LineChart size={16} className="text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-blue-900 uppercase tracking-wider mb-2">AI Analyzes</h4>
                <ul className="space-y-1 text-xs text-blue-900">
                  <li>✓ Compares risk scores over time (trend detection)</li>
                  <li>✓ Predicts 30-day risk direction (RISING, FALLING, STABLE)</li>
                  <li>✓ Flags portfolios aging without review</li>
                  <li>✓ Highlights recommended actions based on risk patterns</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Human Responsibility */}
          <div className="card p-4 bg-emerald-50 border border-emerald-200">
            <div className="flex items-start gap-3">
              <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-emerald-900 uppercase tracking-wider mb-2">You Decide</h4>
                <ul className="space-y-1 text-xs text-emerald-900">
                  <li>✓ Intervention timing and urgency</li>
                  <li>✓ Rebalancing strategy & target allocations</li>
                  <li>✓ Client contact approach & messaging</li>
                  <li>✓ Whether to escalate or wait</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky Batch Action Bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-sm font-semibold text-gray-900">
                {selectedIds.size} portfolio{selectedIds.size !== 1 ? "s" : ""} selected
              </span>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleMarkAllReviewed}
                disabled={batchLoading}
                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <CheckCircle2 size={16} />
                {batchLoading ? "Marking..." : "Mark All Reviewed"}
              </button>

              <button
                onClick={handleRunPlaybook}
                disabled={batchLoading}
                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Zap size={16} />
                Run Simulation Playbook
              </button>

              <button
                onClick={() => setSelectedIds(new Set())}
                className="px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
