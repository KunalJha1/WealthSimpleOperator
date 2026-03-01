"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { AuditEventEntry } from "../lib/types";
import { formatDateTime } from "../lib/utils";

interface AuditTableProps {
  items: AuditEventEntry[];
}

export default function AuditTable({ items }: AuditTableProps) {
  const [query, setQuery] = useState("");
  const [eventFilter, setEventFilter] = useState("ALL");

  const eventOptions = useMemo(() => {
    const unique = Array.from(new Set(items.map((item) => item.event_type)));
    return unique.sort();
  }, [items]);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      if (eventFilter !== "ALL" && item.event_type !== eventFilter) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }

      const detailsText = Object.entries(item.details)
        .map(([k, v]) => `${k} ${formatDetailValue(v)}`)
        .join(" ")
        .toLowerCase();

      return (
        item.event_type.toLowerCase().includes(normalizedQuery) ||
        item.actor.toLowerCase().includes(normalizedQuery) ||
        String(item.alert_id ?? "").includes(normalizedQuery) ||
        String(item.run_id ?? "").includes(normalizedQuery) ||
        detailsText.includes(normalizedQuery)
      );
    });
  }, [items, eventFilter, query]);

  if (!items.length) {
    return <div className="card p-4 text-sm text-ws-muted">No audit events recorded yet.</div>;
  }

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-ws-border bg-gray-50/80 p-3 md:flex-row md:items-center md:justify-between">
        <div className="text-xs text-ws-muted">
          Showing <span className="font-semibold text-gray-900">{filteredItems.length}</span> of{" "}
          <span className="font-semibold text-gray-900">{items.length}</span> events
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actor, run, details..."
            className="rounded-lg border border-ws-border bg-white px-3 py-2 text-xs text-gray-900 outline-none transition focus:border-gray-300 focus:ring-1 focus:ring-gray-200"
          />
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="rounded-lg border border-ws-border bg-white px-2.5 py-2 text-xs text-gray-900 outline-none transition focus:border-gray-300 focus:ring-1 focus:ring-gray-200"
          >
            <option value="ALL">All event types</option>
            {eventOptions.map((eventType) => (
              <option key={eventType} value={eventType}>
                {toLabel(eventType)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Event</th>
              <th className="px-3 py-2">Alert</th>
              <th className="px-3 py-2">Run</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ws-border">
            {filteredItems.map((event) => (
              <tr key={event.id} className="align-top transition-colors hover:bg-gray-50/70">
                <td className="px-3 py-2 text-xs text-ws-muted">{formatDateTime(event.created_at)}</td>
                <td className="px-3 py-2 text-sm text-gray-900">
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${eventBadgeClass(event.event_type)}`}
                  >
                    {toLabel(event.event_type)}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-ws-muted">
                  {event.alert_id ? (
                    <Link href={`/alerts/${event.alert_id}`} className="text-blue-600 hover:text-blue-700 font-medium transition">
                      {event.alert_id}
                    </Link>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-ws-muted">{event.run_id ?? "-"}</td>
                <td className="px-3 py-2 text-xs text-ws-muted">
                  <span className="font-medium text-gray-700">{event.actor}</span>
                </td>
                <td className="px-3 py-2 text-xs text-ws-muted">
                  {Object.entries(event.details)
                    .map(([k, v]) => `${toLabel(k)}: ${formatDetailValue(v)}`)
                    .join(" | ") || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function toLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function eventBadgeClass(eventType: string): string {
  if (eventType.includes("ESCALATED") || eventType.includes("REJECTED")) {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (eventType.includes("APPROVED") || eventType.includes("REVIEWED")) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (eventType.includes("RUN_COMPLETED") || eventType.includes("GENERATED")) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }
  return "border-gray-200 bg-gray-50 text-gray-700";
}
