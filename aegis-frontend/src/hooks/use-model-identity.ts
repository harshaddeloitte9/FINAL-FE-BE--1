import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { identityFromLineage, type LineageReadiness, type ModelIdentity } from "@/lib/model-identity";

// Looks up the registration and lineage of the selected registered model via
// the read-only GET /model-inventory/development/{id}/lineage endpoint.
// Re-checks whenever the selected ID changes; an older response can never be
// applied to a newer selection.
export function useModelIdentity(modelId: string | null): ModelIdentity {
  const [state, setState] = useState<{ id: string | null; readiness: LineageReadiness | null; status: number | null; loading: boolean }>({
    id: null,
    readiness: null,
    status: null,
    loading: false,
  });

  useEffect(() => {
    if (!modelId) {
      setState({ id: null, readiness: null, status: null, loading: false });
      return;
    }
    let active = true;
    setState({ id: modelId, readiness: null, status: null, loading: true });
    api<LineageReadiness>(`/model-inventory/development/${encodeURIComponent(modelId)}/lineage`)
      .then((readiness) => {
        if (active) setState({ id: modelId, readiness, status: null, loading: false });
      })
      .catch((err) => {
        if (active) setState({ id: modelId, readiness: null, status: err instanceof ApiError ? err.status : 0, loading: false });
      });
    return () => {
      active = false;
    };
  }, [modelId]);

  const current = state.id === modelId;
  return identityFromLineage(modelId, current ? state.readiness : null, current ? state.status : null, !current || state.loading);
}
