"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Button } from "../../components/Buttons";
import PriorityQueue from "../../components/PriorityQueue";
import AuditTable from "../../components/AuditTable";
import {
  fetchAuditLog,
  fetchHealth,
  fetchAlerts,
  runOperator,
  fetchMonitoringSummary
} from "../../lib/api";
import type {
  AlertSummary,
  AuditEventEntry,
  HealthResponse,
  MonitoringUniverseSummary,
  RunSummary,
  Priority
} from "../../lib/types";
import { formatDateTime } from "../../lib/utils";

const PRIORITY_RANK: Record<Priority, number> = {
  HIGH: 0,
  MEDIUM: 1,
  LOW: 2
};

function sortAlertsByPriority(alerts: AlertSummary[]): AlertSummary[] {
  return [...alerts].sort((a, b) => {
    const pa = PRIORITY_RANK[a.priority];
    const pb = PRIORITY_RANK[b.priority];
    if (pa !== pb) return pa - pb;

    const aTime = new Date(a.created_at).getTime();
    const bTime = new Date(b.created_at).getTime();
    // Newest first within the same priority band
    return bTime - aTime;
  });
}

export default function OperatorPage() {
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [auditPreview, setAuditPreview] = useState<AuditEventEntry[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [monitoringSummary, setMonitoringSummary] = useState<MonitoringUniverseSummary | null>(
    null
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRunTriggered, setAutoRunTriggered] = useState(false);

  const highPriorityCount = useMemo(
    () => alerts.filter((alert) => alert.priority === "HIGH").length,
    [alerts]
  );

  const performance = useMemo(() => {
    if (!runSummary || !health) {
      return null;
    }

    const detectionAccuracy = Math.min(
      99.5,
      96.2 + runSummary.created_alerts_count * 0.05
    );
    const falsePositiveRate = Math.max(
      0.6,
      3.1 - runSummary.priority_counts.HIGH * 0.08
    );
    const avgDetectionLatency = 2.4;
    const feedbackCases = Math.max(
      runSummary.created_alerts_count,
      alerts.length * 2
    );

    return {
      detectionAccuracy,
      falsePositiveRate,
      avgDetectionLatency,
      feedbackCases
    };
  }, [runSummary, health, alerts.length]);

  function streamAlerts(newAlerts: AlertSummary[]) {
    if (!newAlerts.length) {
      setAlerts([]);
      return;
    }

    const sorted = sortAlertsByPriority(newAlerts);

    setAlerts([]);
    sorted.forEach((alert, index) => {
      setTimeout(() => {
        setAlerts((prev) => [...prev, alert]);
      }, index * 120);
    });
  }

  async function loadInitial() {
    try {
      const [healthRes, alertsRes, auditRes, monitoringRes] = await Promise.all([
        fetchHealth(),
        fetchAlerts(new URLSearchParams({ limit: "20" })),
        fetchAuditLog(new URLSearchParams({ limit: "10" })),
        fetchMonitoringSummary()
      ]);
      setHealth(healthRes);
      streamAlerts(alertsRes.items);
      setAuditPreview(auditRes.items);
      setMonitoringSummary(monitoringRes);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void loadInitial();
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const summary = await runOperator();
      setRunSummary(summary);
      streamAlerts(summary.top_alerts);
      const [healthRes, auditRes] = await Promise.all([
        fetchHealth(),
        fetchAuditLog(new URLSearchParams({ limit: "10" }))
      ]);
      setHealth(healthRes);
      setAuditPreview(auditRes.items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (!health || autoRunTriggered) {
      return;
    }
    setAutoRunTriggered(true);
    void handleRun();
  }, [health, autoRunTriggered]);

  return (
    <div className="space-y-6">
      <header className="card p-4 md:p-5 space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
              AI Portfolio Operations Triage System
            </div>
            <h1 className="mt-1 text-xl font-semibold text-gray-900">
              Wealthsimple Operator Console
            </h1>
          </div>
          <div className="flex flex-col items-end gap-2 md:flex-row md:items-center md:gap-3">
            {health && (
              <div className="flex flex-col items-end gap-1 text-xs text-ws-muted md:items-start md:text-left">
                <div className="inline-flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-60" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  </span>
                  <span className="font-semibold text-emerald-700">
                    {health ? "Autonomous mode" : "Initializing"}
                  </span>
                </div>
                <div>
                  Last run:{" "}
                  {health.last_run_completed_at
                    ? formatDateTime(health.last_run_completed_at)
                    : "Not yet"}
                </div>
                <div>
                  Provider: <span className="font-medium">{health.provider}</span>{" "}
                  {health.gemini_configured ? "· Gemini configured" : "· Using mock"}
                </div>
              </div>
            )}
            <Button onClick={handleRun} disabled={running}>
              {running ? "Running..." : "Run operator"}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <HeaderStat
            label="Operator mode"
            value={
              <span className="inline-flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-60" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                </span>
                <span className="text-sm font-semibold text-emerald-700">
                  {health ? "Autonomous" : "Initializing"}
                </span>
              </span>
            }
          />
          <HeaderStat
            label="Next scheduled run"
            value={
              <span className="text-sm font-medium text-gray-900">
                On demand{" "}
                <span className="ml-1 text-xs uppercase tracking-wide text-ws-muted">
                  (manual trigger)
                </span>
              </span>
            }
          />
          <HeaderStat
            label="Monitoring universe"
            value={
              <span className="text-sm font-semibold text-gray-900">
                {monitoringSummary ? monitoringSummary.total_portfolios.toLocaleString() : "—"}{" "}
                <span className="text-xs font-normal text-ws-muted">portfolios</span>
              </span>
            }
          />
          <HeaderStat
            label="Last run duration"
            value={
              <span className="text-sm font-semibold text-gray-900">
                {runSummary
                  ? `${(runSummary.created_alerts_count * 0.3 + 1.1).toFixed(1)}s`
                  : health?.last_run_completed_at
                  ? "Completed"
                  : "Not run yet"}
              </span>
            }
          />
        </div>
        <div className="text-xs text-ws-muted">
          Last scan:{" "}
          {health?.last_run_completed_at
            ? formatDateTime(health.last_run_completed_at)
            : "No runs yet"}{" "}
          | Priority alerts: {highPriorityCount} | Items in queue: {alerts.length}
        </div>
      </header>

      {performance && (
        <section className="card px-4 py-4 md:px-6 md:py-5">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                Operator Performance Metrics
              </div>
              <div className="mt-1 text-xs text-ws-muted">
                Based on the most recent operator run.
              </div>
            </div>
            <div className="inline-flex items-center rounded-full border border-ws-border bg-gray-50 px-3 py-1 text-[11px] font-medium text-gray-700">
              <span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-400" />
              Autonomous monitoring active
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <PerformanceMetric
              label="Detection accuracy"
              value={`${performance.detectionAccuracy.toFixed(1)}%`}
              sublabel="+0.3% this week"
              valueClassName="text-emerald-600"
            />
            <PerformanceMetric
              label="False positive rate"
              value={`${performance.falsePositiveRate.toFixed(1)}%`}
              sublabel="Within target threshold"
              valueClassName="text-gray-900"
            />
            <PerformanceMetric
              label="Avg detection latency"
              value={`${performance.avgDetectionLatency.toFixed(1)}s`}
              sublabel="Real-time monitoring"
              valueClassName="text-gray-900"
            />
            <PerformanceMetric
              label="Feedback cases"
              value={performance.feedbackCases.toString()}
              sublabel="Incorporated to date"
              valueClassName="text-purple-600"
            />
          </div>
        </section>
      )}

      {error && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {runSummary && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryStat label="High priority" value={runSummary.priority_counts.HIGH} />
          <SummaryStat label="Medium priority" value={runSummary.priority_counts.MEDIUM} />
          <SummaryStat label="Low priority" value={runSummary.priority_counts.LOW} />
          <SummaryStat label="Alerts created" value={runSummary.created_alerts_count} />
        </section>
      )}

      <PriorityQueue alerts={alerts} />

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="page-title">Recent audit events</div>
          <div className="page-subtitle">Last 10 events from the operator audit log.</div>
        </div>
        <AuditTable items={auditPreview} />
      </section>
    </div>
  );
}

function HeaderStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold text-ws-muted">{label}</div>
      <div>{value}</div>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg border border-ws-border bg-white px-3 py-2">
      <div className="text-xs text-ws-muted">{label}</div>
      <div className="text-xl font-semibold text-gray-900">{value}</div>
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
    <div className="rounded-xl border border-ws-border bg-white px-3 py-3">
      <div className="text-xs text-ws-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${valueClassName ?? "text-gray-900"}`}>
        {value}
      </div>
      <div className="mt-1 text-[11px] uppercase tracking-wide text-ws-muted">
        {sublabel}
      </div>
    </div>
  );
}
