import { createFileRoute, redirect, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/validation")({
  component: () => <Outlet />,
  beforeLoad: ({ location }) => {
    if (location.pathname === "/validation" || location.pathname === "/validation/") {
      throw redirect({ to: "/validation/intake" });
    }
  },
});
