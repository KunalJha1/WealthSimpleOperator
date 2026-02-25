import { fetchMonitoringSummary } from "../../lib/api";

export default async function MonitoringUniversePage() {
  let summary = null;
  let error: string | null = null;

  try {
    summary = await fetchMonitoringSummary();
  } catch (e) {
    error = (e as Error).message;
  }

  if (!summary) {
    return (
      <div className="space-y-4">
        <header>
          <h1 className="page-title">Monitoring universe</h1>
          <p className="page-subtitle">
            High-level view of portfolios under monitoring and operator throughput.
          </p>
        </header>
        <div className="card border-orange-200 bg-orange-50 p-4 text-sm text-orange-900">
          Unable to load monitoring metrics right now. Ensure the backend is running on
          <span className="mx-1 font-mono text-xs">NEXT_PUBLIC_API_BASE_URL</span>
          and refresh this page.
          {error ? <div className="mt-2 text-xs text-orange-800">{error}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="page-title">Monitoring universe</h1>
        <p className="page-subtitle">
          High-level view of the portfolios under monitoring and operator
          throughput.
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Clients" value={summary.total_clients} />
        <MetricCard label="Portfolios" value={summary.total_portfolios} />
        <MetricCard
          label="Avg alerts per run"
          value={summary.average_alerts_per_run.toFixed(1)}
        />
        <MetricCard
          label="% alerts needing human review"
          value={`${summary.percent_alerts_human_review_required.toFixed(1)}%`}
        />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="page-title">Alerts by priority</div>
          <div className="mt-3 space-y-2 text-sm">
            {(["HIGH", "MEDIUM", "LOW"] as const).map((p) => (
              <BarRow
                key={p}
                label={p}
                value={summary.alerts_by_priority[p]}
                total={Object.values(summary.alerts_by_priority).reduce(
                  (acc, v) => acc + v,
                  0
                )}
              />
            ))}
          </div>
        </div>
        <div className="card p-4">
          <div className="page-title">Alerts by status</div>
          <div className="mt-3 space-y-2 text-sm">
            {(
              ["OPEN", "REVIEWED", "ESCALATED", "FALSE_POSITIVE"] as const
            ).map((s) => (
              <BarRow
                key={s}
                label={s}
                value={summary.alerts_by_status[s]}
                total={Object.values(summary.alerts_by_status).reduce(
                  (acc, v) => acc + v,
                  0
                )}
              />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border border-ws-border rounded-lg px-3 py-2">
      <div className="text-xs text-ws-muted">{label}</div>
      <div className="text-xl font-semibold text-gray-900">{value}</div>
    </div>
  );
}

function BarRow({
  label,
  value,
  total
}: {
  label: string;
  value: number;
  total: number;
}) {
  const pct = total ? (value / total) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-ws-muted mb-1">
        <span>{label}</span>
        <span>
          {value} ({pct.toFixed(0)}%)
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-ws-green rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

