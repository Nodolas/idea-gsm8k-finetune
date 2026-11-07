import { createBrowserRouter, createMemoryRouter, type RouteObject } from "react-router";

import { AppLayout } from "@/components/app-layout";
import { LandingPage } from "@/pages/landing";
import { ScoresPage } from "@/pages/scores";
import { TrainingPage } from "@/pages/training";

/** The three pages inside the shared layout. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "scores", element: <ScoresPage /> },
      { path: "training", element: <TrainingPage /> },
    ],
  },
];

export type AppRouter = ReturnType<typeof createBrowserRouter>;

/** The browser router for the app, or a memory router at `initialPath` for tests. */
export function createAppRouter(kind: "browser" | "memory", initialPath = "/"): AppRouter {
  if (kind === "memory") return createMemoryRouter(routes, { initialEntries: [initialPath] });
  return createBrowserRouter(routes);
}
