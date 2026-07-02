import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/pd")({
  beforeLoad: () => {
    throw redirect({ to: "/data-upload" });
  },
});
