"use client";

import { useEffect, useState } from "react";
import { fetchRiskDashboard } from "../../lib/api";
import type { RiskDashboardResponse, RiskClientRow } from "../../lib/types";
import { TrendingUp, AlertTriangle, Activity, ArrowUp, ArrowDown, ArrowRight, Zap } from "lucide-react";

export default function RiskDashboardPage() {
  const [data, setData] = useState<RiskDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"predicted_30d_risk" | "current_risk" | "days_without_review">(
    "predicted_30d_risk"
  );

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

  const sortedRows = getSortedRows();

  return (
    <section className="space-y-5 page-enter">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
            <TrendingUp size={24} className="text-blue-600" />
          </div>
          <div>
            <h1 className="page-title">Risk Dashboard</h1>
            <p className="text-xs text-ws-muted font-semibold tracking-wide">FORWARD-LOOKING RISK ANALYSIS</p>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Avg Current Risk</div>
            <div className="text-3xl font-semibold text-gray-900">{data.avg_current_risk.toFixed(1)}</div>
            <p className="text-xs text-ws-muted mt-1">out of 10</p>
          </div>

          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Predicted 30d</div>
            <div className="text-3xl font-semibold text-blue-600">{data.avg_predicted_risk.toFixed(1)}</div>
            <p className="text-xs text-ws-muted mt-1">Trend-adjusted</p>
          </div>

          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Rising Trend</div>
            <div className="text-3xl font-semibold text-red-600">{data.rising_count}</div>
            <p className="text-xs text-ws-muted mt-1">Upward trajectories</p>
          </div>

          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">High Risk ≥7</div>
            <div className="text-3xl font-semibold text-red-600">{data.high_risk_count}</div>
            <p className="text-xs text-ws-muted mt-1">Urgent attention</p>
          </div>
        </div>
      </header>

      {/* Sort Controls */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Sort by:</span>
        <div className="flex gap-2">
          <button
            onClick={() => setSortBy("predicted_30d_risk")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
              sortBy === "predicted_30d_risk"
                ? "bg-blue-100 text-blue-700 border border-blue-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            📊 Predicted
          </button>
          <button
            onClick={() => setSortBy("current_risk")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
              sortBy === "current_risk"
                ? "bg-blue-100 text-blue-700 border border-blue-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            📈 Current
          </button>
          <button
            onClick={() => setSortBy("days_without_review")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
              sortBy === "days_without_review"
                ? "bg-blue-100 text-blue-700 border border-blue-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            ⏱️ Review Age
          </button>
        </div>
      </div>

      {/* Portfolio Rows */}
      <div className="space-y-3">
        {sortedRows.length === 0 ? (
          <div className="card p-12 text-center">
            <TrendingUp className="w-8 h-8 text-ws-muted mx-auto mb-2" />
            <p className="text-sm text-ws-muted">No portfolios with risk data</p>
          </div>
        ) : (
          sortedRows.map((row) => (
            <div
              key={`${row.client_id}-${row.portfolio_id}`}
              className={`card p-5 space-y-4 ${getRiskBgColor(row.predicted_30d_risk)}`}
            >
              {/* Top Row: Client Info & Risk Scores */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="md:col-span-2">
                  <h3 className="font-semibold text-gray-900">{row.client_name}</h3>
                  <p className="text-sm text-gray-600 mt-1">{row.portfolio_name}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-600 mt-2">
                    <span>{row.segment}</span>
                    <span>•</span>
                    <span>{row.risk_profile}</span>
                  </div>
                </div>

                <div className="text-sm">
                  <span className="text-xs text-gray-600 font-semibold block mb-1">CURRENT RISK</span>
                  <div className={`text-2xl font-semibold ${getRiskTextColor(row.current_risk)}`}>
                    {row.current_risk.toFixed(1)}
                  </div>
                </div>

                <div className="text-sm">
                  <span className="text-xs text-gray-600 font-semibold block mb-1">PREDICTED 30D</span>
                  <div className={`text-2xl font-semibold ${getRiskTextColor(row.predicted_30d_risk)}`}>
                    {row.predicted_30d_risk.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* Bottom Row: Trend, Days, Status */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-gray-200">
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

                <div className="p-3 rounded-lg bg-white/50">
                  <span className="text-xs text-gray-600 font-semibold block mb-1">STATUS</span>
                  <div className="text-xs font-semibold text-gray-900">
                    {row.latest_alert_status}{row.latest_priority && ` • ${row.latest_priority}`}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer AI Boundary */}
      <div className="card p-4 bg-blue-50 border-blue-200">
        <p className="text-xs text-blue-900 leading-relaxed">
          <strong>AI analyzes trends:</strong> Compares consecutive alert scores to predict 30-day risk direction.
          <br />
          <strong>You decide action:</strong> Intervention timing, strategy, and client communication approach.
        </p>
      </div>
    </section>
  );
}
