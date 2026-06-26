/** Display-only string formatting — no analytical meaning. */

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
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
