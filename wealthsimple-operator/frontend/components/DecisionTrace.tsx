import { useState } from "react";
import type { DecisionTraceStep } from "../lib/types";
import { Button } from "./Buttons";

export default function DecisionTrace({
  steps
}: {
  steps: DecisionTraceStep[];
}) {
  const [open, setOpen] = useState(false);

  if (!steps.length) return null;

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="page-title">Decision trace</div>
          <div className="page-subtitle">
            Step-by-step breakdown of how the AI arrived at this triage decision.
          </div>
        </div>
        <Button
          variant="ghost"
          type="button"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide steps" : "Show steps"}
        </Button>
      </div>
      {open && (
        <ol className="mt-2 space-y-2 text-sm text-gray-800 list-decimal list-inside">
          {steps.map((step, idx) => (
            <li key={`${idx}-${step.step}`} className="space-y-0.5">
              <div className="font-medium">{step.step}</div>
              <div className="text-ws-muted text-xs">{step.detail}</div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

