import { createFileRoute, redirect } from "@tanstack/react-router";

// Feature Engineering was merged into Data Preparation & Feature
// Engineering's second sub-tab, alongside Preprocessing (see
// data-preparation.tsx) — this route now just redirects old links/bookmarks
// there instead of 404ing.
export const Route = createFileRoute("/features")({
  beforeLoad: () => {
    throw redirect({ to: "/data-preparation", search: { tab: "preprocessing" } });
  },
});
