import { useRouterState } from "@tanstack/react-router";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PageTransition({
  children,
  className,
  intent = "page",
}: {
  children: ReactNode;
  className?: string;
  intent?: "page" | "login";
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div
      key={pathname}
      className={cn(
        "page-transition-shell",
        intent === "login" && "page-transition-shell--login",
        className,
      )}
    >
      {children}
    </div>
  );
}
