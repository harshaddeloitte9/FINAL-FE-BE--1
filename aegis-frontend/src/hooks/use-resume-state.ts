import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

interface LatestRunResponse<T> {
  latest: {
    run_id: string;
    timestamp: string;
    summary: unknown;
    full_payload: T | null;
  } | null;
}

export interface ResumeMeta {
  runId: string;
  timestamp: string;
  summary: unknown;
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
  const [loading, setLoading] = useState(true);
  const fetchedRef = useRef(false);
  // Stable key so an inline `{ business_model_name }` object literal at the
  // call site doesn't retrigger the effect every render.
  const paramsKey = params ? JSON.stringify(params) : "";

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    let cancelled = false;

    (async () => {
      try {
        const query = new URLSearchParams({ log_file: logFile, stage, ...(params ?? {}) });
        const res = await api<LatestRunResponse<T>>(`/history/latest?${query.toString()}`);
        if (!cancelled && res?.latest?.full_payload) {
          setData(res.latest.full_payload);
          setMeta({ runId: res.latest.run_id, timestamp: res.latest.timestamp, summary: res.latest.summary });
        }
      } catch {
        // Silent — resume is a convenience, never blocks the page.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logFile, stage, enabled, paramsKey]);

  return { data, loading, meta };
}
