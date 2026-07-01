import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/development")({
  beforeLoad: () => {
    throw redirect({ to: "/data-upload" });
  },
});
