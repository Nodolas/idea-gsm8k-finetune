import { createBrowserRouter, createMemoryRouter, type RouteObject } from "react-router";

import { AppLayout } from "@/components/app-layout";
import { CoursePage } from "@/pages/course";
import { LabPage } from "@/pages/lab";
import { LandingPage } from "@/pages/landing";
import { ReasoningPage } from "@/pages/reasoning";
import { ScoresPage } from "@/pages/scores";
import { TrainingPage } from "@/pages/training";

/** The pages inside the shared layout. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "scores", element: <ScoresPage /> },
      { path: "training", element: <TrainingPage /> },
      { path: "reasoning", element: <ReasoningPage /> },
      { path: "lab", element: <LabPage /> },
      { path: "course", element: <CoursePage /> },
    ],
  },
];

export type AppRouter = ReturnType<typeof createBrowserRouter>;

/** The browser router for the app, or a memory router at `initialPath` for tests. */
export function createAppRouter(kind: "browser" | "memory", initialPath = "/"): AppRouter {
  if (kind === "memory") return createMemoryRouter(routes, { initialEntries: [initialPath] });
  return createBrowserRouter(routes);
}
