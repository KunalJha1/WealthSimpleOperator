"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import RiskBrief from "../../../components/RiskBrief";
import {
  ConfidencePill,
  PriorityPill,
  StatusPill
} from "../../../components/StatusPills";
import { fetchAlert, postAlertAction } from "../../../lib/api";
import type { AlertDetail } from "../../../lib/types";

export default function AlertDetailPage() {
  const router = useRouter();
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
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="mb-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium transition"
        >
          <ArrowLeft size={16} />
          Back to Operator
        </button>
      </div>

      {error && (
        <div className="card border-red-200 bg-red-50 text-red-800 p-3 text-sm">
          {error}
        </div>
      )}

      <RiskBrief alert={alert} onAction={handleAction} updating={updating} />
    </div>
  );
}

