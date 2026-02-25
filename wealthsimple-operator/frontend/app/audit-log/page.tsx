import AuditTable from "../../components/AuditTable";
import { fetchAuditLog } from "../../lib/api";

export default async function AuditLogPage() {
  let audit = null;
  let error: string | null = null;

  try {
    audit = await fetchAuditLog();
  } catch (e) {
    error = (e as Error).message;
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="page-title">Audit log</h1>
        <p className="page-subtitle">
          End-to-end trail of operator runs, alert creation, and human actions.
        </p>
      </header>

      {audit ? (
        <AuditTable items={audit.items} />
      ) : (
        <div className="card border-orange-200 bg-orange-50 p-4 text-sm text-orange-900">
          Unable to load audit events. Start the backend and refresh.
          {error ? <div className="mt-2 text-xs text-orange-800">{error}</div> : null}
        </div>
      )}
    </div>
  );
}

