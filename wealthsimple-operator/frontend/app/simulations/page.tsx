
"use client";

import { useMemo, useState } from "react";
import { X, TrendingUp, Zap, AlertTriangle, DollarSign } from "lucide-react";

import { Button } from "../../components/Buttons";
import { runSimulation, fetchSimulationPlaybook } from "../../lib/api";
import type {
  SimulationScenario,
  SimulationSeverity,
  SimulationSummary,
  PlaybookSummary,
  ClientSummary,
  PortfolioSummary
} from "../../lib/types";

const DEFAULT_SCENARIO: SimulationScenario = "interest_rate_shock";
const DEFAULT_SEVERITY: SimulationSeverity = "moderate";

// Scenario context: market moves, affected assets, historical references
const SCENARIO_CONFIG: Record<SimulationScenario, {
  marketMove: string;
  affected: string[];
  notAffected: string[];
  historicalRef: string;
  worstExposure: string;
  icon: React.ReactNode;
}> = {
  interest_rate_shock: {
    marketMove: "+175 bps overnight",
    affected: ["Fixed Income", "Rate-sensitive equities", "Dividend stocks"],
    notAffected: ["Cash", "Commodities"],
    historicalRef: "2022 Bank of Canada tightening cycle",
    worstExposure: "Fixed income-heavy portfolios with long duration",
    icon: <TrendingUp className="w-5 h-5" />
  },
  bond_spread_widening: {
    marketMove: "Credit spreads +200 bps",
    affected: ["Corporate bonds", "Credit-sensitive sectors", "High-yield"],
    notAffected: ["Government bonds", "Cash", "Treasuries"],
    historicalRef: "March 2020 COVID market stress",
    worstExposure: "Investment grade & high-yield bond positions",
    icon: <AlertTriangle className="w-5 h-5" />
  },
  equity_drawdown: {
    marketMove: "-18% broad decline",
    affected: ["Growth stocks", "Technology", "Small-cap equities"],
    notAffected: ["Fixed income", "Cash", "Gold"],
    historicalRef: "2022 bear market & rate-driven selloff",
    worstExposure: "Growth-heavy or 100% equity portfolios",
    icon: <TrendingUp className="w-5 h-5 rotate-180" />
  },
  multi_asset_regime_change: {
    marketMove: "Complex macro shift (rates +150, equities -12%, spreads +100)",
    affected: ["All risk assets", "Diversification breakdown", "Correlation shifts"],
    notAffected: ["Gold", "Cash", "Defensive bonds"],
    historicalRef: "2008 financial crisis stagflation environment",
    worstExposure: "Balanced portfolios relying on traditional diversification",
    icon: <Zap className="w-5 h-5" />
  }
};

// Severity descriptions with real market numbers
const SEVERITY_CONFIG: Record<SimulationSeverity, {
  label: string;
  drawdown: string;
  description: string;
}> = {
  mild: {
    label: "Mild",
    drawdown: "~5% drawdown",
    description: "+50 bps or -5% equity draw"
  },
  moderate: {
    label: "Moderate",
    drawdown: "~12% drawdown",
    description: "+175 bps or -12% equity draw"
  },
  severe: {
    label: "Severe",
    drawdown: "~25% drawdown",
    description: "+350 bps or -25% equity draw"
  }
};

// Helper: Generate narrative summary from results
function scenarioNarrative(result: SimulationSummary): string {
  const clientWord = result.clients_off_trajectory === 1 ? "client" : "clients";
  const portWord = result.portfolios_off_trajectory === 1 ? "portfolio" : "portfolios";
  const pctOff = ((result.clients_off_trajectory / result.total_clients) * 100).toFixed(0);

  return `${result.clients_off_trajectory} ${clientWord} would miss their investment goals. Under this scenario, ${result.portfolios_off_trajectory} ${portWord} drop off their risk-adjusted return path (${pctOff}% of your universe affected).`;
}

// Helper: Calculate estimated at-risk capital from delta_risk
function calculateAtRiskCapital(totalValue: number, deltaRisk: number): number {
  return Math.round(totalValue * (deltaRisk / 10) * 0.15);
}

export default function SimulationsPage() {
  const [selectedScenario, setSelectedScenario] =
    useState<SimulationScenario>(DEFAULT_SCENARIO);
  const [severity, setSeverity] = useState<SimulationSeverity>(DEFAULT_SEVERITY);
  const [result, setResult] = useState<SimulationSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedTable, setExpandedTable] = useState(false);
  const [playbook, setPlaybook] = useState<PlaybookSummary | null>(null);
  const [playbookLoading, setPlaybookLoading] = useState(false);
  const [playbookError, setPlaybookError] = useState<string | null>(null);
  const [selectedClient, setSelectedClient] = useState<{
    client: ClientSummary;
    portfolio: PortfolioSummary;
    risk_before: number;
    risk_after: number;
    delta_risk: number;
    off_trajectory: boolean;
  } | null>(null);

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
    setPlaybook(null);
    try {
      // Add artificial delay to simulate backend processing (1.5-2.5 seconds)
      const startTime = Date.now();
      const minDelay = 1500; // milliseconds

      const summary = await runSimulation({ scenario, severity });

      // Ensure minimum delay has elapsed for better UX
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < minDelay) {
        await new Promise(resolve => setTimeout(resolve, minDelay - elapsedTime));
      }

      setResult(summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  async function handleGeneratePlaybook() {
    if (!result) return;
    setPlaybookLoading(true);
    setPlaybookError(null);
    try {
      const offTrajectoryPortfolios = result.impacted_portfolios
        .filter((p) => p.off_trajectory)
        .map((p) => p.portfolio.id);

      // Add artificial delay to simulate backend processing (1.2-1.8 seconds)
      const startTime = Date.now();
      const minDelay = 1200; // milliseconds

      const playbookResult = await fetchSimulationPlaybook({
        scenario: result.scenario,
        severity: result.severity,
        portfolio_ids: offTrajectoryPortfolios
      });

      // Ensure minimum delay has elapsed for better UX
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < minDelay) {
        await new Promise(resolve => setTimeout(resolve, minDelay - elapsedTime));
      }

      setPlaybook(playbookResult);
    } catch (e) {
      setPlaybookError(e instanceof Error ? e.message : String(e));
    } finally {
      setPlaybookLoading(false);
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
            severity={severity}
          />
          <ScenarioCard
            scenario="bond_spread_widening"
            title="Bond spread widening"
            description="Credit spread stress across ratings and sectors; identify clients whose income or risk budget is breached."
            selected={selectedScenario === "bond_spread_widening"}
            onSelect={() => setSelectedScenario("bond_spread_widening")}
            onRun={() => handleRun("bond_spread_widening")}
            running={running}
            severity={severity}
          />
          <ScenarioCard
            scenario="equity_drawdown"
            title="Equity drawdown"
            description="Single-asset, sector, or broad index sell-offs; see which clients fall off-plan given their required return path."
            selected={selectedScenario === "equity_drawdown"}
            onSelect={() => setSelectedScenario("equity_drawdown")}
            onRun={() => handleRun("equity_drawdown")}
            running={running}
            severity={severity}
          />
          <ScenarioCard
            scenario="multi_asset_regime_change"
            title="Multi-asset regime change"
            description="Combined moves in rates, equities, FX, and volatility to test portfolios against complex macro regimes."
            selected={selectedScenario === "multi_asset_regime_change"}
            onSelect={() => setSelectedScenario("multi_asset_regime_change")}
            onRun={() => handleRun("multi_asset_regime_change")}
            running={running}
            severity={severity}
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
          <div className="flex-1">
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
            {result ? (
              <div className="mt-2 rounded-lg p-3 space-y-1.5">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-600">
                  AI scenario assessment
                </div>
                <p className="text-sm leading-relaxed text-gray-900">{result.ai_summary}</p>
              </div>
            ) : (
              <div className="mt-3 flex flex-col items-center justify-center rounded-xl border border-dashed border-ws-border bg-gray-50 py-10 text-center space-y-2">
                <div className="text-sm font-medium text-gray-700">No simulation run yet</div>
                <p className="text-xs text-ws-muted max-w-xs">
                  Select a scenario and severity above, then click "Run selected scenario" to see
                  how many clients are pushed off trajectory.
                </p>
              </div>
            )}
          </div>
        </div>

        {result && (
          <div className="space-y-4">
            {/* Narrative banner */}
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
              <p className="text-sm text-amber-900">
                <strong>Impact summary:</strong> {scenarioNarrative(result)}
              </p>
            </div>

            {/* Featured risk card */}
            <FeaturedRiskCard result={result} />

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <ImpactStat
                label="Clients off trajectory"
                value={running ? undefined : result.clients_off_trajectory}
                helper={running ? undefined : `of ${result.total_clients} clients`}
                loading={running}
              />
              <ImpactStat
                label="Portfolios off trajectory"
                value={running ? undefined : result.portfolios_off_trajectory}
                helper={running ? undefined : `of ${result.total_portfolios} portfolios`}
                loading={running}
              />
              <ImpactStat
                label="Portfolios still on plan"
                value={running ? undefined : result.portfolios_on_track}
                loading={running}
              />
              <ImpactStat
                label="Scenario severity"
                value={running ? undefined : result.severity.charAt(0).toUpperCase() + result.severity.slice(1)}
                helper={running ? undefined : result.scenario.replace(/_/g, " ")}
                loading={running}
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  AI proactive steps checklist
                </div>
                <ol className="space-y-1.5">
                  {result.ai_checklist.map((item, idx) => (
                    <li key={idx} className="flex gap-2 text-xs text-gray-800">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-700">
                        {idx + 1}
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Impact by portfolio
                </div>
                <div className="border border-ws-border rounded-lg overflow-hidden bg-white">
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-gray-50 text-ws-muted">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">Client</th>
                          <th className="px-3 py-2 text-right font-medium">$ at Risk</th>
                          <th className="px-3 py-2 text-right font-medium">Risk Δ</th>
                          <th className="px-3 py-2 text-left font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {running ? (
                          <>
                            {[...Array(4)].map((_, idx) => (
                              <tr key={`skeleton-${idx}`} className="bg-gray-50 animate-pulse">
                                <td className="px-3 py-1.5">
                                  <div className="h-4 w-20 rounded bg-gray-200" />
                                </td>
                                <td className="px-3 py-1.5 text-right">
                                  <div className="ml-auto h-4 w-16 rounded bg-gray-200" />
                                </td>
                                <td className="px-3 py-1.5 text-right">
                                  <div className="ml-auto h-4 w-10 rounded bg-gray-200" />
                                </td>
                                <td className="px-3 py-1.5">
                                  <div className="h-4 w-20 rounded bg-gray-200" />
                                </td>
                              </tr>
                            ))}
                          </>
                        ) : (
                          (expandedTable
                            ? result.impacted_portfolios
                            : result.impacted_portfolios.slice(0, 6)
                          ).map((impact, idx) => {
                            const atRiskCapital = calculateAtRiskCapital(impact.portfolio.total_value, impact.delta_risk);
                            return (
                              <tr
                                key={`${impact.portfolio.id}-${impact.client.id}-${idx}`}
                                onClick={() => setSelectedClient(impact)}
                                className={`cursor-pointer transition-colors border-t ${
                                  impact.off_trajectory
                                    ? "bg-red-50/60 text-red-900 hover:bg-red-100/60"
                                    : "text-gray-900 hover:bg-gray-50"
                                }`}
                              >
                                <td className="px-3 py-2">
                                  <div className="font-medium text-sm">{impact.client.name}</div>
                                  <div className="text-[10px] text-gray-600 mt-0.5">{impact.portfolio.name}</div>
                                </td>
                                <td className="px-3 py-2 text-right">
                                  <div className="font-semibold">${(atRiskCapital / 1000).toFixed(0)}k</div>
                                </td>
                                <td className="px-3 py-2 text-right">
                                  <span
                                    className={
                                      impact.delta_risk > 0
                                        ? "text-red-700 font-semibold"
                                        : "text-emerald-700 font-semibold"
                                    }
                                  >
                                    {impact.delta_risk > 0 ? "+" : ""}{impact.delta_risk.toFixed(1)}
                                  </span>
                                </td>
                                <td className="px-3 py-2">
                                  <span
                                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                      impact.off_trajectory
                                        ? "bg-red-100 text-red-800"
                                        : "bg-emerald-100 text-emerald-800"
                                    }`}
                                  >
                                    {impact.off_trajectory ? "Off" : "On"}
                                  </span>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                {result.impacted_portfolios.length > 6 && (
                  <div className="flex justify-center pt-2">
                    <button
                      type="button"
                      onClick={() => setExpandedTable(!expandedTable)}
                      className="text-xs font-medium text-ws-ink hover:text-ws-ink/80 transition-colors"
                    >
                      {expandedTable
                        ? `Show less (${6} of ${result.impacted_portfolios.length})`
                        : `Show all (${result.impacted_portfolios.length})`}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {playbook && result && (
        <section className="card p-4 md:p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                Defensive Playbook — Scenario-Specific Actions
              </div>
              <p className="mt-2 text-sm text-gray-700 font-medium">
                {result.scenario === "interest_rate_shock" && "Focus on duration management: short-duration bond swaps and income buffer review."}
                {result.scenario === "bond_spread_widening" && "Focus on credit quality: investment grade migration and yield laddering review."}
                {result.scenario === "equity_drawdown" && "Focus on sequence-of-returns risk: cash buffer and systematic withdrawal strategy review."}
                {result.scenario === "multi_asset_regime_change" && "Focus on regime-aware rebalancing: asset class concentration and diversification review."}
              </p>
              <p className="mt-2 text-xs text-gray-600">{playbook.ai_rationale}</p>
            </div>
            <button
              type="button"
              onClick={() => setPlaybook(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <div className="space-y-4">
              {playbook.actions.map((action, idx) => {
                // Find corresponding impact to show $ at risk
                const impact = result.impacted_portfolios.find(
                  p => p.portfolio.id.toString() === action.portfolio_name
                ) || result.impacted_portfolios[idx];
                const atRiskCapital = impact ? calculateAtRiskCapital(impact.portfolio.total_value, impact.delta_risk) : 0;

                return (
                  <div
                    key={idx}
                    className="rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
                            {action.rank}
                          </span>
                          <div className="font-semibold text-gray-900">
                            {action.client_name}
                          </div>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                            {action.portfolio_name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <div className="text-sm text-gray-700">
                            <span className="font-medium">{action.action_type}</span>
                            {" — "}
                            <span
                              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
                                action.urgency === "Urgent"
                                  ? "border-red-200 bg-red-50 text-red-700"
                                  : action.urgency === "High"
                                  ? "border-amber-200 bg-amber-50 text-amber-700"
                                  : "border-gray-200 bg-gray-50 text-gray-700"
                              }`}
                            >
                              {action.urgency}
                            </span>
                          </div>
                          {impact && (
                            <span className="text-sm font-semibold text-red-700">
                              ${(atRiskCapital / 1000).toFixed(0)}k at risk
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Draft email inline */}
                    <div className="bg-gray-50 rounded-lg border border-gray-200 p-3 space-y-2">
                      <div>
                        <div className="font-semibold text-xs text-gray-700 mb-1">Subject</div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-sm text-gray-800 font-medium">
                          {action.draft_email_subject}
                        </div>
                      </div>
                      <div>
                        <div className="font-semibold text-xs text-gray-700 mb-1">Message</div>
                        <div className="p-2 bg-white rounded border border-gray-200 text-xs text-gray-800 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                          {action.draft_email_body}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
            <div className="text-xs font-semibold text-blue-900 mb-1">
              Playbook Approval
            </div>
            <p className="text-xs text-blue-800 leading-relaxed">
              Review all draft actions and email templates above. Customize as needed for tax efficiency and client circumstances. Approve individual drafts or adjust before sending. Full human responsibility for final client outreach decisions.
            </p>
          </div>
        </section>
      )}

      {playbookError && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Failed to generate playbook: {playbookError}
        </div>
      )}

      {selectedClient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 p-4 md:p-5 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Client Details</h2>
                <p className="text-xs text-ws-muted mt-1">Simulation impact analysis</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedClient(null)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 md:p-5 space-y-6">
              {/* Client Header */}
              <div className="space-y-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                    Client Name
                  </div>
                  <p className="mt-1 text-lg font-semibold text-gray-900">
                    {selectedClient.client.name}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                      Segment
                    </div>
                    <p className="mt-1 text-sm text-gray-900">{selectedClient.client.segment}</p>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                      Risk Profile
                    </div>
                    <p className="mt-1 text-sm text-gray-900">{selectedClient.client.risk_profile}</p>
                  </div>
                </div>

                {selectedClient.client.email && (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                      Email
                    </div>
                    <p className="mt-1 text-sm text-gray-600">{selectedClient.client.email}</p>
                  </div>
                )}
              </div>

              {/* Portfolio Section */}
              <div className="border-t border-gray-200 pt-6 space-y-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                    Portfolio Name
                  </div>
                  <p className="mt-1 text-lg font-semibold text-gray-900">
                    {selectedClient.portfolio.name}
                  </p>
                </div>

                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                    Portfolio Value
                  </div>
                  <p className="mt-1 text-lg font-semibold text-gray-900">
                    ${selectedClient.portfolio.total_value.toLocaleString('en-US', {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0,
                    })}
                  </p>
                </div>

                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted mb-2">
                    Target Allocation
                  </div>
                  <div className="space-y-2">
                    <AllocationBar
                      label="Equity"
                      value={selectedClient.portfolio.target_equity_pct}
                      color="blue"
                    />
                    <AllocationBar
                      label="Fixed Income"
                      value={selectedClient.portfolio.target_fixed_income_pct}
                      color="emerald"
                    />
                    <AllocationBar
                      label="Cash"
                      value={selectedClient.portfolio.target_cash_pct}
                      color="amber"
                    />
                  </div>
                </div>
              </div>

              {/* Risk Impact Section */}
              <div className="border-t border-gray-200 pt-6 space-y-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Scenario Impact
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs text-ws-muted font-medium">Risk Before</div>
                    <p className="mt-2 text-xl font-semibold text-gray-900">
                      {selectedClient.risk_before.toFixed(1)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs text-ws-muted font-medium">Risk Change</div>
                    <p
                      className={`mt-2 text-xl font-semibold ${
                        selectedClient.delta_risk > 0
                          ? "text-red-700"
                          : "text-emerald-700"
                      }`}
                    >
                      {selectedClient.delta_risk > 0 ? "+" : ""}
                      {selectedClient.delta_risk.toFixed(1)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs text-ws-muted font-medium">Risk After</div>
                    <p className="mt-2 text-xl font-semibold text-gray-900">
                      {selectedClient.risk_after.toFixed(1)}
                    </p>
                  </div>
                </div>

                <div
                  className={`rounded-lg border-2 p-3 ${
                    selectedClient.off_trajectory
                      ? "border-red-200 bg-red-50"
                      : "border-emerald-200 bg-emerald-50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                        selectedClient.off_trajectory
                          ? "bg-red-100 text-red-800"
                          : "bg-emerald-100 text-emerald-800"
                      }`}
                    >
                      {selectedClient.off_trajectory ? "Off Trajectory" : "On Plan"}
                    </div>
                    <p
                      className={`text-sm font-medium ${
                        selectedClient.off_trajectory
                          ? "text-red-900"
                          : "text-emerald-900"
                      }`}
                    >
                      {selectedClient.off_trajectory
                        ? "This portfolio may drift from its required trajectory in this scenario."
                        : "This portfolio remains on its required trajectory in this scenario."}
                    </p>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="border-t border-gray-200 pt-6 flex gap-3">
                <Button
                  onClick={() => setSelectedClient(null)}
                  variant="secondary"
                  className="flex-1"
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AllocationBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "blue" | "emerald" | "amber";
}) {
  const colorMap = {
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 text-xs font-medium text-gray-600">{label}</div>
      <div className="flex-1 flex items-center gap-2">
        <div className="flex-1 h-2 rounded-full bg-gray-200 overflow-hidden">
          <div
            className={`h-full ${colorMap[color]}`}
            style={{ width: `${Math.min(value, 100)}%` }}
          />
        </div>
        <div className="w-12 text-right text-xs font-medium text-gray-700">
          {value.toFixed(1)}%
        </div>
      </div>
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
  running,
  severity
}: {
  scenario: SimulationScenario;
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  onRun: () => void;
  running: boolean;
  severity: SimulationSeverity;
}) {
  const config = SCENARIO_CONFIG[scenario];
  const severityConfig = SEVERITY_CONFIG[severity];

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
      className={`text-left rounded-lg border bg-white p-3 space-y-3 transition-colors cursor-pointer ${
        selected ? "border-ws-ink shadow-sm" : "border-ws-border hover:bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">{title}</div>
          <div className="mt-1 text-xs text-gray-600">{severityConfig.description}</div>
        </div>
        <span
          className={`mt-0.5 inline-flex h-2.5 w-2.5 rounded-full ${
            selected ? "bg-ws-ink" : "bg-gray-200"
          }`}
          aria-hidden="true"
        />
      </div>

      <div className="space-y-2 text-xs">
        <div>
          <div className="font-semibold text-gray-700 mb-1">Affected assets</div>
          <div className="flex flex-wrap gap-1">
            {config.affected.map((asset, idx) => (
              <span key={idx} className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-red-700">
                {asset}
              </span>
            ))}
          </div>
        </div>
        <div className="text-[11px] text-ws-muted">
          <span className="font-semibold">Historical ref:</span> {config.historicalRef}
        </div>
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
  const config = SEVERITY_CONFIG[value];

  return (
    <button
      type="button"
      onClick={onClick}
      title={config.description}
      className={`rounded-full px-3 py-1.5 border text-xs font-medium transition-colors ${
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
  helper,
  loading = false
}: {
  label: string;
  value?: number | string;
  helper?: string;
  loading?: boolean;
}) {
  return (
    <div className="rounded-lg border border-ws-border bg-white px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ws-muted">{label}</div>
      {loading ? (
        <div className="mt-2 h-6 w-12 animate-pulse rounded bg-gray-200" />
      ) : (
        <>
          <div className="mt-1 text-lg font-semibold text-gray-900">{value}</div>
          {helper ? <div className="mt-0.5 text-[11px] text-ws-muted">{helper}</div> : null}
        </>
      )}
    </div>
  );
}

function FeaturedRiskCard({
  result
}: {
  result: SimulationSummary;
}) {
  // Find the portfolio with highest delta_risk that is off-trajectory
  const mostAtRisk = result.impacted_portfolios
    .filter(p => p.off_trajectory)
    .sort((a, b) => b.delta_risk - a.delta_risk)[0];

  if (!mostAtRisk) return null;

  const atRiskCapital = calculateAtRiskCapital(mostAtRisk.portfolio.total_value, mostAtRisk.delta_risk);

  return (
    <div className="rounded-lg border-2 border-red-200 bg-red-50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-red-700 shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-red-900">Most at risk — {mostAtRisk.client.name}</h3>
          <p className="text-sm text-red-800 mt-1">{mostAtRisk.portfolio.name}</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
            <div>
              <div className="text-xs text-red-700 font-medium">Total AUM</div>
              <div className="text-lg font-semibold text-red-900 mt-0.5">
                ${(mostAtRisk.portfolio.total_value / 1000).toFixed(0)}k
              </div>
            </div>
            <div>
              <div className="text-xs text-red-700 font-medium">Risk Score</div>
              <div className="text-lg font-semibold text-red-900 mt-0.5">
                {mostAtRisk.risk_before.toFixed(1)} → {mostAtRisk.risk_after.toFixed(1)}
              </div>
            </div>
            <div>
              <div className="text-xs text-red-700 font-medium">Est. at-risk capital</div>
              <div className="text-lg font-semibold text-red-900 mt-0.5">
                ${(atRiskCapital / 1000).toFixed(0)}k
              </div>
            </div>
            <div>
              <div className="text-xs text-red-700 font-medium">% of portfolio</div>
              <div className="text-lg font-semibold text-red-900 mt-0.5">
                {((atRiskCapital / mostAtRisk.portfolio.total_value) * 100).toFixed(0)}%
              </div>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-red-200 text-sm text-red-900">
            <div className="font-medium mb-1">Why exposed:</div>
            <p className="text-[13px]">
              {mostAtRisk.portfolio.target_fixed_income_pct > 50
                ? `Fixed income weight (${mostAtRisk.portfolio.target_fixed_income_pct.toFixed(0)}%) far exceeds target (40%). Duration mismatch in rising rate scenario.`
                : mostAtRisk.portfolio.target_equity_pct > 80
                ? `Equity concentration (${mostAtRisk.portfolio.target_equity_pct.toFixed(0)}%) exposes portfolio to market drawdown risk.`
                : "Portfolio allocation creates exposure to this scenario's key risk factors."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
