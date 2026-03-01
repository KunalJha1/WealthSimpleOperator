"use client";

import { useEffect, useState } from "react";
import { fetchTaxLossOpportunities } from "../../lib/api";
import type { TaxLossResponse, TaxLossOpportunity } from "../../lib/types";
import { Scissors, AlertTriangle, Activity, AlertCircle, ChevronDown, ChevronUp, TrendingDown, Flag } from "lucide-react";
import { formatCurrency } from "../../lib/utils";

export default function TaxLossHarvestingPage() {
  const [data, setData] = useState<TaxLossResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"tax_savings" | "unrealized_loss">("tax_savings");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

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

  const getSortedOpportunities = () => {
    if (!data) return [];
    const sorted = [...data.opportunities];
    if (sortBy === "tax_savings") {
      sorted.sort((a, b) => b.tax_savings_estimate - a.tax_savings_estimate);
    } else if (sortBy === "unrealized_loss") {
      sorted.sort((a, b) => b.unrealized_loss - a.unrealized_loss);
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
            <p className="text-xs text-ws-muted mt-1">@ 20% capital gains rate</p>
          </div>
          <div className="card p-4">
            <div className="text-xs text-ws-muted font-semibold uppercase tracking-wider mb-2">Portfolios</div>
            <div className="text-2xl font-semibold text-gray-900">{data.portfolios_with_opportunities}</div>
            <p className="text-xs text-ws-muted mt-1">With opportunities</p>
          </div>
        </div>
      </header>

      {/* Sort Controls */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-ws-muted font-semibold uppercase tracking-wider">Sort by:</span>
        <div className="flex gap-2">
          <button
            onClick={() => setSortBy("tax_savings")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
              sortBy === "tax_savings"
                ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            💰 Tax Savings
          </button>
          <button
            onClick={() => setSortBy("unrealized_loss")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
              sortBy === "unrealized_loss"
                ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                : "bg-white border border-ws-border text-gray-600 hover:border-gray-400"
            }`}
          >
            📉 Loss Amount
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
                  className="w-full p-4 flex items-center justify-between hover:bg-ws-background transition text-left"
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    {/* Ticker */}
                    <div className="flex-shrink-0 font-semibold text-gray-900 w-12 text-center">
                      {opportunity.ticker}
                    </div>

                    {/* Client Info */}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-gray-900 truncate">{opportunity.client_name}</div>
                      <div className="text-xs text-ws-muted truncate">{opportunity.portfolio_name}</div>
                    </div>

                    {/* Loss & Savings */}
                    <div className="flex-shrink-0 text-right mr-4">
                      <div className="text-sm font-semibold text-red-600">
                        {formatCurrency(opportunity.unrealized_loss)}
                      </div>
                      <div className="text-xs text-emerald-600 font-semibold">
                        Save: {formatCurrency(opportunity.tax_savings_estimate)}
                      </div>
                    </div>

                    {/* Wash Sale Badge */}
                    {opportunity.wash_sale_risk && (
                      <div className="flex-shrink-0">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 border border-amber-300 text-amber-700 text-xs font-semibold rounded">
                          <AlertTriangle size={12} />
                          Wash Sale
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="ml-2">
                    {isExpanded ? (
                      <ChevronUp size={16} className="text-gray-400" />
                    ) : (
                      <ChevronDown size={16} className="text-gray-400" />
                    )}
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
                          Consider <span className="font-semibold">{opportunity.replacement_ticker}</span> to maintain asset class exposure.
                        </p>
                      </div>
                    )}

                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={() => handleFlagForReview(opportunity.ticker, opportunity.client_name)}
                        className="flex-1 flex items-center justify-center gap-2 p-3 rounded-lg bg-emerald-100 text-emerald-700 hover:bg-emerald-200 font-semibold text-sm transition border border-emerald-300"
                      >
                        <Flag size={14} />
                        Flag for Review
                      </button>
                      <button
                        onClick={() => handleCopyDetails(opportunity)}
                        className="flex-1 p-3 rounded-lg bg-white text-gray-700 hover:bg-gray-50 font-semibold text-sm transition border border-ws-border"
                      >
                        📋 Copy Details
                      </button>
                    </div>
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

      {/* Footer AI Boundary */}
      <div className="card p-4 bg-blue-50 border-blue-200">
        <p className="text-xs text-blue-900 leading-relaxed">
          <strong>AI scans and estimates:</strong> Synthetic loss calculations based on portfolio metrics.
          <br />
          <strong>You execute:</strong> Confirm trades considering wash sale rules, client goals, and tax timing.
        </p>
      </div>
    </section>
  );
}
