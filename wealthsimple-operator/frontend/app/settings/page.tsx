import ResponsibilityBoundary from "../../components/ResponsibilityBoundary";
import { fetchHealth } from "../../lib/api";

export default async function SettingsPage() {
  let health = null;
  let error: string | null = null;

  try {
    health = await fetchHealth();
  } catch (e) {
    error = (e as Error).message;
  }

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
          <div className="mt-3 border-t border-ws-border pt-3 text-xs text-ws-muted">
            To swap providers in this demo, update{" "}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-xs">
              PROVIDER
            </code>{" "}
            and{" "}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-xs">
              GEMINI_API_KEY
            </code>{" "}
            in <span className="font-mono">backend/.env</span>, or adjust the
            provider factory in <span className="font-mono">ai/provider.py</span>.
          </div>
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

      <ResponsibilityBoundary />
    </div>
  );
}

