import { createFileRoute, redirect } from "@tanstack/react-router";

// Model Evaluation was merged into Model Training & Evaluation as its
// second sub-tab (see model-training-evaluation.tsx) — this route now just
// redirects old links/bookmarks there instead of 404ing.
export const Route = createFileRoute("/evaluation")({
  beforeLoad: () => {
    throw redirect({ to: "/model-training-evaluation", search: { tab: "evaluation" } });
  },
});
