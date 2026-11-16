export function formatMddMetricValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not reported";
  return String(value);
}
