import { useEffect, useState } from "react";
import { jsx } from "react/jsx-runtime";
import { ResponsiveContainer } from "recharts";
//#region src/components/chart-container.tsx
/**
* Client-only wrapper around Recharts ResponsiveContainer.
* Recharts 2.x + React 19 SSR can leave the container un-measured after
* hydration, leaving charts blank. Deferring render until after mount
* forces a clean client-side measurement.
*/
function ChartContainer(props) {
	const [mounted, setMounted] = useState(false);
	useEffect(() => {
		setMounted(true);
	}, []);
	if (!mounted) return null;
	return /* @__PURE__ */ jsx(ResponsiveContainer, { ...props });
}
//#endregion
export { ChartContainer as t };
