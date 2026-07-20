// Shared Plotly configuration used across the app.
// Keep this file limited to ModeBar / interactivity settings only.
export const plotlyConfig: any = {
  // Keep responsive behavior enabled so existing sizing/layout is preserved.
  responsive: true,
  // Always show the ModeBar.
  displayModeBar: true,
  // Hide Plotly logo in the ModeBar.
  displaylogo: false,
  // Enable mouse wheel (scroll) zooming.
  scrollZoom: true,
  // Define an explicit set of ModeBar buttons. This replaces the default set
  // so only the requested controls appear.
  // Exact button names are those used internally by Plotly: see docs.
  modeBarButtons: [
    [
      "toImage"
    ],
    [
      "zoom2d",
      "pan2d",
      "zoomIn2d",
      "zoomOut2d",
      "autoScale2d",
      "resetScale2d"
    ]
  ],
};

export default plotlyConfig;
