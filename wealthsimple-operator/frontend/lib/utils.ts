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
      return "bg-red-50 text-red-800 border-red-300";
    case "MEDIUM":
      return "bg-amber-50 text-amber-800 border-amber-300";
    case "LOW":
    default:
      return "bg-emerald-50 text-emerald-800 border-emerald-300";
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
      return "bg-red-50 text-red-800 border-red-300";
    case "REVIEWED":
      return "bg-emerald-50 text-emerald-800 border-emerald-300";
    case "ESCALATED":
      return "bg-orange-50 text-orange-800 border-orange-300";
    case "FALSE_POSITIVE":
      return "bg-slate-50 text-slate-700 border-slate-300";
    default:
      return "bg-gray-100 text-gray-800 border-gray-300";
  }
}

export function confidenceLabel(confidence: number): string {
  return `${confidence.toFixed(0)}%`;
}

export function formatCurrency(value: number, currency: string = "CAD"): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(value);
}

