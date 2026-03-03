"use client";

import { useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchTaxLossOpportunities } from "../../lib/api";
import type { TaxLossResponse, TaxLossOpportunity } from "../../lib/types";
import { Scissors, AlertTriangle, Activity, AlertCircle, ChevronDown, ChevronUp, TrendingDown, Flag, Info, Copy, Zap, Calendar, Download, CheckCircle2 } from "lucide-react";
import { formatCurrency } from "../../lib/utils";

function TaxLossHarvestingContent() {
  const searchParams = useSearchParams();
  const clientIdParam = searchParams.get("client_id");
  const portfolioIdParam = searchParams.get("portfolio_id");
  const targetClientId = clientIdParam ? Number.parseInt(clientIdParam, 10) : null;
  const targetPortfolioId = portfolioIdParam ? Number.parseInt(portfolioIdParam, 10) : null;

  const [data, setData] = useState<TaxLossResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"tax_savings" | "unrealized_loss">("tax_savings");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [executionScheduled, setExecutionScheduled] = useState<Set<string>>(new Set());
  const [executionDates, setExecutionDates] = useState<Record<string, string>>({});

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const response = await fetchTaxLossOpportunities();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load tax-loss opportunities");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const targetOpportunityKey = useMemo(() => {
    if (!data) return null;

    if (Number.isFinite(targetPortfolioId)) {
      const exactMatch = data.opportunities.find(
        (opportunity) =>
          opportunity.portfolio_id === targetPortfolioId &&
          (!Number.isFinite(targetClientId) || opportunity.client_id === targetClientId)
      );
      if (exactMatch) {
        return `${exactMatch.portfolio_id}-${exactMatch.ticker}`;
      }
    }

    if (Number.isFinite(targetClientId)) {
      const clientMatch = data.opportunities.find(
        (opportunity) => opportunity.client_id === targetClientId
      );
      if (clientMatch) {
        return `${clientMatch.portfolio_id}-${clientMatch.ticker}`;
      }
    }

    return null;
  }, [data, targetClientId, targetPortfolioId]);

  useEffect(() => {
    if (!targetOpportunityKey) return;
    setExpandedId(targetOpportunityKey);
  }, [targetOpportunityKey]);

  const getSortedOpportunities = () => {
    if (!data) return [];
    const sorted = [...data.opportunities];
    if (sortBy === "tax_savings") {
      sorted.sort((a, b) => b.tax_savings_estimate - a.tax_savings_estimate);
    } else if (sortBy === "unrealized_loss") {
      sorted.sort((a, b) => b.unrealized_loss - a.unrealized_loss);
    }

    if (targetOpportunityKey) {
      sorted.sort((a, b) => {
        const aIsTarget = `${a.portfolio_id}-${a.ticker}` === targetOpportunityKey;
        const bIsTarget = `${b.portfolio_id}-${b.ticker}` === targetOpportunityKey;
        if (aIsTarget && !bIsTarget) return -1;
        if (!aIsTarget && bIsTarget) return 1;
        return 0;
      });
    }

    return sorted;
  };


  const handleFlagForReview = (ticker: string, clientName: string) => {
    setActionFeedback(`✓ ${ticker} at ${clientName} flagged for review. Added to your queue.`);
    setTimeout(() => setActionFeedback(null), 4000);
  };

  const handleCopyDetails = async (opportunity: TaxLossOpportunity) => {
    try {
      const details = `${opportunity.ticker} - ${opportunity.client_name} (${opportunity.portfolio_name})
Unrealized Loss: ${formatCurrency(opportunity.unrealized_loss)}
Tax Savings Estimate: ${formatCurrency(opportunity.tax_savings_estimate)}
Cost Basis: ${formatCurrency(opportunity.cost_basis_per_unit)}/unit`;
      await navigator.clipboard.writeText(details);
      setActionFeedback(`✓ Details copied to clipboard for ${opportunity.ticker}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err) {
      setActionFeedback(`Error: Could not copy to clipboard`);
    }
  };

  if (loading) {
    return (
      <section className="space-y-5 page-enter">
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
              <Scissors size={24} className="text-emerald-600" />
            </div>
            <div>
              <h1 className="page-title">Tax-Loss Harvesting</h1>
              <p className="text-xs text-ws-muted font-semibold tracking-wide">OPPORTUNITY SCANNER</p>
            </div>
          </div>
        </header>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Activity className="w-8 h-8 text-ws-muted mx-auto mb-2 animate-spin" />
            <p className="text-sm text-ws-muted">Scanning for opportunities...</p>
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
              <p className="text-xs text-ws-muted font-semibold tracking-wide">Unable to load opportunities</p>
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
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
              <Scissors size={24} className="text-emerald-600" />
            </div>
            <div>
              <h1 className="page-title">Tax-Loss Harvesting</h1>
              <p className="page-subtitle">No data available</p>
            </div>
          </div>
        </header>
      </section>
    );
  }

  const sortedOpportunities = getSortedOpportunities();

  return (
    <section className="space-y-5 page-enter">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
            <Scissors size={24} className="text-emerald-600" />
          </div>
          <div>
            <h1 className="page-title">Tax-Loss Harvesting</h1>
            <p className="text-xs text-ws-muted font-semibold tracking-wide">PRECISION TAX OPTIMIZATION</p>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-3 gap-3">
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Harvestable Loss</div>
            <div className="text-2xl font-semibold text-gray-900">{formatCurrency(data.total_harvestable_loss).split('.')[0]}</div>
            <p className="text-xs text-ws-muted mt-1">Synthetic estimates</p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Est. Tax Savings</div>
            <div className="text-2xl font-semibold text-emerald-600">{formatCurrency(data.total_tax_savings).split('.')[0]}</div>
            <p className="text-xs text-ws-muted mt-1">Segment-adjusted CG rates</p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Portfolios</div>
            <div className="text-2xl font-semibold text-gray-900">{data.portfolios_with_opportunities}</div>
            <p className="text-xs text-ws-muted mt-1">With opportunities</p>
          </div>
        </div>
      </header>

      {/* Intro Card */}
      <div className="card p-5 bg-emerald-50 border border-emerald-200 space-y-2">
        <div className="flex items-start gap-3">
          <Info size={18} className="text-emerald-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-emerald-900">Tax-Loss Harvesting Scanner</p>
            <p className="text-xs text-emerald-800 mt-1">AI scans your portfolios for unrealized losses and estimates tax savings potential. All values are synthetic estimates—you confirm wash sale compliance and execution timing.</p>
          </div>
        </div>
      </div>

      {/* Sort Controls */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Sort by:</span>
        <div className="flex gap-2">
          <button
            onClick={() => setSortBy("tax_savings")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
              sortBy === "tax_savings"
                ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            <TrendingDown size={14} />
            Tax Savings
          </button>
          <button
            onClick={() => setSortBy("unrealized_loss")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
              sortBy === "unrealized_loss"
                ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            <AlertTriangle size={14} />
            Loss Amount
          </button>
        </div>
      </div>

      {/* Opportunities List */}
      <div className="space-y-3">
        {sortedOpportunities.length === 0 ? (
          <div className="card p-12 text-center">
            <TrendingDown className="w-8 h-8 text-ws-muted mx-auto mb-2" />
            <p className="text-sm text-ws-muted">No tax-loss harvesting opportunities at this time</p>
          </div>
        ) : (
          sortedOpportunities.map((opportunity) => {
            const key = `${opportunity.portfolio_id}-${opportunity.ticker}`;
            const isExpanded = expandedId === key;

            return (
              <div key={key} className="card overflow-hidden">
                {/* Row Header */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : key)}
                  className="w-full p-4 hover:bg-ws-background transition text-left"
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Ticker + Client Info */}
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      <div className="flex-shrink-0 w-14">
                        <div className="font-bold text-lg text-gray-900 text-center">{opportunity.ticker}</div>
                      </div>

                      <div className="flex-1 min-w-0 py-1">
                        <div className="text-sm font-semibold text-gray-900">{opportunity.client_name}</div>
                        <div className="text-xs text-ws-muted">{opportunity.portfolio_name}</div>
                      </div>
                    </div>

                    {/* Right: Metrics + Badge + Chevron */}
                    <div className="flex items-start gap-4 flex-shrink-0">
                      {/* Loss & Savings */}
                      <div className="text-right">
                        <div className="text-sm font-semibold text-red-600">
                          {formatCurrency(opportunity.unrealized_loss)}
                        </div>
                        <div className="text-xs text-emerald-600 font-semibold">
                          {formatCurrency(opportunity.tax_savings_estimate)}
                        </div>
                      </div>

                      {/* Wash Sale Badge */}
                      {opportunity.wash_sale_risk && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 border border-amber-300 text-amber-700 text-xs font-semibold rounded whitespace-nowrap">
                          <AlertTriangle size={12} />
                          Wash
                        </span>
                      )}

                      {/* Chevron */}
                      <div className="pt-1">
                        {isExpanded ? (
                          <ChevronUp size={16} className="text-gray-400" />
                        ) : (
                          <ChevronDown size={16} className="text-gray-400" />
                        )}
                      </div>
                    </div>
                  </div>
                </button>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="border-t border-ws-border bg-ws-background p-4 space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Asset Class</span>
                        <div className="text-sm font-semibold text-gray-900">{opportunity.asset_class}</div>
                      </div>

                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Position Value</span>
                        <div className="text-sm font-semibold text-gray-900">
                          {formatCurrency(opportunity.position_value)}
                        </div>
                      </div>

                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Est. Units</span>
                        <div className="text-sm font-semibold text-gray-900">
                          {opportunity.estimated_units.toFixed(2)}
                        </div>
                      </div>

                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Current Price</span>
                        <div className="text-sm font-semibold text-gray-900">
                          {formatCurrency(opportunity.current_price)}
                        </div>
                      </div>

                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Cost Basis</span>
                        <div className="text-sm font-semibold text-gray-900">
                          {formatCurrency(opportunity.cost_basis_per_unit)}
                        </div>
                      </div>

                      <div>
                        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Unrealized Loss</span>
                        <div className="text-sm font-semibold text-red-600">
                          {formatCurrency(opportunity.unrealized_loss)}
                        </div>
                      </div>

                      {opportunity.loss_reason && (
                        <div>
                          <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Loss Context</span>
                          <div className="text-sm font-semibold text-gray-900">{opportunity.loss_reason}</div>
                        </div>
                      )}

                      {opportunity.holding_period_days !== undefined && (
                        <div>
                          <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider block mb-2">Holding Period</span>
                          <div className="text-sm font-semibold text-gray-900">
                            {opportunity.holding_period_days} days
                            <span className="ml-1 text-xs font-normal text-ws-muted">
                              ({opportunity.holding_period_days >= 365 ? "Long-term" : "Short-term"})
                            </span>
                          </div>
                        </div>
                      )}
                    </div>

                    {opportunity.wash_sale_risk && (
                      <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
                        <div className="flex items-start gap-2">
                          <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-semibold text-amber-900 uppercase tracking-wider">Wash Sale Alert</p>
                            <p className="text-xs text-amber-800 mt-1">
                              High concentration detected. Review wash sale rules before reacquiring.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {opportunity.replacement_ticker && (
                      <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200">
                        <p className="text-xs font-semibold text-emerald-900 uppercase tracking-wider mb-1">Suggested Alternative</p>
                        <p className="text-sm text-emerald-900">
                          Consider <span className="font-semibold">{opportunity.replacement_ticker}</span> to maintain {opportunity.asset_class.toLowerCase()} exposure while satisfying the wash sale waiting period.
                        </p>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <button
                        onClick={() => handleFlagForReview(opportunity.ticker, opportunity.client_name)}
                        className="flex items-center justify-center gap-2 p-3 rounded-lg bg-emerald-100 text-emerald-700 hover:bg-emerald-200 font-semibold text-sm transition border border-emerald-300"
                      >
                        <Flag size={14} />
                        Flag
                      </button>
                      <button
                        onClick={() => handleCopyDetails(opportunity)}
                        className="flex items-center justify-center gap-2 p-3 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 font-semibold text-sm transition border border-blue-300"
                      >
                        <Copy size={14} />
                        Copy
                      </button>
                      <button
                        onClick={() => {
                          const key = `${opportunity.portfolio_id}-${opportunity.ticker}`;
                          setExecutionScheduled(prev => {
                            const next = new Set(prev);
                            if (next.has(key)) next.delete(key);
                            else next.add(key);
                            return next;
                          });
                        }}
                        className="flex items-center justify-center gap-2 p-3 rounded-lg bg-amber-100 text-amber-700 hover:bg-amber-200 font-semibold text-sm transition border border-amber-300"
                      >
                        <Calendar size={14} />
                        Schedule
                      </button>
                      <button
                        onClick={() => {
                          const details = `${opportunity.ticker} - ${opportunity.client_name}\nUnrealized Loss: ${formatCurrency(opportunity.unrealized_loss)}\nTax Savings: ${formatCurrency(opportunity.tax_savings_estimate)}\nLoss Context: ${opportunity.loss_reason || 'N/A'}\nHolding Period: ${opportunity.holding_period_days || 365} days\n\nTrade Plan:\nSell Position → Tax Loss Recognition → Reinvest in ${opportunity.replacement_ticker || 'similar exposure'}`;
                          const blob = new Blob([details], { type: "text/plain" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `${opportunity.ticker}-tax-loss-${new Date().toISOString().split('T')[0]}.txt`;
                          a.click();
                          setActionFeedback(`✓ Export downloaded for ${opportunity.ticker}`);
                          setTimeout(() => setActionFeedback(null), 3000);
                        }}
                        className="flex items-center justify-center gap-2 p-3 rounded-lg bg-purple-100 text-purple-700 hover:bg-purple-200 font-semibold text-sm transition border border-purple-300"
                      >
                        <Download size={14} />
                        Export
                      </button>
                    </div>

                    {/* Execution Schedule UI */}
                    {executionScheduled.has(`${opportunity.portfolio_id}-${opportunity.ticker}`) && (
                      <div className="pt-4 mt-4 border-t border-gray-200 space-y-3">
                        <h4 className="text-sm font-semibold text-gray-900">Schedule Execution</h4>
                        <input
                          type="date"
                          value={executionDates[`${opportunity.portfolio_id}-${opportunity.ticker}`] || ""}
                          onChange={(e) => {
                            const key = `${opportunity.portfolio_id}-${opportunity.ticker}`;
                            setExecutionDates(prev => ({
                              ...prev,
                              [key]: e.target.value
                            }));
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        />
                        <button
                          onClick={() => {
                            const key = `${opportunity.portfolio_id}-${opportunity.ticker}`;
                            const date = executionDates[key];
                            if (!date) {
                              setActionFeedback("Please select a date");
                              setTimeout(() => setActionFeedback(null), 3000);
                              return;
                            }
                            setActionFeedback(`✓ Execution scheduled for ${opportunity.ticker} on ${date}`);
                            setTimeout(() => setActionFeedback(null), 4000);
                            setExecutionScheduled(prev => {
                              const next = new Set(prev);
                              next.delete(key);
                              return next;
                            });
                          }}
                          className="w-full flex items-center justify-center gap-2 p-2 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold text-sm transition"
                        >
                          <CheckCircle2 size={14} />
                          Confirm Schedule
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Action Feedback */}
      {actionFeedback && (
        <div className="card p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-900">{actionFeedback}</p>
        </div>
      )}
    </section>
  );
}

export default function TaxLossHarvestingPage() {
  return (
    <Suspense fallback={<div className="p-6 text-center text-gray-600">Loading...</div>}>
      <TaxLossHarvestingContent />
    </Suspense>
  );
}
