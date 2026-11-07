/**
 * Shared helpers for the website tests (tests/web): render a route of the real app under a fake
 * (or given) Api, or any element under an Api and a memory router.
 */
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, RouterProvider } from "react-router";

import type { Api } from "@/lib/api";
import { ApiProvider } from "@/lib/api-context";
import { createAppRouter, type AppRouter } from "@/router";
import { fakeApi, type FakeApi } from "@/test/fake-api";
import { setReducedMotion } from "@/test/setup";

export { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";

export interface RenderPageOptions<A extends Api = FakeApi> {
  /** The Api the page reads; defaults to `fakeApi()`. */
  api?: A;
  /** The operating system's reduce-motion setting; defaults to off. */
  reducedMotion?: boolean;
}

export type RenderPageResult<A extends Api> = RenderResult & { api: A; router: AppRouter };

/** Renders the app at `path` (e.g. "/training") inside its layout, under an ApiProvider. */
export function renderPage<A extends Api = FakeApi>(
  path: string,
  options: RenderPageOptions<A> = {},
): RenderPageResult<A> {
  setReducedMotion(options.reducedMotion ?? false);
  const api = (options.api ?? fakeApi()) as A;
  const router = createAppRouter("memory", path);
  const result = render(
    <ApiProvider api={api}>
      <RouterProvider router={router} />
    </ApiProvider>,
  );
  return { ...result, api, router };
}

/** Renders one element under an ApiProvider and a memory router (for links). */
export function renderWithApi(ui: ReactElement, api: Api = fakeApi()): RenderResult {
  return render(
    <ApiProvider api={api}>
      <MemoryRouter>{ui}</MemoryRouter>
    </ApiProvider>,
  );
}
