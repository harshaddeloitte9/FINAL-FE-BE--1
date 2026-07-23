import { createFileRoute, redirect } from "@tanstack/react-router";

// Model Training was merged into Model Training & Evaluation as its first
// sub-tab (see model-training-evaluation.tsx) — this route now just
// redirects old links/bookmarks there instead of 404ing.
export const Route = createFileRoute("/training")({
  beforeLoad: () => {
    throw redirect({ to: "/model-training-evaluation", search: { tab: "training" } });
  },
});
