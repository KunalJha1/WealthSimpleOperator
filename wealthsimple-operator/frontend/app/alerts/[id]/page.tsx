"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import RiskBrief from "../../../components/RiskBrief";
import {
  ConfidencePill,
  PriorityPill,
  StatusPill
} from "../../../components/StatusPills";
import { fetchAlert, postAlertAction } from "../../../lib/api";
import type { AlertDetail } from "../../../lib/types";

export default function AlertDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchAlert(id);
        setAlert(data);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
    if (!Number.isNaN(id)) {
      void load();
    }
  }, [id]);

  async function handleAction(
    action: "reviewed" | "escalate" | "false_positive"
  ) {
    if (!alert) return;
    setUpdating(true);
    setError(null);
    try {
      const res = await postAlertAction(alert.id, action);
      setAlert(res.alert);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUpdating(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-ws-muted">Loading alert…</div>;
  }

  if (!alert) {
    return (
      <div className="text-sm text-red-700">
        Unable to load this alert. It may have been removed.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="page-title">{alert.event_title}</h1>
          <p className="page-subtitle max-w-2xl">{alert.summary}</p>
          <div className="mt-2 flex flex-wrap gap-2 items-center">
            <PriorityPill priority={alert.priority} />
            <StatusPill status={alert.status} />
            <ConfidencePill confidence={alert.confidence} />
          </div>
        </div>
        <div className="space-y-2">
          <div className="text-xs text-ws-muted">
            Actions are advisory tooling only. Advisors remain fully
            responsible for all investment decisions and client contact.
          </div>
        </div>
      </header>

      {error && (
        <div className="card border-red-200 bg-red-50 text-red-800 p-3 text-sm">
          {error}
        </div>
      )}

      <RiskBrief alert={alert} onAction={handleAction} updating={updating} />
    </div>
  );
}

