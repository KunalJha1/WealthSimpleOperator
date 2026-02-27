"use client";

import { useMemo, useState } from "react";
import { fetchAlert, postAlertAction } from "../lib/api";
import { AlertDetail, MonitoringClientRow, MonitoringQueuedCase } from "../lib/types";
import { ClientDetailsPanel } from "./RiskBrief";
import RiskBrief from "./RiskBrief";

type ClientsSortKey =
  | "client_name"
  | "client_since_year"
  | "total_aum"
  | "daily_pnl"
  | "daily_pnl_pct"
  | "ytd_performance_pct"
  | "open_alerts"
  | "queued_for_review"
  | "last_alert_at";

type QueuedSortKey =
  | "priority"
  | "client_name"
  | "portfolio_name"
  | "status"
  | "confidence"
  | "created_at";

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
  return parsed.toLocaleString("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true
  });
}

function sortClientValue(row: MonitoringClientRow, key: ClientsSortKey): string | number {
  if (key === "client_name") return row.client_name.toLowerCase();
  if (key === "last_alert_at") return row.last_alert_at ? new Date(row.last_alert_at).getTime() : 0;
  return row[key];
}

function sortQueuedValue(row: MonitoringQueuedCase, key: QueuedSortKey): string | number {
  if (key === "client_name") return row.client_name.toLowerCase();
  if (key === "portfolio_name") return row.portfolio_name.toLowerCase();
  if (key === "created_at") return new Date(row.created_at).getTime();
  if (key === "priority") {
    const priorityOrder: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
    return priorityOrder[row.priority] ?? 99;
  }
  if (key === "status") {
    const statusOrder: Record<string, number> = { OPEN: 0, ESCALATED: 1, REVIEWED: 2, FALSE_POSITIVE: 3 };
    return statusOrder[row.status] ?? 99;
  }
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
  const [clientsSortKey, setClientsSortKey] = useState<ClientsSortKey>("total_aum");
  const [clientsSortDirection, setClientsSortDirection] = useState<SortDirection>("desc");
  const [queuedSortKey, setQueuedSortKey] = useState<QueuedSortKey>("priority");
  const [queuedSortDirection, setQueuedSortDirection] = useState<SortDirection>("asc");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedAlert, setSelectedAlert] = useState<AlertDetail | null>(null);
  const [loadingAlert, setLoadingAlert] = useState(false);
  const [updatingAlert, setUpdatingAlert] = useState(false);
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
      const left = sortClientValue(a, clientsSortKey);
      const right = sortClientValue(b, clientsSortKey);
      const result = left < right ? -1 : left > right ? 1 : 0;
      return clientsSortDirection === "asc" ? result : -result;
    });

    const start = (currentPage - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    const paged = sorted.slice(start, end);

    return { all: sorted, paged, total: sorted.length };
  }, [clients, search, clientsSortKey, clientsSortDirection, currentPage]);

  const sortedQueuedCases = useMemo(() => {
    return [...queuedCases].sort((a, b) => {
      const left = sortQueuedValue(a, queuedSortKey);
      const right = sortQueuedValue(b, queuedSortKey);
      const result = left < right ? -1 : left > right ? 1 : 0;
      return queuedSortDirection === "asc" ? result : -result;
    });
  }, [queuedCases, queuedSortKey, queuedSortDirection]);

  function toggleClientsSort(key: ClientsSortKey) {
    if (clientsSortKey !== key) {
      setClientsSortKey(key);
      setClientsSortDirection("desc");
      return;
    }
    setClientsSortDirection((prev) => (prev === "desc" ? "asc" : "desc"));
  }

  function toggleQueuedSort(key: QueuedSortKey) {
    if (queuedSortKey !== key) {
      setQueuedSortKey(key);
      setQueuedSortDirection("asc");
      return;
    }
    setQueuedSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
  }

  async function handleClientClick(clientId: number) {
    try {
      setLoadingAlert(true);
      // Fetch client's most recent alert from the API
      const params = new URLSearchParams({ limit: "100" });
      const alertsResponse = await fetch(`http://localhost:8000/alerts?${params.toString()}`, { cache: "no-store" });

      let alertId: number | undefined;
      if (alertsResponse.ok) {
        const data = await alertsResponse.json();
        const clientAlert = data.items?.find((a: AlertDetail) => a.client.id === clientId);
        alertId = clientAlert?.id;
      }

      // Fallback to queued cases if not found in general alerts
      if (!alertId) {
        alertId = queuedCases.find(c => c.client_id === clientId)?.alert_id;
      }

      if (!alertId) {
        alert(`Client has no recent alerts to review`);
        return;
      }
      const alertDetail = await fetchAlert(alertId);
      setSelectedAlert(alertDetail);
    } catch (err) {
      alert(`Failed to load alert: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingAlert(false);
    }
  }

  async function handleQueuedCaseClick(alertId: number) {
    try {
      setLoadingAlert(true);
      const alertDetail = await fetchAlert(alertId);
      setSelectedAlert(alertDetail);
    } catch (err) {
      alert(`Failed to load alert: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingAlert(false);
    }
  }

  async function handleAlertAction(action: "reviewed" | "escalate" | "false_positive") {
    if (!selectedAlert) return;
    try {
      setUpdatingAlert(true);
      const result = await postAlertAction(selectedAlert.id, action);
      setSelectedAlert(result.alert);
      alert(`Alert ${action === "false_positive" ? "marked as false positive" : action === "escalate" ? "escalated" : "marked as reviewed"}`);
    } catch (err) {
      alert(`Failed to update alert: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setUpdatingAlert(false);
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

  function SortArrow({ active, direction }: { active: boolean; direction: SortDirection }) {
    if (!active) return <span className="ml-1 text-gray-300">↕</span>;
    return <span className="ml-1">{direction === "asc" ? "↑" : "↓"}</span>;
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
                  <button type="button" onClick={() => toggleClientsSort("client_name")} className="flex items-center">
                    Client <SortArrow active={clientsSortKey === "client_name"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">Account</th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("client_since_year")} className="flex items-center">
                    Since <SortArrow active={clientsSortKey === "client_since_year"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("total_aum")} className="flex items-center">
                    AUM <SortArrow active={clientsSortKey === "total_aum"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("daily_pnl")} className="flex items-center">
                    Daily PNL <SortArrow active={clientsSortKey === "daily_pnl"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("daily_pnl_pct")} className="flex items-center">
                    Daily % <SortArrow active={clientsSortKey === "daily_pnl_pct"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("ytd_performance_pct")} className="flex items-center">
                    YTD % <SortArrow active={clientsSortKey === "ytd_performance_pct"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("open_alerts")} className="flex items-center">
                    Open alerts <SortArrow active={clientsSortKey === "open_alerts"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("queued_for_review")} className="flex items-center">
                    Queued review <SortArrow active={clientsSortKey === "queued_for_review"} direction={clientsSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleClientsSort("last_alert_at")} className="flex items-center">
                    Last alert <SortArrow active={clientsSortKey === "last_alert_at"} direction={clientsSortDirection} />
                  </button>
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
          Prioritized open and escalated alerts needing review attention. Click any case to review the risk brief.
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-ws-border text-left text-xs uppercase tracking-wide text-ws-muted">
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("priority")} className="flex items-center">
                    Priority <SortArrow active={queuedSortKey === "priority"} direction={queuedSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("client_name")} className="flex items-center">
                    Client <SortArrow active={queuedSortKey === "client_name"} direction={queuedSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("portfolio_name")} className="flex items-center">
                    Portfolio <SortArrow active={queuedSortKey === "portfolio_name"} direction={queuedSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">Case</th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("status")} className="flex items-center">
                    Status <SortArrow active={queuedSortKey === "status"} direction={queuedSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("confidence")} className="flex items-center">
                    Confidence <SortArrow active={queuedSortKey === "confidence"} direction={queuedSortDirection} />
                  </button>
                </th>
                <th className="px-2 py-2">
                  <button type="button" onClick={() => toggleQueuedSort("created_at")} className="flex items-center">
                    Created <SortArrow active={queuedSortKey === "created_at"} direction={queuedSortDirection} />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedQueuedCases.map((item) => (
                <tr key={item.alert_id} className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => handleQueuedCaseClick(item.alert_id)}>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-6xl max-h-[90vh] rounded-2xl bg-white shadow-2xl flex flex-col overflow-hidden">
            <div className="flex items-center justify-between border-b border-ws-border px-5 py-3 md:px-6 md:py-4 shrink-0">
              <div className="space-y-0.5">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ws-muted">
                  Alert review
                </div>
                <div className="text-sm font-medium text-gray-900">
                  {selectedAlert.client.name}
                </div>
              </div>
              <button
                type="button"
                className="rounded-full border border-ws-border bg-white px-4 py-1.5 text-xs font-medium text-ws-muted shadow-sm hover:bg-gray-50 shrink-0"
                onClick={() => setSelectedAlert(null)}
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              <div className="p-5 md:p-6">
                <RiskBrief alert={selectedAlert} onAction={handleAlertAction} updating={updatingAlert} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


