import type { AlertStatus, Priority } from "./types";

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function priorityLabel(priority: Priority): string {
  return priority === "HIGH"
    ? "High"
    : priority === "MEDIUM"
      ? "Medium"
      : "Low";
}

export function priorityColorClasses(priority: Priority): string {
  switch (priority) {
    case "HIGH":
      return "bg-red-900 text-white border-red-700 shadow-[0_0_0_1px_rgba(248,113,113,0.6)]";
    case "MEDIUM":
      return "bg-amber-50 text-amber-900 border-amber-300";
    case "LOW":
    default:
      return "bg-emerald-50 text-emerald-900 border-emerald-300";
  }
}

export function statusLabel(status: AlertStatus): string {
  switch (status) {
    case "OPEN":
      return "Open";
    case "REVIEWED":
      return "Reviewed";
    case "ESCALATED":
      return "Escalated";
    case "FALSE_POSITIVE":
      return "False positive";
    default:
      return status;
  }
}

export function statusColorClasses(status: AlertStatus): string {
  switch (status) {
    case "OPEN":
      return "bg-gray-900 text-white border-gray-900";
    case "REVIEWED":
      return "bg-gray-100 text-gray-800 border-gray-300";
    case "ESCALATED":
      return "bg-white text-gray-900 border-gray-900";
    case "FALSE_POSITIVE":
      return "bg-white text-gray-600 border-gray-300";
    default:
      return "bg-gray-100 text-gray-800 border-gray-300";
  }
}

export function confidenceLabel(confidence: number): string {
  return `${confidence.toFixed(0)}%`;
}

