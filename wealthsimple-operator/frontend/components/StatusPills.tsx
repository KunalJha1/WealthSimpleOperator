import Badge from "./Badge";
import { confidenceLabel, priorityColorClasses, priorityLabel, statusColorClasses, statusLabel } from "../lib/utils";
import type { AlertStatus, Priority } from "../lib/types";

export function PriorityPill({ priority }: { priority: Priority }) {
  return (
    <Badge className={priorityColorClasses(priority)}>
      {priorityLabel(priority)}
    </Badge>
  );
}

export function StatusPill({ status }: { status: AlertStatus }) {
  return (
    <Badge className={statusColorClasses(status)}>{statusLabel(status)}</Badge>
  );
}

export function ConfidencePill({ confidence }: { confidence: number }) {
  return (
    <Badge className="bg-gray-50 text-gray-700 border-gray-200">
      Confidence {confidenceLabel(confidence)}
    </Badge>
  );
}

