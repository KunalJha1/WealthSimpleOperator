import type { ChangeDetectionItem } from "../lib/types";

export default function ChangeDetection({
  items
}: {
  items: ChangeDetectionItem[];
}) {
  if (!items.length) {
    return (
      <div className="card p-4 text-sm text-ws-muted">
        No prior run metrics available yet for change detection.
      </div>
    );
  }

  return (
    <div className="card p-4">
      <div className="page-title">Change detection</div>
      <div className="page-subtitle mb-3">
        How key risk metrics have moved since the last operator run.
      </div>
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-2">Metric</th>
            <th className="px-3 py-2">From</th>
            <th className="px-3 py-2">To</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ws-border">
          {items.map((item, idx) => (
            <tr key={`${idx}-${item.metric}`}>
              <td className="px-3 py-2 text-sm text-gray-900">
                {item.metric.replace("_", " ")}
              </td>
              <td className="px-3 py-2 text-sm text-ws-muted">
                {item.from}
              </td>
              <td className="px-3 py-2 text-sm text-gray-900">{item.to}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

