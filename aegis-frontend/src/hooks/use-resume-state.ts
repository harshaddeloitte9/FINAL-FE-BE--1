import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface ExcludedRun {
  run_id: string;
  timestamp: string;
  reason: string;
}

interface LatestRunResponse<T> {
  latest: {
    run_id: string;
    timestamp: string;
    summary: unknown;
    full_payload: T | null;
    record_status?: "current" | "legacy";
    record_status_reason?: string | null;
  } | null;
  // Newer runs of this stage that were passed over (legacy format, another
  // model/dataset, model retrained since, …) and why. Nothing is deleted.
  excluded?: ExcludedRun[];
  excluded_counts?: Record<string, number>;
}

export interface ResumeMeta {
  runId: string;
  timestamp: string;
  summary: unknown;
  recordStatus?: "current" | "legacy";
}

interface UseResumeStateOptions {
  /**
   * Extra query params sent to /history/latest (e.g. `{ business_model_name }`)
   * to scope which "most recent" row is eligible to resume, beyond just the
   * log file + stage. Omit for the original unscoped lookup.
   */
  params?: Record<string, string>;
  /**
   * When false, no fetch is made at all and `data` stays null. Use this when
   * the identifier needed to scope the resume safely (e.g. the current
   * model's name) isn't known yet — resuming an unscoped "latest of
   * everyone's runs" in that situation would risk showing the wrong result,
   * which is worse than just showing the empty state. Defaults to true,
   * preserving prior behavior for every caller that doesn't pass this.
   */
  enabled?: boolean;
}

/**
 * Fetches the most recently saved run for a given pipeline stage so a page
 * can resume where the user left off instead of starting blank.
 *
 * Fails silently: any network/parsing error just leaves `data` as null, so
 * callers fall back to their normal empty/initial state exactly as before.
 */
export function useResumeState<T = unknown>(logFile: string, stage: string, options?: UseResumeStateOptions) {
  const { params, enabled = true } = options ?? {};
  const [data, setData] = useState<T | null>(null);
  const [meta, setMeta] = useState<ResumeMeta | null>(null);
  const [excluded, setExcluded] = useState<{ runs: ExcludedRun[]; counts: Record<string, number> }>({ runs: [], counts: {} });
  const [loading, setLoading] = useState(true);
  // Stable key so an inline `{ business_model_name }` object literal at the
  // call site doesn't retrigger the effect every render.
  const paramsKey = params ? JSON.stringify(params) : "";
  // The query whose lookup has finished (found or not). `settled` is true
  // only when that is the CURRENT query, so a caller never mistakes the gap
  // before a new lookup starts for "nothing was found".
  const queryKey = `${logFile}|${stage}|${enabled}|${paramsKey}`;
  const [settledKey, setSettledKey] = useState<string | null>(null);

  // Fetches once per scope (log file + stage + identity params). When the
  // scope changes — e.g. a different registered model or replication run —
  // the previous scope's result is cleared first so it can never be shown
  // under the new identity. Cancellation (not a "fetched once" flag) guards
  // against stale responses, which also keeps React StrictMode's dev double
  // invoke from cancelling the only request.
  useEffect(() => {
    setData(null);
    setMeta(null);
    setExcluded({ runs: [], counts: {} });
    if (!enabled) {
      setLoading(false);
      setSettledKey(queryKey);
      return;
    }
    setLoading(true);

    let cancelled = false;

    (async () => {
      try {
        const query = new URLSearchParams({ log_file: logFile, stage, ...(params ?? {}) });
        const res = await api<LatestRunResponse<T>>(`/history/latest?${query.toString()}`);
        if (cancelled) return;
        setExcluded({ runs: res?.excluded ?? [], counts: res?.excluded_counts ?? {} });
        if (res?.latest?.full_payload) {
          setData(res.latest.full_payload);
          setMeta({
            runId: res.latest.run_id,
            timestamp: res.latest.timestamp,
            summary: res.latest.summary,
            recordStatus: res.latest.record_status,
          });
        }
      } catch {
        // Silent — resume is a convenience, never blocks the page.
      } finally {
        if (!cancelled) {
          setLoading(false);
          setSettledKey(queryKey);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logFile, stage, enabled, paramsKey]);

  return { data, loading, meta, excluded, settled: settledKey === queryKey };
}
