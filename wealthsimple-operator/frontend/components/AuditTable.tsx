import type { AuditEventEntry } from "../lib/types";
import { formatDateTime } from "../lib/utils";

interface AuditTableProps {
  items: AuditEventEntry[];
}

export default function AuditTable({ items }: AuditTableProps) {
  if (!items.length) {
    return (
      <div className="card p-4 text-sm text-ws-muted">
        No audit events recorded yet.
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-2">Time</th>
            <th className="px-3 py-2">Event</th>
            <th className="px-3 py-2">Alert</th>
            <th className="px-3 py-2">Run</th>
            <th className="px-3 py-2">Actor</th>
            <th className="px-3 py-2">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ws-border">
          {items.map((e) => (
            <tr key={e.id}>
              <td className="px-3 py-2 text-xs text-ws-muted">
                {formatDateTime(e.created_at)}
              </td>
              <td className="px-3 py-2 text-sm text-gray-900">{e.event_type}</td>
              <td className="px-3 py-2 text-xs text-ws-muted">
                {e.alert_id ?? "—"}
              </td>
              <td className="px-3 py-2 text-xs text-ws-muted">
                {e.run_id ?? "—"}
              </td>
              <td className="px-3 py-2 text-xs text-ws-muted">{e.actor}</td>
              <td className="px-3 py-2 text-xs text-ws-muted">
                {Object.entries(e.details)
                  .map(([k, v]) => `${k}: ${String(v)}`)
                  .join(" • ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

