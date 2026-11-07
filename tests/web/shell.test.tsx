/**
 * u5-website, part W1: the shell every page shares (US4.1, AC4.1.1 and AC4.1.2): the skip link,
 * the top bar and keyboard reach of every control on the three routes.
 */
import type { Run } from "@/lib/api";
import {
  apiError,
  fakeApi,
  Q06,
  Q17,
  queueEntry,
  run,
  serviceStatus,
  withQueue,
  type FakeApi,
} from "@/test/fake-api";
import { renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

type User = ReturnType<typeof userEvent.setup>;

const ROUTES = ["/", "/scores", "/training"] as const;

const RUNS: Run[] = [
  run({
    run_id: "q17-base-dev-1",
    model: Q17,
    method: "base",
    dev_accuracy: 0.587,
    test_accuracy: 0.579,
    gain: null,
    minutes: 24,
    date: "2026-11-02T10:00:00Z",
    started_at: "2026-11-02T09:36:00Z",
  }),
  run({
    run_id: "q06-base-dev-1",
    model: Q06,
    method: "base",
    dev_accuracy: 0.413,
    gain: null,
    minutes: 11,
    date: "2026-11-01T10:00:00Z",
    started_at: "2026-11-01T09:49:00Z",
  }),
  run({
    run_id: "q17-sft-dev-2",
    model: Q17,
    method: "sft",
    dev_accuracy: 0.681,
    test_accuracy: 0.67,
    gain: 0.094,
    minutes: 52,
    date: "2026-11-05T10:00:00Z",
    started_at: "2026-11-05T09:08:00Z",
    finalist: true,
  }),
  run({
    run_id: "q06-sft-dev-3",
    model: Q06,
    method: "sft",
    dev_accuracy: 0.47,
    gain: 0.057,
    minutes: 23,
    date: "2026-11-04T12:00:00Z",
    started_at: "2026-11-04T11:37:00Z",
  }),
  run({
    run_id: "q06-sft-dev-1",
    model: Q06,
    method: "sft",
    dev_accuracy: null,
    gain: null,
    minutes: 7,
    date: "2026-11-04T19:09:00Z",
    started_at: "2026-11-04T19:02:00Z",
    status: "stopped",
  }),
];

function apiWithRuns(): FakeApi {
  const api = fakeApi({
    listRuns: async () => ({ runs: RUNS, skipped_rows: 0 }),
    getFinalists: async () => ["q17-sft-dev-2"],
  });
  return withQueue(api, [
    queueEntry({ attempt_id: "q06-sft-dev-4", config: { model: Q06, method: "sft" } }),
  ]);
}

function runningApi(): FakeApi {
  return fakeApi({
    getStatus: async () =>
      serviceStatus({
        status: "RUNNING",
        run_id: "q06-sft-dev-3",
        started_at: "2026-11-04T20:10:00Z",
      }),
  });
}

async function topBar(): Promise<HTMLElement> {
  return screen.findByRole("banner");
}

function wordmarkLink(bar: HTMLElement): HTMLElement {
  return within(bar).getByRole("link", { name: /gsm8k/ });
}

async function expectTopBar(): Promise<void> {
  const bar = await topBar();
  const home = wordmarkLink(bar);
  expect(home).toHaveTextContent("gsm8k");
  expect(home).toHaveAttribute("href", "/");
  expect(within(bar).getByRole("link", { name: "Scores" })).toHaveAttribute("href", "/scores");
  expect(within(bar).getByRole("link", { name: "Training" })).toHaveAttribute("href", "/training");
}

/** Native and ARIA controls a person can operate (disabled and hidden ones left out). */
const CONTROL_SELECTOR = [
  "a[href]",
  "button",
  "input",
  "select",
  "textarea",
  "summary",
  '[role="button"]',
  '[role="link"]',
  '[role="tab"]',
  '[role="checkbox"]',
  '[role="switch"]',
  '[role="combobox"]',
  '[role="menuitem"]',
  '[role="slider"]',
].join(", ");

function operableControls(): HTMLElement[] {
  return [...document.body.querySelectorAll<HTMLElement>(CONTROL_SELECTOR)].filter((el) => {
    if (el.matches(":disabled")) return false;
    if (el instanceof HTMLInputElement && el.type === "hidden") return false;
    if (el.closest('[aria-hidden="true"], [hidden], [inert]')) return false;
    return true;
  });
}

function describeControl(el: HTMLElement): string {
  const name =
    el.getAttribute("aria-label") ?? el.textContent?.trim() ?? el.getAttribute("name") ?? "";
  return `<${el.tagName.toLowerCase()} tabindex=${el.getAttribute("tabindex")}> ${name}`;
}

/** Presses Tab from the top of the page and returns every element that takes focus, in order. */
async function tabStops(user: User): Promise<HTMLElement[]> {
  (document.activeElement as HTMLElement | null)?.blur();
  const seen: HTMLElement[] = [];
  for (let i = 0; i < 400; i += 1) {
    await user.tab();
    const el = document.activeElement as HTMLElement | null;
    if (el === null || el === document.body || seen.includes(el)) break;
    seen.push(el);
  }
  return seen;
}

/**
 * Every operable control was a Tab stop. A tab of a tablist counts as reached when a tab of the
 * same tablist was (roving focus: the arrow keys move between tabs).
 */
function unreachable(stops: HTMLElement[]): string[] {
  return operableControls()
    .filter((el) => {
      if (stops.includes(el)) return false;
      if (el.getAttribute("role") === "tab") {
        const list = el.closest('[role="tablist"]');
        if (list && stops.some((stop) => list.contains(stop))) return false;
      }
      return true;
    })
    .map(describeControl);
}

/** The first Tab stops are the skip link and then the top bar links, in this order. */
function expectShellOrder(stops: HTMLElement[], bar: HTMLElement, runTag?: HTMLElement): void {
  const expected = [
    screen.getByRole("link", { name: "Skip to content" }),
    wordmarkLink(bar),
    ...(runTag ? [runTag] : []),
    within(bar).getByRole("link", { name: "Scores" }),
    within(bar).getByRole("link", { name: "Training" }),
  ];
  expect(stops.slice(0, expected.length).map(describeControl)).toEqual(
    expected.map(describeControl),
  );
  expected.forEach((el, i) => expect(stops[i]).toBe(el));
}

describe("top bar", () => {
  it("AC4.1.1 shows the wordmark linking home, Scores and Training on the landing page", async () => {
    renderPage("/", { api: apiWithRuns() });
    await expectTopBar();
  });

  it("AC4.1.1 shows the wordmark linking home, Scores and Training on the scores page", async () => {
    renderPage("/scores", { api: apiWithRuns() });
    await expectTopBar();
  });

  it("AC4.1.1 shows the wordmark linking home, Scores and Training on the training page", async () => {
    renderPage("/training", { api: apiWithRuns() });
    await expectTopBar();
  });

  it('AC4.1.1 marks only the current page\'s link with aria-current="page"', async () => {
    for (const route of ROUTES) {
      const { unmount } = renderPage(route, { api: apiWithRuns() });
      const bar = await topBar();
      const scores = within(bar).getByRole("link", { name: "Scores" });
      const training = within(bar).getByRole("link", { name: "Training" });
      if (route === "/scores") expect(scores).toHaveAttribute("aria-current", "page");
      else expect(scores).not.toHaveAttribute("aria-current", "page");
      if (route === "/training") expect(training).toHaveAttribute("aria-current", "page");
      else expect(training).not.toHaveAttribute("aria-current", "page");
      unmount();
    }
  });

  it("AC4.1.1 shows the running tag linking to Training while a run is active", async () => {
    renderPage("/scores", { api: runningApi() });
    const bar = await topBar();
    const tag = await within(bar).findByRole("link", { name: /RUNNING q06-sft-dev-3/ });
    expect(tag).toHaveAttribute("href", "/training");
  });

  it("AC4.1.1 keeps the top bar, without a running tag, when the status cannot be read", async () => {
    const api = fakeApi({
      getStatus: async () => {
        throw apiError(
          "unreachable",
          "The run service is not reachable at 127.0.0.1:8000. Start it with `make serve`.",
        );
      },
    });
    renderPage("/", { api });
    await expectTopBar();
    await waitFor(() => expect(api.getStatus).toHaveBeenCalled());
    const bar = await topBar();
    expect(within(bar).queryByText(/RUNNING/)).toBeNull();
  });
});

describe("keyboard", () => {
  it("AC4.1.2 Tab from the top reaches the skip link first, then the top bar links", async () => {
    const user = userEvent.setup();
    renderPage("/", { api: apiWithRuns() });
    const bar = await topBar();
    expect(within(bar).getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(document.querySelector("main#main")).not.toBeNull();
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
  });

  it("AC4.1.2 the skip link moves focus to the main content", async () => {
    const user = userEvent.setup();
    renderPage("/", { api: apiWithRuns() });
    await topBar();
    await user.tab();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveFocus();
    await user.keyboard("{Enter}");
    const main = document.querySelector<HTMLElement>("main#main");
    expect(main).not.toBeNull();
    await waitFor(() => expect(main).toHaveFocus());
  });

  it("AC4.1.2 with a run active, Tab goes skip link, wordmark, run tag, Scores, Training", async () => {
    const user = userEvent.setup();
    renderPage("/", { api: runningApi() });
    const bar = await topBar();
    const tag = await within(bar).findByRole("link", { name: /RUNNING q06-sft-dev-3/ });
    const stops = await tabStops(user);
    expectShellOrder(stops, bar, tag);
  });

  it("AC4.1.2 every control on the landing page is reachable by Tab", async () => {
    const user = userEvent.setup();
    renderPage("/", { api: apiWithRuns() });
    const bar = await topBar();
    await waitFor(() => expect(screen.getByRole("main")).toHaveTextContent("+9.4 pts"));
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
    const goToTraining = [
      ...screen.queryAllByRole("link", { name: "Go to training" }),
      ...screen.queryAllByRole("button", { name: "Go to training" }),
    ];
    expect(goToTraining).toHaveLength(1);
    expect(unreachable(stops)).toEqual([]);
  });

  it("AC4.1.2 every control on the scores page is reachable by Tab", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: apiWithRuns() });
    const bar = await topBar();
    await screen.findAllByText(/q17-sft-dev-2/);
    await screen.findAllByText(/q06-sft-dev-3/);
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
    expect(operableControls().length).toBeGreaterThan(4);
    expect(unreachable(stops)).toEqual([]);
  });

  it("AC4.1.2 every control on the training page is reachable by Tab", async () => {
    const user = userEvent.setup();
    renderPage("/training", { api: apiWithRuns() });
    const bar = await topBar();
    await screen.findAllByLabelText(/Learning rate/);
    await screen.findAllByText(/q17-sft-dev-2/);
    await screen.findAllByText(/q06-sft-dev-4/);
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
    expect(operableControls().length).toBeGreaterThan(4);
    expect(unreachable(stops)).toEqual([]);
  });
});
