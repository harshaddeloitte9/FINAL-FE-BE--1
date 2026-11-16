import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useModelIdentity } from "@/hooks/use-model-identity";
import {
  cachedResultUsable,
  datasetFingerprint,
  evaluationKey,
  evaluationReducer,
  initialEvaluationState,
  type EvaluationAction,
  type EvaluationState,
} from "@/lib/evaluation-evidence";

// The identity a stress / bias / benchmark result belongs to: the registered
// model, its current training run and the exact dataset bytes being sent.
// null while any part is still being determined (nothing is shown meanwhile).
export function useEvaluationKey(dataset: Blob | null, registeredModelId: string | null, extra?: string | null): string | null {
  const [datasetKey, setDatasetKey] = useState<{ source: Blob; key: string } | null>(null);
  useEffect(() => {
    if (!dataset) {
      setDatasetKey(null);
      return;
    }
    let active = true;
    void datasetFingerprint(dataset)
      .then((key) => {
        if (active) setDatasetKey({ source: dataset, key });
      })
      .catch(() => {
        if (active) setDatasetKey(null);
      });
    return () => {
      active = false;
    };
  }, [dataset]);

  const identity = useModelIdentity(registeredModelId);
  if (!dataset || !datasetKey || datasetKey.source !== dataset) return null;
  if (registeredModelId && identity.kind === "loading") return null;
  const trainingRunId =
    identity.kind === "ready" || identity.kind === "incomplete" ? identity.readiness.contract?.training_run_id ?? null : null;
  return evaluationKey({ registeredModelId, datasetKey: datasetKey.key, trainingRunId, extra });
}

// Loading / success / error state for one page's result, scoped to `key`.
// Each request gets a token; only the latest request's response is applied.
export function useEvaluationState<R>(key: string | null, cached: (R & { evaluation_key?: string | null }) | null) {
  const [state, dispatch] = useReducer(
    evaluationReducer as (s: EvaluationState<R>, a: EvaluationAction<R>) => EvaluationState<R>,
    undefined,
    () => initialEvaluationState<R>(),
  );
  const tokenRef = useRef(0);
  const cachedRef = useRef(cached);
  cachedRef.current = cached;

  // Identity changed (other dataset, model or training): drop what was shown
  // and invalidate in-flight requests; restore only an exact-key cache entry.
  useEffect(() => {
    tokenRef.current += 1;
    dispatch({ type: "reset", key, token: tokenRef.current, cached: cachedResultUsable(cachedRef.current, key) ? (cachedRef.current as R) : null });
  }, [key]);

  const begin = useCallback(() => {
    tokenRef.current += 1;
    dispatch({ type: "start", token: tokenRef.current });
    return tokenRef.current;
  }, []);
  const succeed = useCallback((token: number, result: R) => dispatch({ type: "success", token, result }), []);
  const fail = useCallback((token: number, error: string) => dispatch({ type: "failure", token, error }), []);
  const isCurrent = useCallback((token: number) => token === tokenRef.current, []);

  return { state, begin, succeed, fail, isCurrent };
}
