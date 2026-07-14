import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const getRouter = (queryClient?: QueryClient) => {
  const client = queryClient ?? new QueryClient();

  const router = createRouter({
    routeTree,
    context: { queryClient: client },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
