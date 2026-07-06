import React, { useEffect, useRef } from "react";

interface PlotlyChartProps {
  figure: any;
  useContainerWidth?: boolean;
  style?: React.CSSProperties;
}

const PlotlyChart: React.FC<PlotlyChartProps> = ({ figure, useContainerWidth = true, style }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const plotlyRef = useRef<any>(null);

  useEffect(() => {
    let Plotly: any;
    let mounted = true;

    const loadPlotly = async () => {
      const mod = await import("plotly.js-basic-dist");
      if (!mounted) return;
      Plotly = mod;
      if (containerRef.current) {
        plotlyRef.current = Plotly.newPlot(containerRef.current, figure.data, figure.layout, {
          responsive: true,
          displayModeBar: false,
        });
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
  }, [figure]);

  return (
    <div ref={containerRef} style={{ width: "100%", minHeight: 320, ...style }} />
  );
};

export default PlotlyChart;
