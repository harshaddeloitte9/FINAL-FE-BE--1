import { createFileRoute, redirect } from "@tanstack/react-router";

// Conceptual Soundness was merged into the Data Validation page as a second
// sub-tab (see validation.data-quality.tsx) — this route now just redirects
// old links/bookmarks there instead of 404ing.
export const Route = createFileRoute("/validation/conceptual")({
  beforeLoad: () => {
    throw redirect({ to: "/validation/data-quality" });
  },
});
