import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { getRouter } from "./router";
import { DatasetProvider } from "./lib/app-context";
import "./styles.css";

const queryClient = new QueryClient();
const router = getRouter(queryClient);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <DatasetProvider>
        <RouterProvider router={router} />
      </DatasetProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
