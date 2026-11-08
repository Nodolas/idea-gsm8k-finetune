/**
 * Part C4 (u10-self-taught-cot): the Reasoning page (US10.4). The top bar link (AC10.4.1), the
 * comparison of base, reference fine-tune and self-taught runs (AC10.4.2), the examples and
 * keyboard reach (AC10.4.3), and the empty, error and loading states (AC10.4.4). Text, roles and
 * labels only, never colours or pixels.
 */
import { UNREACHABLE_MESSAGE, type Reasoning } from "@/lib/api";
import { formatGain, formatPct } from "@/lib/format";
import { apiError, fakeApi, reasoning, reasoningRole, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

type User = ReturnType<typeof userEvent.setup>;

const ROUTES = ["/", "/scores", "/training", "/reasoning"] as const;

const EMPTY_TEXT = "No self-taught chain-of-thought run yet";
const SUMMARY_HEADING = "How it affected the score";

const SUMMARY = [
  "Training on its own worked solutions moved the dev score a little, less than the noise band.",
  "The model now writes longer step-by-step answers before the final line.",
  "The reference fine-tune still scores higher on dev.",
];

const BASE_OUT_1 = ["Tom has 3 boxes of 12 pencils.", "He gives away 20 pencils.", "#### 16"].join(
  "\n",
);
const SELFCOT_OUT_1 = [
  "Tom starts with 3 boxes of 12 pencils, so 3 * 12 = 36 pencils.",
  "He gives away 20 pencils, so 36 - 20 = 16 pencils are left.",
  "Then he buys 2 more, so 16 + 2 = 18 pencils.",
  "#### 18",
].join("\n");
const BASE_OUT_2 = ["A ticket costs 25 dollars.", "#### 25"].join("\n");
const SELFCOT_OUT_2 = [
  "One ticket costs 25 dollars and she buys 50 tickets.",
  "So she pays 25 * 50 = 1250 dollars.",
  "#### 1250",
].join("\n");

/** A full comparison: base, reference fine-tune and self-taught runs, flips, generation, examples. */
const FULL: Reasoning = reasoning({
  available: true,
  roles: [
    reasoningRole("base", {
      run_id: "q17-base-dev-1",
      accuracy: 0.588,
      correct: 294,
      scored: 500,
      interval_low: 0.545,
      interval_high: 0.631,
      mean_lines: 3.4,
      mean_words: 38.6,
    }),
    reasoningRole("sft", {
      run_id: "q17-sft-dev-2",
      accuracy: 0.682,
      correct: 341,
      scored: 500,
      interval_low: 0.641,
      interval_high: 0.723,
      trained_on: 6973,
      gain_pts: 9.4,
      noise: "outside noise",
      mean_lines: 4.6,
      mean_words: 47.9,
    }),
    reasoningRole("selfcot", {
      run_id: "q17-selfcot-dev-1",
      accuracy: 0.62,
      correct: 310,
      scored: 500,
      interval_low: 0.577,
      interval_high: 0.663,
      trained_on: 1000,
      gain_pts: 3.2,
      noise: "within noise",
      mean_lines: 5.7,
      mean_words: 66.2,
    }),
  ],
  flips: [
    {
      role: "sft",
      run_id: "q17-sft-dev-2",
      against: "q17-base-dev-1",
      fixed: 83,
      broken: 36,
      both_right: 258,
      both_wrong: 123,
    },
    {
      role: "selfcot",
      run_id: "q17-selfcot-dev-1",
      against: "q17-base-dev-1",
      fixed: 71,
      broken: 55,
      both_right: 239,
      both_wrong: 135,
    },
  ],
  generation: {
    run_id: "q17-cotgen-train-1",
    problems: 1500,
    samples_per_problem: 4,
    solved: 1212,
    kept: 1104,
    kept_fraction: 0.736,
    mean_lines_kept: 5.9,
    mean_words_kept: 70.3,
    mean_lines_reference: 2.8,
    mean_words_reference: 44.1,
  },
  examples: [
    {
      problem_id: "gsm8k-dev-0042",
      gold: "18",
      base_output: BASE_OUT_1,
      selfcot_output: SELFCOT_OUT_1,
    },
    {
      problem_id: "gsm8k-dev-0317",
      gold: "1250",
      base_output: BASE_OUT_2,
      selfcot_output: SELFCOT_OUT_2,
    },
  ],
  summary: SUMMARY,
});

/** Base and reference figures only: no self-taught run yet. */
const NO_SELFCOT: Reasoning = reasoning({
  available: false,
  roles: [
    reasoningRole("base", {
      run_id: "q17-base-dev-1",
      accuracy: 0.588,
      correct: 294,
      scored: 500,
      interval_low: 0.545,
      interval_high: 0.631,
    }),
    reasoningRole("sft", {
      run_id: "q17-sft-dev-2",
      accuracy: 0.682,
      correct: 341,
      scored: 500,
      interval_low: 0.641,
      interval_high: 0.723,
      trained_on: 6973,
      gain_pts: 9.4,
      noise: "outside noise",
    }),
    reasoningRole("selfcot"),
  ],
});

function apiWith(data: Reasoning): FakeApi {
  return fakeApi({ getReasoning: async () => data });
}

function main(): HTMLElement {
  return screen.getByRole("main");
}

async function topBar(): Promise<HTMLElement> {
  return screen.findByRole("banner");
}

function wordmarkLink(bar: HTMLElement): HTMLElement {
  return within(bar).getByRole("link", { name: /gsm8k/ });
}

/** Waits until the full comparison has rendered (the summary heading is there). */
async function findSummaryHeading(): Promise<HTMLElement> {
  return screen.findByRole("heading", { level: 2, name: SUMMARY_HEADING });
}

/** Table rows that are not header rows. */
function bodyRows(table: HTMLElement): HTMLElement[] {
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("columnheader").length === 0);
}

/** The trimmed text of a row's first cell (its row header or first data cell). */
function firstCellText(row: HTMLElement): string {
  const cells = [...row.querySelectorAll("th, td")];
  return (cells[0]?.textContent ?? "").trim();
}

const ROLE_LABELS = {
  base: /base/i,
  sft: /reference fine-tune/i,
  selfcot: /self-taught/i,
} as const;

/** The score table: the table with a base, a reference fine-tune and a self-taught row. */
function scoreTable(): HTMLElement {
  const table = screen.getAllByRole("table").find((t) => {
    const labels = bodyRows(t).map(firstCellText);
    return Object.values(ROLE_LABELS).every((pattern) => labels.some((l) => pattern.test(l)));
  });
  if (!table) throw new Error("No table with base, reference fine-tune and self-taught rows");
  return table;
}

function roleRow(table: HTMLElement, role: keyof typeof ROLE_LABELS): HTMLElement {
  const row = bodyRows(table).find((r) => {
    const label = firstCellText(r);
    if (role === "base") {
      return ROLE_LABELS.base.test(label) && !/fine-tune|self-taught/i.test(label);
    }
    return ROLE_LABELS[role].test(label);
  });
  if (!row) throw new Error(`No score table row for ${role}`);
  return row;
}

/** The `pre` block whose text is exactly `text` (outputs are shown verbatim). */
function preWith(text: string): HTMLElement {
  const pre = [...main().querySelectorAll<HTMLElement>("pre")].find(
    (el) => (el.textContent ?? "").trim() === text,
  );
  if (!pre) throw new Error(`No <pre> block showing:\n${text}`);
  return pre;
}

/** The nearest ancestor of `el` whose text names `problemId`: the example's own block. */
function exampleBlock(el: HTMLElement, problemId: string): HTMLElement {
  let node: HTMLElement | null = el;
  while (node && !(node.textContent ?? "").includes(problemId)) node = node.parentElement;
  if (!node) throw new Error(`No block around the outputs names ${problemId}`);
  return node;
}

/** The text of `el` without its `pre` blocks (labels and figures around the outputs). */
function textOutsidePre(el: HTMLElement): string {
  const copy = el.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("pre").forEach((pre) => pre.remove());
  return copy.textContent ?? "";
}

function follows(first: Node, second: Node): boolean {
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
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

/** Every operable control was a Tab stop (a tab of a tablist counts when its tablist was). */
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

/** The first Tab stops: skip link, wordmark, Scores, Training, then Reasoning. */
function expectShellOrder(stops: HTMLElement[], bar: HTMLElement): void {
  const expected = [
    screen.getByRole("link", { name: "Skip to content" }),
    wordmarkLink(bar),
    within(bar).getByRole("link", { name: "Scores" }),
    within(bar).getByRole("link", { name: "Training" }),
    within(bar).getByRole("link", { name: "Reasoning" }),
  ];
  expect(stops.slice(0, expected.length).map(describeControl)).toEqual(
    expected.map(describeControl),
  );
  expected.forEach((el, i) => expect(stops[i]).toBe(el));
}

describe("top bar", () => {
  for (const route of ROUTES) {
    it(`AC10.4.1 shows a Reasoning link to /reasoning after Training on ${route}`, async () => {
      renderPage(route, { api: apiWith(FULL) });
      const bar = await topBar();
      const training = within(bar).getByRole("link", { name: "Training" });
      const reasoningLink = within(bar).getByRole("link", { name: "Reasoning" });
      expect(reasoningLink).toHaveAttribute("href", "/reasoning");
      expect(follows(training, reasoningLink)).toBe(true);
    });
  }

  it('AC10.4.1 marks the Reasoning link aria-current="page" only on /reasoning', async () => {
    for (const route of ROUTES) {
      const { unmount } = renderPage(route, { api: apiWith(FULL) });
      const bar = await topBar();
      const reasoningLink = within(bar).getByRole("link", { name: "Reasoning" });
      const scores = within(bar).getByRole("link", { name: "Scores" });
      const training = within(bar).getByRole("link", { name: "Training" });
      if (route === "/reasoning") {
        expect(reasoningLink).toHaveAttribute("aria-current", "page");
        expect(scores).not.toHaveAttribute("aria-current", "page");
        expect(training).not.toHaveAttribute("aria-current", "page");
      } else {
        expect(reasoningLink).not.toHaveAttribute("aria-current", "page");
      }
      unmount();
    }
  });

  it("AC10.4.1 following the Reasoning link opens the Reasoning page", async () => {
    const user = userEvent.setup();
    const { router } = renderPage("/scores", { api: apiWith(FULL) });
    const bar = await topBar();
    await user.click(within(bar).getByRole("link", { name: "Reasoning" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/reasoning"));
    expect(await screen.findByRole("heading", { level: 1, name: "Reasoning" })).toBeVisible();
  });

  it("AC10.4.1 Tab goes skip link, wordmark, Scores, Training, then Reasoning", async () => {
    const user = userEvent.setup();
    renderPage("/", { api: apiWith(FULL) });
    const bar = await topBar();
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
  });
});

describe("reasoning comparison", () => {
  it("AC10.4.2 has exactly one h1, Reasoning, and explains self-taught chain of thought", async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    await findSummaryHeading();
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]).toHaveTextContent("Reasoning");
    const explanation = [...main().querySelectorAll("p")].find((p) => {
      const text = p.textContent ?? "";
      return /self-taught/i.test(text) && /chain of thought/i.test(text);
    });
    expect(explanation).toBeDefined();
  });

  it("AC10.4.2 tables accuracy, interval, training problems, gain and noise for the three runs", async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    await findSummaryHeading();
    const table = scoreTable();
    const roles = bodyRows(table)
      .map(firstCellText)
      .filter((l) => Object.values(ROLE_LABELS).some((p) => p.test(l)));
    expect(roles).toHaveLength(3);

    const base = roleRow(table, "base").textContent ?? "";
    expect(base).toContain(formatPct(0.588));
    expect(base).toContain("54.5");
    expect(base).toContain("63.1");

    const sft = roleRow(table, "sft").textContent ?? "";
    expect(sft).toContain(formatPct(0.682));
    expect(sft).toContain("64.1");
    expect(sft).toContain("72.3");
    expect(sft).toMatch(/6,?973/);
    expect(sft).toContain(formatGain(9.4 / 100));
    expect(sft).toContain("outside noise");

    const selfcot = roleRow(table, "selfcot").textContent ?? "";
    expect(selfcot).toContain(formatPct(0.62));
    expect(selfcot).toContain("57.7");
    expect(selfcot).toContain("66.3");
    expect(selfcot).toMatch(/1,?000/);
    expect(selfcot).toContain(formatGain(3.2 / 100));
    expect(selfcot).toContain("within noise");

    // The base run is the reference point: it has no gain and no noise label.
    expect(base).not.toContain("noise");
  });

  it("AC10.4.2 shows fixed and broken counts and mean reasoning lines and words per run", async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    await findSummaryHeading();
    const text = main().textContent ?? "";
    expect(text).toMatch(/fixed/i);
    expect(text).toMatch(/broken/i);
    for (const count of ["83", "36", "71", "55"]) {
      expect(text).toMatch(new RegExp(`(^|[^0-9.,])${count}([^0-9.,%]|$)`));
    }
    expect(text).toMatch(/lines/i);
    expect(text).toMatch(/words/i);
    for (const mean of ["3.4", "38.6", "4.6", "47.9", "5.7", "66.2"]) {
      expect(text).toContain(mean);
    }
  });

  it("AC10.4.2 shows the generation figures of the self-taught run's generation run", async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    await findSummaryHeading();
    const text = main().textContent ?? "";
    expect(text).toContain("q17-cotgen-train-1");
    expect(text).toMatch(/1,?500/);
    expect(text).toMatch(/1,?212/);
    expect(text).toMatch(/1,?104/);
    expect(text).toContain(formatPct(0.736));
    for (const mean of ["5.9", "70.3", "2.8", "44.1"]) {
      expect(text).toContain(mean);
    }
  });

  it('AC10.4.2 puts the summary sentences under the h2 "How it affected the score"', async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    const heading = await findSummaryHeading();
    for (const sentence of SUMMARY) {
      const el = within(main()).getByText(sentence);
      expect(follows(heading, el)).toBe(true);
    }
  });
});

describe("reasoning examples and keyboard", () => {
  it("AC10.4.3 each example shows its problem id, gold answer and both outputs side by side", async () => {
    renderPage("/reasoning", { api: apiWith(FULL) });
    await findSummaryHeading();
    for (const example of FULL.examples) {
      const basePre = preWith(example.base_output);
      const selfPre = preWith(example.selfcot_output);
      const block = exampleBlock(basePre, example.problem_id);
      expect(block).not.toBe(main());
      expect(block.contains(selfPre)).toBe(true);
      expect(follows(basePre, selfPre)).toBe(true);
      const others = FULL.examples.filter((e) => e.problem_id !== example.problem_id);
      for (const other of others) expect(block.textContent).not.toContain(other.problem_id);
      // Labels may sit in the example's own block or, for a table, in its column headers.
      const header = block.closest("table")?.querySelector("thead")?.textContent ?? "";
      const around = `${textOutsidePre(block)} ${header}`;
      expect(around).toMatch(/gold/i);
      expect(textOutsidePre(block)).toContain(example.gold);
      expect(around).toMatch(/base/i);
      expect(around).toMatch(/self-taught/i);
    }
  });

  it("AC10.4.3 every control on the Reasoning page is reachable by Tab", async () => {
    const user = userEvent.setup();
    renderPage("/reasoning", { api: apiWith(FULL) });
    const bar = await topBar();
    await findSummaryHeading();
    preWith(SELFCOT_OUT_2);
    const stops = await tabStops(user);
    expectShellOrder(stops, bar);
    expect(unreachable(stops)).toEqual([]);
  });
});

describe("reasoning states", () => {
  it("AC10.4.4 with no self-taught run says so and shows the base and reference figures", async () => {
    renderPage("/reasoning", { api: apiWith(NO_SELFCOT) });
    await waitFor(() => expect(main()).toHaveTextContent(EMPTY_TEXT));
    const text = main().textContent ?? "";
    expect(text).toContain(formatPct(0.588));
    expect(text).toContain(formatPct(0.682));
    expect(text).toContain(formatGain(9.4 / 100));
    expect(text).toContain("outside noise");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("AC10.4.4 with no runs at all still says no self-taught run yet", async () => {
    renderPage("/reasoning", { api: fakeApi() });
    await waitFor(() => expect(main()).toHaveTextContent(EMPTY_TEXT));
    expect(main().querySelectorAll("pre")).toHaveLength(0);
  });

  it("AC10.4.4 names the service error when the comparison cannot be read", async () => {
    const api = fakeApi({
      getReasoning: async () => {
        throw apiError("run_log_unreadable", "Run log could not be read", "results/runs.csv");
      },
    });
    renderPage("/reasoning", { api });
    await waitFor(() => expect(main()).toHaveTextContent("Run log could not be read"));
    expect(main()).toHaveTextContent("results/runs.csv");
    expect(main()).not.toHaveTextContent(EMPTY_TEXT);
    expect(screen.queryByRole("heading", { level: 2, name: SUMMARY_HEADING })).toBeNull();
  });

  it("AC10.4.4 says what to do when the run service is unreachable", async () => {
    const api = fakeApi({
      getReasoning: async () => {
        throw apiError("unreachable", UNREACHABLE_MESSAGE);
      },
    });
    renderPage("/reasoning", { api });
    await waitFor(() =>
      expect(main()).toHaveTextContent("The run service is not reachable at 127.0.0.1:8000"),
    );
    expect(main().textContent).not.toMatch(/\b(500|undefined)\b/);
  });

  it("AC10.4.4 shows a loading state while the comparison loads", async () => {
    const api = fakeApi({ getReasoning: () => new Promise<Reasoning>(() => {}) });
    renderPage("/reasoning", { api });
    expect(await screen.findByRole("heading", { level: 1, name: "Reasoning" })).toBeVisible();
    await waitFor(() => expect(api.getReasoning).toHaveBeenCalled());
    expect(main().textContent).toMatch(/loading/i);
    expect(main()).not.toHaveTextContent(EMPTY_TEXT);
    expect(screen.queryByRole("heading", { level: 2, name: SUMMARY_HEADING })).toBeNull();
  });
});
