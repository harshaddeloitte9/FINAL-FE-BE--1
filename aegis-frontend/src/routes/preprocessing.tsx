import { createFileRoute, redirect } from "@tanstack/react-router";

// Preprocessing was merged into Data Preparation & Feature Engineering's
// second sub-tab (see data-preparation.tsx) — this route now just
// redirects old links/bookmarks there instead of 404ing.
export const Route = createFileRoute("/preprocessing")({
  beforeLoad: () => {
    throw redirect({ to: "/data-preparation", search: { tab: "preprocessing" } });
  },
});
