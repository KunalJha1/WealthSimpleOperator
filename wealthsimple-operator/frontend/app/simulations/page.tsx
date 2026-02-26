
"use client";

import { useMemo, useState } from "react";

import { Button } from "../../components/Buttons";
import { runSimulation } from "../../lib/api";
import type {
  SimulationScenario,
  SimulationSeverity,
  SimulationSummary
} from "../../lib/types";

const DEFAULT_SCENARIO: SimulationScenario = "interest_rate_shock";
const DEFAULT_SEVERITY: SimulationSeverity = "moderate";

export default function SimulationsPage() {
  const [selectedScenario, setSelectedScenario] =
    useState<SimulationScenario>(DEFAULT_SCENARIO);
  const [severity, setSeverity] = useState<SimulationSeverity>(DEFAULT_SEVERITY);
  const [result, setResult] = useState<SimulationSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const impactOverview = useMemo(() => {
    if (!result || result.total_portfolios === 0) {
      return null;
    }
    const total = result.total_portfolios;
    const offPct = (result.portfolios_off_trajectory / total) * 100;
    const onPct = (result.portfolios_on_track / total) * 100;

    return {
      offPct,
      onPct
    };
  }, [result]);

  async function handleRun(scenarioOverride?: SimulationScenario) {
    const scenario = scenarioOverride ?? selectedScenario;
    setSelectedScenario(scenario);
    setRunning(true);
    setError(null);
    try {
      const summary = await runSimulation({ scenario, severity });
      setResult(summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="page-title">Scenario lab</h1>
        <p className="page-subtitle">
          Simulate market events and see which clients are pushed off their required
          trajectory before they happen.
        </p>
      </header>

      <section className="card p-4 md:p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
              Event templates
            </div>
            <p className="mt-1 text-sm text-ws-muted">
              Choose a scenario and severity. The operator will estimate impact on client
              trajectories and surface portfolios needing defensive action.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="text-ws-muted uppercase tracking-[0.18em]">Severity</span>
            <SeverityPill
              label="Mild"
              value="mild"
              active={severity === "mild"}
              onClick={() => setSeverity("mild")}
            />
            <SeverityPill
              label="Moderate"
              value="moderate"
              active={severity === "moderate"}
              onClick={() => setSeverity("moderate")}
            />
            <SeverityPill
              label="Severe"
              value="severe"
              active={severity === "severe"}
              onClick={() => setSeverity("severe")}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <ScenarioCard
            scenario="interest_rate_shock"
            title="Interest rate shock"
            description="Parallel or curve-steepening shifts in rates and their impact on fixed income ladders and liability-matched portfolios."
            selected={selectedScenario === "interest_rate_shock"}
            onSelect={() => setSelectedScenario("interest_rate_shock")}
            onRun={() => handleRun("interest_rate_shock")}
            running={running}
          />
          <ScenarioCard
            scenario="bond_spread_widening"
            title="Bond spread widening"
            description="Credit spread stress across ratings and sectors; identify clients whose income or risk budget is breached."
            selected={selectedScenario === "bond_spread_widening"}
            onSelect={() => setSelectedScenario("bond_spread_widening")}
            onRun={() => handleRun("bond_spread_widening")}
            running={running}
          />
          <ScenarioCard
            scenario="equity_drawdown"
            title="Equity drawdown"
            description="Single-asset, sector, or broad index sell-offs; see which clients fall off-plan given their required return path."
            selected={selectedScenario === "equity_drawdown"}
            onSelect={() => setSelectedScenario("equity_drawdown")}
            onRun={() => handleRun("equity_drawdown")}
            running={running}
          />
          <ScenarioCard
            scenario="multi_asset_regime_change"
            title="Multi-asset regime change"
            description="Combined moves in rates, equities, FX, and volatility to test portfolios against complex macro regimes."
            selected={selectedScenario === "multi_asset_regime_change"}
            onSelect={() => setSelectedScenario("multi_asset_regime_change")}
            onRun={() => handleRun("multi_asset_regime_change")}
            running={running}
          />
        </div>

        <div className="flex justify-end">
          <Button onClick={() => handleRun()} disabled={running}>
            {running ? "Running simulation..." : "Run selected scenario"}
          </Button>
        </div>
        {error && (
          <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
            <div className="font-medium">Unable to run scenario</div>
            <div className="mt-1">{error}</div>
            <div className="mt-1 text-[11px] text-red-700">
              Check that the simulation backend is running and reachable from this browser session,
              then try again.
            </div>
          </div>
        )}
      </section>

      <section className="card p-4 md:p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
              Impact preview
            </div>
            {result && (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-ws-muted">
                <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-800">
                  {result.scenario.replace(/_/g, " ")}
                </span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    result.severity === "severe"
                      ? "bg-red-100 text-red-800"
                      : result.severity === "moderate"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {result.severity.toUpperCase()}
                </span>
              </div>
            )}
            <p className="mt-2 text-sm text-ws-muted">
              {result
                ? result.ai_summary
                : "Run a scenario to see how many clients are pushed off trajectory, which portfolios are most exposed, and what defensive levers to consider."}
            </p>
          </div>
          <Button variant="secondary" disabled={!result}>
            Configure defensive playbook
          </Button>
        </div>

        {result && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <ImpactStat
                label="Clients off trajectory"
                value={result.clients_off_trajectory}
                helper={`of ${result.total_clients} clients`}
              />
              <ImpactStat
                label="Portfolios off trajectory"
                value={result.portfolios_off_trajectory}
                helper={`of ${result.total_portfolios} portfolios`}
              />
              <ImpactStat
                label="Portfolios still on plan"
                value={result.portfolios_on_track}
              />
              <ImpactStat
                label="Scenario severity"
                value={result.severity}
                helper={result.scenario.replace(/_/g, " ")}
              />
            </div>

            {impactOverview && (
              <div className="space-y-1 text-[11px] text-ws-muted">
                <div className="flex items-center justify-between">
                  <span>Universe coverage</span>
                  <span>
                    {impactOverview.offPct.toFixed(1)}% off trajectory ·{" "}
                    {impactOverview.onPct.toFixed(1)}% on plan
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full bg-red-400"
                    style={{ width: `${impactOverview.offPct}%` }}
                  />
                  <div
                    className="h-full bg-emerald-500"
                    style={{ width: `${impactOverview.onPct}%` }}
                  />
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  AI proactive steps checklist
                </div>
                <ul className="list-disc pl-4 text-xs text-gray-800 space-y-1">
                  {result.ai_checklist.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Most exposed portfolios
                </div>
                <div className="border border-ws-border rounded-lg overflow-hidden bg-white">
                  <table className="min-w-full text-xs">
                    <thead className="bg-gray-50 text-ws-muted">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">Client</th>
                        <th className="px-3 py-2 text-left font-medium">Portfolio</th>
                        <th className="px-3 py-2 text-right font-medium">Risk Δ</th>
                        <th className="px-3 py-2 text-right font-medium">Scenario risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.impacted_portfolios.slice(0, 6).map((impact, idx) => (
                        <tr
                          key={`${impact.portfolio.id}-${impact.client.id}-${idx}`}
                          className={
                            impact.off_trajectory
                              ? "bg-red-50/60 text-red-900"
                              : "text-gray-900"
                          }
                        >
                          <td className="px-3 py-1.5">
                            <div className="font-medium">{impact.client.name}</div>
                            <div className="text-[10px] text-ws-muted">
                              {impact.client.segment} · {impact.client.risk_profile}
                            </div>
                          </td>
                          <td className="px-3 py-1.5">
                            <div className="font-medium">{impact.portfolio.name}</div>
                            <div className="text-[10px] text-ws-muted">
                              {impact.off_trajectory ? "Off trajectory" : "Within plan band"}
                            </div>
                          </td>
                          <td className="px-3 py-1.5 text-right">
                            {impact.delta_risk.toFixed(1)}
                          </td>
                          <td className="px-3 py-1.5 text-right">
                            {impact.risk_after.toFixed(1)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ScenarioCard({
  scenario,
  title,
  description,
  selected,
  onSelect,
  onRun,
  running
}: {
  scenario: SimulationScenario;
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect();
        }
      }}
      className={`text-left rounded-lg border bg-white p-3 space-y-2 transition-colors cursor-pointer ${
        selected ? "border-ws-ink shadow-sm" : "border-ws-border hover:bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-gray-900">{title}</div>
          <div className="mt-1 text-xs text-ws-muted">{description}</div>
        </div>
        <span
          className={`mt-0.5 inline-flex h-2.5 w-2.5 rounded-full ${
            selected ? "bg-ws-ink" : "bg-gray-200"
          }`}
          aria-hidden="true"
        />
      </div>
      <div className="pt-1">
        <Button
          variant={selected ? "primary" : "secondary"}
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
          disabled={running}
        >
          {running ? "Running..." : "Run this scenario"}
        </Button>
      </div>
    </div>
  );
}

function SeverityPill({
  label,
  value,
  active,
  onClick
}: {
  label: string;
  value: SimulationSeverity;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1 border text-xs font-medium transition-colors ${
        active ? "border-ws-ink bg-ws-ink text-white" : "border-gray-200 bg-white text-gray-800"
      }`}
    >
      {label}
    </button>
  );
}

function ImpactStat({
  label,
  value,
  helper
}: {
  label: string;
  value: number | string;
  helper?: string;
}) {
  return (
    <div className="rounded-lg border border-ws-border bg-white px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ws-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold text-gray-900">{value}</div>
      {helper ? <div className="mt-0.5 text-[11px] text-ws-muted">{helper}</div> : null}
    </div>
  );
}
