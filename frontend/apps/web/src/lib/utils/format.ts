import { formatDistanceToNow, format, parseISO } from "date-fns";

export function relativeTime(dateStr: string): string {
  return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
}

export function shortDate(dateStr: string): string {
  return format(parseISO(dateStr), "MMM d, yyyy");
}

export function shortDateTime(dateStr: string): string {
  return format(parseISO(dateStr), "MMM d, yyyy · h:mm a");
}

export function initials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

export function confidenceLabel(score: number): "high" | "medium" | "low" {
  if (score >= 0.75) return "high";
  if (score >= 0.45) return "medium";
  return "low";
}

export function confidenceColor(score: number): string {
  if (score >= 0.75) return "text-emerald-400";
  if (score >= 0.45) return "text-amber-400";
  return "text-red-400";
}

export function scoreColor(score: number): string {
  if (score >= 75) return "#4ade80";
  if (score >= 50) return "#fbbf24";
  return "#f87171";
}

export function formatSalary(min?: number, max?: number, currency = "USD"): string {
  if (!min && !max) return "Competitive";
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 0,
    }).format(n);
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max!)}`;
}

export const stageLabelMap: Record<string, string> = {
  applied:       "Applied",
  sourced:       "Sourced",
  screening:     "Screening",
  assessment:    "Assessment",
  hr_interview:  "HR Interview",
  tech_interview:"Tech Interview",
  decision:      "Decision",
  hired:         "Hired",
  rejected:      "Rejected",
  withdrawn:     "Withdrawn",
};

export function stageLabel(stage: string): string {
  return stageLabelMap[stage] ?? stage;
}
