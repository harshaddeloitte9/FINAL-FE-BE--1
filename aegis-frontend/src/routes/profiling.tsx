import { createFileRoute, redirect } from "@tanstack/react-router";

// Data Profiling was merged into Data Preparation & Feature Engineering as
// its first sub-tab (see data-preparation.tsx) — this route now just
// redirects old links/bookmarks there instead of 404ing.
export const Route = createFileRoute("/profiling")({
  beforeLoad: () => {
    throw redirect({ to: "/data-preparation", search: { tab: "profiling" } });
  },
});
