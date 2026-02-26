"use client";

import { useMemo, useState } from "react";
import { fetchAlert } from "../lib/api";
import { AlertDetail, MonitoringClientRow, MonitoringQueuedCase } from "../lib/types";
import { ClientDetailsPanel } from "./RiskBrief";

type SortKey =
  | "client_name"
  | "client_since_year"
  | "total_aum"
  | "daily_pnl"
  | "daily_pnl_pct"
  | "ytd_performance_pct"
  | "open_alerts"
  | "queued_for_review"
  | "last_alert_at";

type SortDirection = "asc" | "desc";

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
}

function formatPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleString();
}

function sortValue(row: MonitoringClientRow, key: SortKey): string | number {
  if (key === "client_name") return row.client_name.toLowerCase();
  if (key === "last_alert_at") return row.last_alert_at ? new Date(row.last_alert_at).getTime() : 0;
  return row[key];
}

export default function MonitoringUniverseExplorer({
  clients,
  queuedCases
}: {
  clients: MonitoringClientRow[];
  queuedCases: MonitoringQueuedCase[];
}) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("total_aum");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedAlert, setSelectedAlert] = useState<AlertDetail | null>(null);
  const [, setLoadingAlert] = useState(false);
  const PAGE_SIZE = 20;

  const filteredAndPagedClients = useMemo(() => {
    const query = search.trim().toLowerCase();
    const rows = !query
      ? clients
      : clients.filter((row) => {
          return (
            row.client_name.toLowerCase().includes(query) ||
            row.email.toLowerCase().includes(query) ||
            row.segment.toLowerCase().includes(query) ||
            row.risk_profile.toLowerCase().includes(query)
          );
        });

    const sorted = [...rows].sort((a, b) => {
      const left = sortValue(a, sortKey);
      const right = sortValue(b, sortKey);
      const result = left < right ? -1 : left > right ? 1 : 0;
      return sortDirection === "asc" ? result : -result;
    });

    const start = (currentPage - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    const paged = sorted.slice(start, end);

    return { all: sorted, paged, total: sorted.length };
  }, [clients, search, sortKey, sortDirection, currentPage]);

  function toggleSort(key: SortKey) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDirection("desc");
      return;
    }
    setSortDirection((prev) => (prev === "desc" ? "asc" : "desc"));
  }

  async function handleClientClick(clientId: number) {
    try {
      setLoadingAlert(true);
      // Find the first alert for this client in the queued cases
      const alertId = queuedCases.find(c => c.client_id === clientId)?.alert_id;
      if (!alertId) {
        // If no queued alert, just show a notification
        alert(`Client has no open alerts`);
        return;
      }
      const alertDetail = await fetchAlert(alertId);
      setSelectedAlert(alertDetail);
    } catch (err) {
      alert(`Failed to load client details: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingAlert(false);
    }
  }

  function getAccountTierBadgeColor(tier?: string) {
    if (!tier) return "bg-gray-100 text-gray-800";
    switch (tier.toLowerCase()) {
      case "core": return "bg-blue-100 text-blue-800";
      case "premium": return "bg-purple-100 text-purple-800";
      case "generation": return "bg-amber-100 text-amber-800";
      default: return "bg-gray-100 text-gray-800";
    }
  }

  return (
    <div className="space-y-4">
      <section className="card p-4 space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="page-title">Client monitoring explorer</div>
            <div className="page-subtitle">
              Search clients and sort by AUM, daily PNL, and queue pressure.
            </div>
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search client, email, segment, risk profile..."
            className="w-full md:w-96 rounded-lg border border-ws-border bg-white px-3 py-2 text-sm outline-none focus:border-emerald-400"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-ws-border text-left text-xs uppercase tracking-wide text-ws-muted">
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("client_name")}>Client</button>
                </th>
                <th className="px-2 py-2">Account</th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("client_since_year")}>Since</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("total_aum")}>AUM</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("daily_pnl")}>Daily PNL</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("daily_pnl_pct")}>Daily %</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("ytd_performance_pct")}>YTD %</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("open_alerts")}>Open alerts</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("queued_for_review")}>Queued review</button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleSort("last_alert_at")}>Last alert</button>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAndPagedClients.paged.map((row) => (
                <tr
                  key={row.client_id}
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => handleClientClick(row.client_id)}
                >
                  <td className="px-2 py-2">
                    <div className="font-medium text-gray-900">{row.client_name}</div>
                    <div className="text-xs text-ws-muted">
                      {row.segment} | {row.risk_profile}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <span className={`inline-block rounded-full px-2 py-1 text-[10px] font-semibold ${getAccountTierBadgeColor(row.account_tier)}`}>
                      {row.account_tier || "-"}
                    </span>
                  </td>
                  <td className="px-2 py-2">{row.client_since_year}</td>
                  <td className="px-2 py-2 text-gray-900">{formatCurrency(row.total_aum)}</td>
                  <td className={`px-2 py-2 ${row.daily_pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {row.daily_pnl >= 0 ? "+" : ""}
                    {formatCurrency(row.daily_pnl)}
                  </td>
                  <td className={`px-2 py-2 ${row.daily_pnl_pct >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {formatPct(row.daily_pnl_pct)}
                  </td>
                  <td className={`px-2 py-2 ${row.ytd_performance_pct >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                    {formatPct(row.ytd_performance_pct)}
                  </td>
                  <td className="px-2 py-2">{row.open_alerts}</td>
                  <td className="px-2 py-2">{row.queued_for_review}</td>
                  <td className="px-2 py-2 text-xs text-ws-muted">
                    <div>{formatDate(row.last_alert_at)}</div>
                    <div className="max-w-56 truncate">{row.last_alert_event || "-"}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-xs text-ws-muted">
          <div>
            Showing {(currentPage - 1) * PAGE_SIZE + 1}-{Math.min(currentPage * PAGE_SIZE, filteredAndPagedClients.total)} of {filteredAndPagedClients.total} clients
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded border border-ws-border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <div className="px-3 py-1">Page {currentPage}</div>
            <button
              type="button"
              onClick={() => setCurrentPage(prev => prev + 1)}
              disabled={currentPage * PAGE_SIZE >= filteredAndPagedClients.total}
              className="px-3 py-1 rounded border border-ws-border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <section className="card p-4 space-y-3">
        <div className="page-title">Queued cases to review</div>
        <div className="page-subtitle">
          Prioritized open and escalated alerts needing review attention.
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-ws-border text-left text-xs uppercase tracking-wide text-ws-muted">
                <th className="px-2 py-2">Priority</th>
                <th className="px-2 py-2">Client</th>
                <th className="px-2 py-2">Portfolio</th>
                <th className="px-2 py-2">Case</th>
                <th className="px-2 py-2">Status</th>
                <th className="px-2 py-2">Confidence</th>
                <th className="px-2 py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {queuedCases.map((item) => (
                <tr key={item.alert_id} className="border-b border-gray-100">
                  <td className="px-2 py-2 font-medium">
                    <span
                      className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                        item.priority === "HIGH"
                          ? "border-red-300 bg-red-50 text-red-700"
                          : item.priority === "MEDIUM"
                            ? "border-amber-300 bg-amber-50 text-amber-700"
                            : "border-emerald-300 bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      {item.priority}
                    </span>
                  </td>
                  <td className="px-2 py-2">{item.client_name}</td>
                  <td className="px-2 py-2">{item.portfolio_name}</td>
                  <td className="px-2 py-2">{item.event_title}</td>
                  <td className="px-2 py-2">
                    <span
                      className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                        item.status === "OPEN"
                          ? "border-red-300 bg-red-50 text-red-700"
                          : item.status === "ESCALATED"
                            ? "border-orange-300 bg-orange-50 text-orange-700"
                            : item.status === "REVIEWED"
                              ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                              : "border-slate-300 bg-slate-50 text-slate-700"
                      }`}
                    >
                      {item.status}
                    </span>
                    {item.human_review_required ? " | Human" : ""}
                  </td>
                  <td className="px-2 py-2">{item.confidence}%</td>
                  <td className="px-2 py-2 text-xs text-ws-muted">{formatDate(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedAlert && (
        <div className="fixed inset-0 z-40 flex justify-center bg-black/50 backdrop-blur-sm overflow-y-auto px-4 py-10">
          <div className="relative w-full max-w-5xl rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-ws-border px-5 py-3 md:px-6 md:py-4">
              <div className="space-y-0.5">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Client details
                </div>
                <div className="text-sm font-medium text-gray-900">
                  {selectedAlert.client.name}
                </div>
              </div>
              <button
                type="button"
                className="rounded-full border border-ws-border bg-white px-4 py-1.5 text-xs font-medium text-ws-muted shadow-sm hover:bg-gray-50"
                onClick={() => setSelectedAlert(null)}
              >
                Close
              </button>
            </div>
            <div className="p-5 md:p-6">
              {selectedAlert && <ClientDetailsPanel alert={selectedAlert} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


