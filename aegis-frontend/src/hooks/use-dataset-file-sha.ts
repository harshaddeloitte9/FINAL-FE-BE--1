import { useEffect, useState } from "react";
import { datasetFingerprint } from "@/lib/evaluation-evidence";

/**
 * SHA-256 of the dataset bytes a page sends to the backend, i.e. the
 * `dataset_file_sha256` the backend records with every development run.
 * null while it is being computed or when there is no dataset.
 */
export function useDatasetFileSha(dataset: Blob | null | undefined): string | null {
  const [state, setState] = useState<{ source: Blob; sha: string } | null>(null);
  useEffect(() => {
    if (!dataset) {
      setState(null);
      return;
    }
    let active = true;
    void datasetFingerprint(dataset)
      .then((sha) => {
        if (active) setState({ source: dataset, sha });
      })
      .catch(() => {
        if (active) setState(null);
      });
    return () => {
      active = false;
    };
  }, [dataset]);
  return dataset && state && state.source === dataset ? state.sha : null;
}
