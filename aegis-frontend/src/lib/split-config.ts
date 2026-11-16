// The train/validation/test split settings every data-preparation preview
// must use (audit finding E12): the split locked in at Preprocessing (or the
// one a trained model actually used), never fixed values.

export type SplitConfig = { test_size: number; val_size: number; random_seed: number };

export const DEFAULT_SPLIT: SplitConfig = { test_size: 0.15, val_size: 0.15, random_seed: 42 };

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** First source with a complete split configuration, else the backend defaults. */
export function resolveSplitConfig(...sources: (Record<string, any> | null | undefined)[]): SplitConfig {
  for (const s of sources) {
    const t = num(s?.test_size), v = num(s?.val_size), r = num(s?.random_seed);
    if (t !== null && v !== null && r !== null) return { test_size: t, val_size: v, random_seed: r };
  }
  return { ...DEFAULT_SPLIT };
}

export function appendSplitConfig(form: FormData, cfg: SplitConfig): FormData {
  form.append("test_size", String(cfg.test_size));
  form.append("val_size", String(cfg.val_size));
  form.append("random_seed", String(cfg.random_seed));
  return form;
}

/** Whether a saved preview was produced with the same split settings. */
export function sameSplit(recorded: Record<string, any> | null | undefined, cfg: SplitConfig): boolean {
  return Boolean(recorded) && recorded!.test_size === cfg.test_size && recorded!.val_size === cfg.val_size
    && recorded!.random_seed === cfg.random_seed;
}
