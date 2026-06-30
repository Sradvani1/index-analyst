/** Display-only string formatting — no analytical meaning. */

import type { RunSummary } from "@/lib/types";

/** Card blurb — first paragraph of Today's Posture from the report markdown. */
export function runCardSummary(run: RunSummary & { narrative_summary?: string; trend_regime?: string }): string {
  return run.posture_lead || run.narrative_summary || run.trend_regime || "";
}

export function humanizeAction(action: string): string {
  return action.replaceAll("_", " ");
}

export function formatDateLong(date: string): string {
  const parsed = new Date(`${date}T12:00:00`);
  return parsed.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatClose(value: number): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
