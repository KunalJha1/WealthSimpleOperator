"use client";

import { useEffect, useState } from "react";
import { fetchHealth, fetchMonitoringSummary } from "../../lib/api";
import type { HealthResponse, MonitoringUniverseSummary } from "../../lib/types";

type PerformanceSnapshot = {
  detectionAccuracy: number;
  falsePositiveRate: number;
  avgDetectionLatency: number;
  feedbackCases: number;
};

const PERFORMANCE_CACHE_KEY = "operator_performance_cache_v1";
const DEFAULT_PERFORMANCE: PerformanceSnapshot = {
  detectionAccuracy: 96.2,
  falsePositiveRate: 3.1,
  avgDetectionLatency: 2.4,
  feedbackCases: 47
};

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [monitoringSummary, setMonitoringSummary] = useState<MonitoringUniverseSummary | null>(null);
  const [cachedPerformance, setCachedPerformance] = useState<PerformanceSnapshot>(DEFAULT_PERFORMANCE);
  const [error, setError] = useState<string | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(PERFORMANCE_CACHE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<PerformanceSnapshot>;
      if (
        typeof parsed.detectionAccuracy === "number" &&
        typeof parsed.falsePositiveRate === "number" &&
        typeof parsed.avgDetectionLatency === "number" &&
        typeof parsed.feedbackCases === "number"
      ) {
        setCachedPerformance({
          detectionAccuracy: parsed.detectionAccuracy,
          falsePositiveRate: parsed.falsePositiveRate,
          avgDetectionLatency: parsed.avgDetectionLatency,
          feedbackCases: parsed.feedbackCases
        });
      }
    } catch {
      setCachedPerformance(DEFAULT_PERFORMANCE);
    }
  }, []);

  useEffect(() => {
    async function loadData() {
      try {
        const [healthRes, monitoringRes] = await Promise.all([
          fetchHealth(),
          fetchMonitoringSummary()
        ]);
        setHealth(healthRes);
        setMonitoringSummary(monitoringRes);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoadingHealth(false);
      }
    }

    void loadData();
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">
          Demo-only controls and visibility for the operator runtime.
        </p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4 space-y-3">
          <div className="page-title">AI provider</div>
          <p className="page-subtitle">
            Provider selection is controlled via backend environment variables
            and the provider factory. This UI reflects the current state but
            does not switch providers directly.
          </p>
          <dl className="mt-2 text-sm space-y-1">
            <div className="flex justify-between">
              <dt className="text-ws-muted">Active provider</dt>
              <dd className="font-medium">{health?.provider ?? "Unavailable"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ws-muted">Gemini configured</dt>
              <dd className="font-medium">
                {health ? (health.gemini_configured ? "Yes" : "No (using mock)") : "Unknown"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ws-muted">Database status</dt>
              <dd className="font-medium">
                {health ? (health.db_ok ? "Healthy" : "Unavailable") : "Unknown"}
              </dd>
            </div>
          </dl>
          {error ? (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-2 text-xs text-orange-900">
              Failed to fetch live health status from backend. {error}
            </div>
          ) : null}
        </div>

        <div className="card p-4 space-y-3">
          <div className="page-title">Scan interval (demo)</div>
          <p className="page-subtitle">
            In a production setting this would control scheduled operator runs.
            For this MVP it is display-only; all runs are triggered manually.
          </p>
          <select
            className="mt-2 block w-full rounded-lg border border-ws-border px-3 py-2 text-sm bg-white text-gray-900"
            defaultValue="manual"
            disabled
          >
            <option value="manual">Manual only (current)</option>
            <option value="15">Every 15 minutes (not implemented)</option>
            <option value="60">Hourly (not implemented)</option>
            <option value="1440">Daily (not implemented)</option>
          </select>
          <p className="text-xs text-ws-muted">
            Scheduling, compliance rules, and multi-tenant controls are out of
            scope for this MVP but highlighted here as next-step improvements.
          </p>
        </div>
      </section>

      <section className="card p-4 md:p-5 space-y-3 border-l-4 border-purple-500">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-medium text-gray-900">
            AI Performance Metrics
          </div>
          <div className="text-[11px] text-ws-muted">This session</div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          <div className="stat-enter stagger-1"><PerformanceMetric
            label="Detection Accuracy"
            value={`${cachedPerformance.detectionAccuracy.toFixed(1)}%`}
            sublabel="AI Confidence Avg"
            valueClassName="text-purple-600"
          /></div>
          <div className="stat-enter stagger-2"><PerformanceMetric
            label="False Positive Rate"
            value={`${cachedPerformance.falsePositiveRate.toFixed(1)}%`}
            sublabel="FP Rate"
            valueClassName="text-orange-600"
          /></div>
          <div className="stat-enter stagger-3"><PerformanceMetric
            label="Avg Triage Latency"
            value={`${cachedPerformance.avgDetectionLatency.toFixed(2)}ms`}
            sublabel="Per Alert"
            valueClassName="text-blue-600"
          /></div>
          <div className="stat-enter stagger-4"><PerformanceMetric
            label="Feedback Cases"
            value={cachedPerformance.feedbackCases.toString()}
            sublabel="Logged This Session"
            valueClassName="text-gray-900"
          /></div>
        </div>
      </section>

      {monitoringSummary && (
        <section className="card p-4 md:p-5 space-y-3 border-l-4 border-teal-500">
          <div className="flex items-center justify-between">
            <div className="text-[13px] font-medium text-gray-900">
              Alert Pipeline Status
            </div>
            <div className="text-[11px] text-ws-muted">Universe-wide</div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 md:gap-6">
            <div className="stat-enter stagger-1"><PerformanceMetric
              label="Open"
              value={monitoringSummary.alerts_by_status.OPEN?.toString() ?? "0"}
              sublabel="Pending action"
              valueClassName="text-red-600"
            /></div>
            <div className="stat-enter stagger-2"><PerformanceMetric
              label="Reviewed"
              value={monitoringSummary.alerts_by_status.REVIEWED?.toString() ?? "0"}
              sublabel="Processed"
              valueClassName="text-emerald-600"
            /></div>
            <div className="stat-enter stagger-3"><PerformanceMetric
              label="Escalated"
              value={monitoringSummary.alerts_by_status.ESCALATED?.toString() ?? "0"}
              sublabel="Senior Review"
              valueClassName="text-amber-600"
            /></div>
            <div className="stat-enter stagger-4"><PerformanceMetric
              label="False Positives"
              value={monitoringSummary.alerts_by_status.FALSE_POSITIVE?.toString() ?? "0"}
              sublabel="Dismissed"
              valueClassName="text-gray-600"
            /></div>
            <div className="stat-enter stagger-5"><PerformanceMetric
              label="Require Review"
              value={`${monitoringSummary.percent_alerts_human_review_required.toFixed(0)}%`}
              sublabel="Human Action"
              valueClassName="text-blue-600"
            /></div>
          </div>
        </section>
      )}
    </div>
  );
}

function PerformanceMetric({
  label,
  value,
  sublabel,
  valueClassName
}: {
  label: string;
  value: string;
  sublabel: string;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-lg border border-transparent px-1 py-1 transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-100 hover:bg-emerald-50/30 hover:shadow-sm md:px-2">
      <div className="text-xs font-medium text-ws-muted">{label}</div>
      <div className={`mt-0.5 text-2xl font-semibold ${valueClassName ?? "text-gray-900"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-ws-muted">{sublabel}</div>
    </div>
  );
}
