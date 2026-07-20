import React, { useEffect, useRef } from "react";
import plotlyConfig from "@/utils/plotlyConfig";

interface PlotlyChartProps {
  figure: any;
  useContainerWidth?: boolean;
  style?: React.CSSProperties;
  config?: Record<string, any>;
}

const PlotlyChart: React.FC<PlotlyChartProps> = ({ figure, useContainerWidth = true, style, config }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const plotlyRef = useRef<any>(null);

  useEffect(() => {
    let Plotly: any;
    let mounted = true;

    const loadPlotly = async () => {
      const mod: any = await import("plotly.js-basic-dist");
      if (!mounted) return;
      // plotly.js-basic-dist is a CJS/UMD bundle (module.exports = Plotly).
      // Dynamic import() of a CJS module surfaces its exports under
      // `.default`; the top-level named properties (newPlot, purge, etc.)
      // aren't reliably re-exported for a bundle this size since Plotly
      // assigns most of its API at runtime rather than via static exports.
      // Falling back to `mod` keeps this working if a bundler ever does
      // flatten it.
      Plotly = mod.default ?? mod;
      if (!Plotly?.newPlot) {
        console.error("PlotlyChart: Plotly.newPlot is unavailable — module shape was", mod);
        return;
      }
      if (containerRef.current) {
        try {
          // Pass the shared Plotly config so every chart uses the same ModeBar
          // and interactivity settings. Do not modify figure.data or figure.layout.
          const mergedConfig = { ...plotlyConfig, ...(config ?? {}) };
          plotlyRef.current = Plotly.newPlot(containerRef.current, figure.data, figure.layout, mergedConfig);
        } catch (err) {
          console.error("PlotlyChart: failed to render figure", err);
        }
      }
    };

    loadPlotly();

    return () => {
      mounted = false;
      if (plotlyRef.current && containerRef.current) {
        plotlyRef.current.then?.((plotInstance: any) => {
          if (plotInstance && typeof plotInstance.purge === "function") {
            plotInstance.purge(containerRef.current!);
          }
        });
      }
    };
  }, [figure, config]);

  const containerStyle: React.CSSProperties = style?.height
    ? { width: "100%", ...style }
    : { width: "100%", minHeight: 320, ...style };

  return <div ref={containerRef} style={containerStyle} />;
};

export default PlotlyChart;
