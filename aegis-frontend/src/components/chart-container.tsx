import { ResponsiveContainer } from "recharts";
import { useEffect, useState, type ComponentProps } from "react";

/**
 * Client-only wrapper around Recharts ResponsiveContainer.
 * Recharts 2.x + React 19 SSR can leave the container un-measured after
 * hydration, leaving charts blank. Deferring render until after mount
 * forces a clean client-side measurement.
 */
export function ChartContainer(props: ComponentProps<typeof ResponsiveContainer>) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  if (!mounted) return null;
  return <ResponsiveContainer {...props} />;
}
