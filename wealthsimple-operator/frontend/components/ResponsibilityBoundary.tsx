export default function ResponsibilityBoundary() {
  return (
    <div className="card p-4 space-y-1">
      <div className="text-xs font-semibold text-ws-muted uppercase tracking-wide">
        Responsibility boundary
      </div>
      <div className="text-sm text-gray-900">
        <span className="font-medium">AI responsibility: </span>
        monitoring and triage only — detecting signals, ranking attention, and
        explaining why review is needed.
      </div>
      <div className="text-sm text-gray-900">
        <span className="font-medium">Human responsibility: </span>
        all investment decisions, client communication, escalation, and
        interpretation of these signals. This tool must not be treated as
        financial advice or a trading instruction engine.
      </div>
    </div>
  );
}

