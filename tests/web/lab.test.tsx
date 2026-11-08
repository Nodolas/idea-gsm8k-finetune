/**
 * Part W (u11-finetune-lab, batch-9): the Lab page (US11.4). The top bar link and the lesson list
 * (AC11.4.1), the shown lesson and `?lesson=` (AC11.4.2), the guess kept in this browser and the
 * explanation (AC11.4.3), running, stopping and the 2-second refresh (AC11.4.4), the charts and
 * the results table (AC11.4.5), "What happened" (AC11.4.6), answers before and after with the
 * big-run and check texts (AC11.4.7), and the loading, error and never-run states (AC11.4.8).
 * Also the full-width rule for the new page and its top bar link (AC4.1.4).
 *
 * Hooks the page provides for these tests (text, roles and data-* only, never pixels):
 * - the lesson list is a list whose items (`<li>`) read "Lesson N · <title>" and the state word;
 * - each chart is an element `[data-chart="train-loss"]` / `[data-chart="dev-loss"]`, inside or
 *   itself `aria-hidden="true"`, holding one `[data-series="<variant name>"]` marker per variant
 *   with `data-points="<number of points drawn>"`, and a legend naming each variant's label;
 * - the results table has one row per variant, the variant's label in the row;
 * - "Answers before and after" uses a native `<select>` of the variant labels.
 */
import {
  ApiError,
  type LabLesson,
  type LabList,
  type LabMetricsLine,
  type LabState,
  type LabSummary,
} from "@/lib/api";
import {
  fakeApi,
  labLesson,
  labList,
  labSummary,
  LAB_LESSONS,
  type FakeApi,
} from "@/test/fake-api";
import { act, fireEvent, renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

const MODEL = "EleutherAI/pythia-31m";
const GUESS_KEY = (lessonId: string) => `gsm8k-lab-guess-${lessonId}`;
const NOT_RUN_TEXT = "Not run yet: press Run this lesson to fill the charts.";
const ROUTES = ["/", "/scores", "/training", "/reasoning", "/lab"] as const;
const STATE_WORDS: Record<LabState, string> = {
  "not-run": "Not run",
  running: "Running",
  finished: "Done",
  failed: "Failed",
  stopped: "Stopped",
};
const GUTTER = "px-[var(--gutter)]";

// ---------------------------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------------------------

/** Steps of a finished variant in these fixtures (dev lines at 0, 2, ..., 20: eleven of them). */
const TOTAL = 20;

function stepLine(step: number, total: number, loss: number | null): LabMetricsLine {
  return {
    v: 1,
    step,
    total_steps: total,
    loss,
    learning_rate: 1e-3,
    grad_norm: 0.5,
    elapsed_s: step * 1.5,
    dev_loss: null,
  };
}

function devLine(step: number, total: number, devLoss: number): LabMetricsLine {
  return {
    v: 1,
    step,
    total_steps: total,
    loss: null,
    learning_rate: null,
    grad_norm: null,
    elapsed_s: step * 1.5,
    dev_loss: devLoss,
  };
}

/** Lines that match a summary: step lines 1..TOTAL, dev lines at 0, 2, ..., TOTAL. */
function linesFor(s: LabSummary): LabMetricsLine[] {
  const lines: LabMetricsLine[] = [];
  const before = s.dev_loss_before ?? 2.8;
  const best = s.dev_loss_best ?? before;
  const bestStep = s.dev_loss_best_step ?? TOTAL;
  const after = s.dev_loss_after ?? best;
  for (let k = 0; k <= 10; k += 1) {
    const step = (k * TOTAL) / 10;
    let value: number;
    if (step === 0) value = before;
    else if (step === TOTAL) value = after;
    else if (step <= bestStep) value = before + ((best - before) * step) / Math.max(bestStep, 1);
    else value = best + ((after - best) * (step - bestStep)) / (TOTAL - bestStep);
    if (step === bestStep) value = best;
    lines.push(devLine(step, TOTAL, value));
  }
  const first = s.train_loss_first ?? 2.9;
  const last = s.train_loss_last ?? first;
  for (let step = 1; step <= TOTAL; step += 1) {
    const loss = first + ((last - first) * (step - 1)) / (TOTAL - 1);
    const missing = s.train_loss_last === null && step === TOTAL;
    lines.push(stepLine(step, TOTAL, missing ? null : loss));
  }
  return lines.sort((a, b) => a.step - b.step || (a.dev_loss === null ? 1 : -1));
}

/** A finished lesson: every variant has a summary (fixture defaults plus `specs`) and lines. */
function finishedLesson(lessonId: string, specs: Record<string, Partial<LabSummary>>): LabLesson {
  const base = labLesson(lessonId);
  return {
    ...base,
    lesson: { ...base.lesson, state: "finished" },
    status: {
      state: "finished",
      variant: null,
      done: base.results.map((r) => r.name),
      started_at: "2026-11-08T10:00:00Z",
      ended_at: "2026-11-08T10:12:00Z",
      message: null,
    },
    results: base.results.map((r) => {
      const summary = labSummary({
        lesson: lessonId,
        variant: r.name,
        label: r.label,
        steps: TOTAL,
        dev_loss_best_step: TOTAL,
        ...specs[r.name],
      });
      return { ...r, summary, lines: linesFor(summary) };
    }),
  };
}

const MIA = {
  question: "Mia reads 48 pages a day for 30 days. How many pages does she read?",
  gold: "1440",
  before: "Mia Mia Mia",
  after: "48 * 30 = 1340 #### 1340",
};
const EGGS = {
  question: "A box holds 7 eggs. How many eggs are in 125 boxes?",
  gold: "875",
  before: "box box box",
  after: "7 * 125 = 870 #### 870",
};

/**
 * Lesson l02 finished. Lowest dev loss after training: "Learning rate 1e-3" (1.523), which also
 * overfitted (best 1.401 at step 8). "Learning rate 1e-5" is 0.040 above its best (not over
 * 0.05, so not overfitted). "Learning rate 1e-2" diverged (last training loss above its first).
 */
const L02_DONE = finishedLesson("l02", {
  "lr-1e-5": {
    seconds: 30,
    seconds_per_step: 1.5,
    train_loss_first: 2.9,
    train_loss_last: 2.6,
    dev_loss_before: 2.8,
    dev_loss_after: 2.74,
    dev_loss_best: 2.7,
    dev_loss_best_step: 16,
    format_rate_after: 0.0625,
    accuracy_after: 0,
  },
  "lr-1e-4": {
    seconds: 36,
    seconds_per_step: 1.8,
    train_loss_first: 2.9,
    train_loss_last: 1.912,
    dev_loss_before: 2.8,
    dev_loss_after: 1.734,
    dev_loss_best: 1.734,
    dev_loss_best_step: 20,
    format_rate_after: 0.8438,
    accuracy_after: 0.0312,
    samples: [EGGS],
  },
  "lr-1e-3": {
    trainable_params: 196608,
    seconds: 42,
    seconds_per_step: 1.25,
    train_loss_first: 2.9,
    train_loss_last: 0.912,
    dev_loss_before: 2.8,
    dev_loss_after: 1.523,
    dev_loss_best: 1.401,
    dev_loss_best_step: 8,
    format_rate_before: 0,
    format_rate_after: 0.9375,
    accuracy_before: 0,
    accuracy_after: 0.0469,
    samples: [MIA],
  },
  "lr-1e-2": {
    seconds: 40,
    seconds_per_step: 2,
    train_loss_first: 2.9,
    train_loss_last: 6.214,
    dev_loss_before: 2.8,
    dev_loss_after: 7.105,
    dev_loss_best: 2.8,
    dev_loss_best_step: 0,
    format_rate_after: 0,
    accuracy_after: 0,
  },
});

/** Lesson l02 running its second variant at step 30 of 120 (the first variant done). */
function l02Running(): LabLesson {
  const base = labLesson("l02");
  const lines: LabMetricsLine[] = [
    devLine(0, 120, 2.8),
    devLine(12, 120, 2.4),
    devLine(24, 120, 2.1),
  ];
  for (let step = 1; step <= 30; step += 1) lines.push(stepLine(step, 120, 2.9 - step * 0.02));
  lines.sort((a, b) => a.step - b.step || (a.dev_loss === null ? 1 : -1));
  return {
    ...base,
    lesson: { ...base.lesson, state: "running" },
    status: {
      state: "running",
      variant: "lr-1e-4",
      done: ["lr-1e-5"],
      started_at: "2026-11-08T10:00:00Z",
      ended_at: null,
      message: null,
    },
    results: base.results.map((r, i) => {
      if (i === 0) return L02_DONE.results[0];
      if (i === 1) return { ...r, lines };
      return r;
    }),
  };
}

/** `GET /lab` with the given lesson states (others `not-run`) and active lesson. */
function listWith(states: Record<string, LabState>, active: string | null = null): LabList {
  const list = labList({ active });
  return {
    ...list,
    lessons: list.lessons.map((l) => ({ ...l, state: states[l.id] ?? l.state })),
  };
}

function allStates(state: LabState): Record<string, LabState> {
  return Object.fromEntries(LAB_LESSONS.map((l) => [l.id, state]));
}

/** A fake Api serving `list` and, per lesson id, the given lesson (else a never-run lesson). */
function labApi(list: LabList, lessons: Record<string, LabLesson> = {}): FakeApi {
  return fakeApi({
    getLab: async () => list,
    getLabLesson: async (lessonId: string) => lessons[lessonId] ?? labLesson(lessonId),
  });
}

/** Lesson l09 finished: "Final number only" has the lower dev loss, "Step by step" the higher accuracy. */
const L09_DONE = finishedLesson("l09", {
  "step-by-step": {
    dev_loss_after: 1.612,
    dev_loss_best: 1.612,
    accuracy_after: 0.0469,
    format_rate_after: 0.9375,
  },
  terse: {
    dev_loss_after: 0.412,
    dev_loss_best: 0.412,
    accuracy_after: 0.0156,
    format_rate_after: 0.6875,
  },
});

/** Lesson l10 finished: "Hot start" has no last training loss (it went non-finite). */
const L10_DONE = finishedLesson("l10", {
  "warmup-decay": { dev_loss_after: 1.5, dev_loss_best: 1.5 },
  constant: { dev_loss_after: 1.55, dev_loss_best: 1.55 },
  "hot-start": { train_loss_last: null, dev_loss_after: 1.6, dev_loss_best: 1.6 },
});

/** Lesson l11 finished: seeds end at 1.512, 1.534 and 1.498 (spread 0.036). */
const L11_DONE = finishedLesson("l11", {
  "seed-1": { dev_loss_after: 1.512, dev_loss_best: 1.512 },
  "seed-2": { dev_loss_after: 1.534, dev_loss_best: 1.534 },
  "seed-3": { dev_loss_after: 1.498, dev_loss_best: 1.498 },
});

/**
 * Lesson l12 finished: tokenizing once takes 2.5 s; re-tokenizing adds 0.42 s per step (25% of
 * its 1.68 s step, 33% of the 1.26 s step without it); padding 31% with random batches, 4% with
 * length-grouped ones.
 */
const L12_DONE = finishedLesson("l12", {
  "tokenize-once": {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: null,
    padding_fraction: 0.31,
    seconds_per_step: 1.26,
    dev_loss_after: 1.5,
    dev_loss_best: 1.5,
  },
  "by-length": {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: null,
    padding_fraction: 0.04,
    seconds_per_step: 1.05,
    dev_loss_after: 1.51,
    dev_loss_best: 1.51,
  },
  retokenize: {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: 0.42,
    padding_fraction: 0.31,
    seconds_per_step: 1.68,
    dev_loss_after: 1.5,
    dev_loss_best: 1.5,
  },
});

// ---------------------------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------------------------

function norm(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Whether `text` holds `token` as a whole number (not part of a longer number). */
function hasToken(text: string, token: string): boolean {
  return new RegExp(`(?<![\\d.,])${escapeRe(token)}(?![\\d,]|\\.\\d)`).test(text);
}

function expectTokens(text: string, tokens: string[]): void {
  for (const token of tokens) {
    expect(hasToken(text, token), `"${token}" in: ${text}`).toBe(true);
  }
}

/** The smallest elements whose text holds `text` (it may be split across child elements). */
function elementsWithText(text: string): HTMLElement[] {
  const wanted = norm(text);
  return [...document.body.querySelectorAll<HTMLElement>("*")].filter((el) => {
    if (!norm(el.textContent).includes(wanted)) return false;
    return ![...el.children].some((child) => norm(child.textContent).includes(wanted));
  });
}

function expectText(text: string): void {
  expect(elementsWithText(text), `text on the page: ${text}`).not.toHaveLength(0);
}

function expectNoText(text: string): void {
  expect(elementsWithText(text), `text not on the page: ${text}`).toHaveLength(0);
}

function follows(first: Node, second: Node): boolean {
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

function mainEl(): HTMLElement {
  return screen.getByRole("main");
}

/** The lesson list's items, in document order. */
function lessonItems(): HTMLElement[] {
  return screen.getAllByRole("listitem").filter((li) => /Lesson \d+ ·/.test(norm(li.textContent)));
}

function lessonItem(n: number, title: string): HTMLElement {
  const item = lessonItems().find((li) => norm(li.textContent).includes(`Lesson ${n} · ${title}`));
  if (!item) throw new Error(`No lesson list item "Lesson ${n} · ${title}"`);
  return item;
}

/** Waits until the lesson list has rendered (real timers only). */
async function findLessonList(): Promise<void> {
  await waitFor(() => expect(lessonItems()).toHaveLength(12));
}

async function findLessonHeading(n: number, title: string): Promise<HTMLElement> {
  return screen.findByRole("heading", { name: `Lesson ${n}: ${title}` });
}

function runButton(): HTMLElement {
  return screen.getByRole("button", { name: /^Run this lesson/ });
}

/** The first list after the "What happened" heading: its items' texts. */
function whatHappened(): string[] {
  const heading = screen.getByRole("heading", { name: "What happened" });
  const list = [...document.querySelectorAll<HTMLElement>("ul, ol")].find((l) =>
    follows(heading, l),
  );
  if (!list) throw new Error('No list after the "What happened" heading');
  return within(list)
    .getAllByRole("listitem")
    .map((li) => norm(li.textContent));
}

/** The results table: the table that names every given variant label. */
function resultsTable(labels: string[]): HTMLElement {
  const table = screen
    .getAllByRole("table")
    .find((t) => labels.every((label) => norm(t.textContent).includes(label)));
  if (!table) throw new Error(`No table naming ${labels.join(", ")}`);
  return table;
}

function rowText(table: HTMLElement, label: string): string {
  const row = within(table)
    .getAllByRole("row")
    .find((r) => norm(r.textContent).includes(label));
  if (!row) throw new Error(`No results row for ${label}`);
  return norm(row.textContent);
}

function headerTexts(table: HTMLElement): string[] {
  return [
    ...within(table).queryAllByRole("columnheader"),
    ...within(table).queryAllByRole("rowheader"),
  ].map((h) => norm(h.textContent));
}

function chart(kind: "train-loss" | "dev-loss"): HTMLElement {
  const el = document.querySelector<HTMLElement>(`[data-chart="${kind}"]`);
  if (!el) throw new Error(`No [data-chart="${kind}"] element`);
  return el;
}

/** Fakes the timers that drive the 2-second refresh; no waitFor, findBy or userEvent then. */
function fakeTimers(): void {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/** Lets pending fetches resolve and the page re-render (fake timers). */
async function settle(): Promise<void> {
  for (let i = 0; i < 6; i += 1) await advance(0);
}

function lessonCalls(api: FakeApi, lessonId: string): number {
  return api.getLabLesson.mock.calls.filter(([id]) => id === lessonId).length;
}

beforeEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    // storage unavailable in this environment: nothing to clear
  }
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  try {
    window.localStorage.clear();
  } catch {
    // nothing to clear
  }
});

// ---------------------------------------------------------------------------------------------
// AC11.4.1 top bar and lesson list
// ---------------------------------------------------------------------------------------------

describe("top bar and lesson list", () => {
  for (const route of ROUTES) {
    it(`AC11.4.1 the top bar has a Lab link to /lab after Reasoning on ${route}`, async () => {
      renderPage(route, { api: labApi(labList()) });
      const bar = await screen.findByRole("banner");
      const reasoning = within(bar).getByRole("link", { name: "Reasoning" });
      const lab = within(bar).getByRole("link", { name: "Lab" });
      expect(lab).toHaveAttribute("href", "/lab");
      expect(follows(reasoning, lab)).toBe(true);
      if (route === "/lab") expect(lab).toHaveAttribute("aria-current", "page");
      else expect(lab).not.toHaveAttribute("aria-current", "page");
    });
  }

  it("AC11.4.1 following the Lab link opens the Lab page", async () => {
    const user = userEvent.setup();
    const { router } = renderPage("/scores", { api: labApi(labList()) });
    const bar = await screen.findByRole("banner");
    await user.click(within(bar).getByRole("link", { name: "Lab" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/lab"));
    await findLessonList();
  });

  it("AC11.4.1 lists the twelve lessons in order as 'Lesson N · <title>'", async () => {
    renderPage("/lab", { api: labApi(labList()) });
    await findLessonList();
    const items = lessonItems();
    expect(items).toHaveLength(12);
    LAB_LESSONS.forEach((lesson, i) => {
      expect(norm(items[i].textContent)).toContain(`Lesson ${i + 1} · ${lesson.title}`);
    });
  });

  it("AC11.4.1 names each lesson's state in words", async () => {
    const states: Record<string, LabState> = {
      l01: "finished",
      l02: "running",
      l03: "failed",
      l04: "stopped",
    };
    renderPage("/lab", { api: labApi(listWith(states, "l02")) });
    await findLessonList();
    LAB_LESSONS.forEach((lesson, i) => {
      const state = states[lesson.id] ?? "not-run";
      const text = norm(lessonItem(i + 1, lesson.title).textContent);
      expect(text, lesson.id).toContain(STATE_WORDS[state]);
      for (const [other, word] of Object.entries(STATE_WORDS)) {
        if (other !== state) expect(text, `${lesson.id} not ${word}`).not.toContain(word);
      }
    });
  });

  it("AC11.4.1 names the lab model and that it runs on the CPU", async () => {
    renderPage("/lab", { api: labApi(labList()) });
    await findLessonList();
    const naming = [...mainEl().querySelectorAll<HTMLElement>("*")].filter((el) => {
      const text = el.textContent ?? "";
      return text.includes(MODEL) && /\bCPU\b/.test(text) && el.querySelector("button") === null;
    });
    expect(naming).not.toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.2 the shown lesson
// ---------------------------------------------------------------------------------------------

describe("shown lesson", () => {
  it("AC11.4.2 shows the first lesson when none has run", async () => {
    renderPage("/lab", { api: labApi(labList()) });
    expect(await findLessonHeading(1, "What a fine-tune does")).toBeInTheDocument();
  });

  it("AC11.4.2 shows the first lesson that is not finished", async () => {
    renderPage("/lab", { api: labApi(listWith({ l01: "finished", l02: "finished" })) });
    expect(await findLessonHeading(3, "Epochs and overfitting")).toBeInTheDocument();
  });

  it("AC11.4.2 a stopped lesson counts as not finished", async () => {
    renderPage("/lab", { api: labApi(listWith({ l01: "finished", l02: "stopped" })) });
    expect(await findLessonHeading(2, "Learning rate")).toBeInTheDocument();
  });

  it("AC11.4.2 shows the first lesson when every lesson is finished", async () => {
    renderPage("/lab", { api: labApi(listWith(allStates("finished"))) });
    expect(await findLessonHeading(1, "What a fine-tune does")).toBeInTheDocument();
  });

  it("AC11.4.2 shows the lesson named by ?lesson= in the address", async () => {
    const api = labApi(labList());
    renderPage("/lab?lesson=l07", { api });
    expect(await findLessonHeading(7, "Batch size")).toBeInTheDocument();
    expect(api.getLabLesson).toHaveBeenCalledWith("l07");
  });

  it("AC11.4.2 choosing a lesson in the list shows it and sets ?lesson=<id>", async () => {
    const user = userEvent.setup();
    const api = labApi(labList());
    const { router } = renderPage("/lab", { api });
    await findLessonHeading(1, "What a fine-tune does");
    const item = lessonItem(5, "LoRA rank");
    const control = item.querySelector<HTMLElement>("a[href], button, [role='button']") ?? item;
    await user.click(control);
    expect(await findLessonHeading(5, "LoRA rank")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toBe("?lesson=l05"));
    expect(api.getLabLesson).toHaveBeenCalledWith("l05");
  });

  it("AC11.4.2 the shown lesson has its question, what to watch and its variants with their changes", async () => {
    renderPage("/lab?lesson=l05", { api: labApi(labList()) });
    await findLessonHeading(5, "LoRA rank");
    expectText("Question of LoRA rank?");
    expectText("What to watch in LoRA rank.");
    for (const variant of LAB_LESSONS[4].variants) {
      expectText(variant.label);
      expectText(variant.changes);
    }
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.3 guess and explanation
// ---------------------------------------------------------------------------------------------

describe("guess and explanation", () => {
  const OPTIONS = LAB_LESSONS[1].guess_options;

  it("AC11.4.3 'Your guess' offers the lesson's three options as radio buttons", async () => {
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    expectText("Your guess");
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    for (const option of OPTIONS) {
      expect(screen.getByRole("radio", { name: option })).not.toBeChecked();
    }
  });

  it("AC11.4.3 a chosen option is kept in this browser under gsm8k-lab-guess-<lesson id>", async () => {
    const user = userEvent.setup();
    const first = renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await user.click(screen.getByRole("radio", { name: OPTIONS[1] }));
    expect(screen.getByRole("radio", { name: OPTIONS[1] })).toBeChecked();
    expect(window.localStorage.getItem(GUESS_KEY("l02"))).not.toBeNull();
    expect(window.localStorage.getItem(GUESS_KEY("l03"))).toBeNull();
    first.unmount();

    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expect(screen.getByRole("radio", { name: OPTIONS[1] })).toBeChecked());
    expect(screen.getByRole("radio", { name: OPTIONS[0] })).not.toBeChecked();
  });

  it("AC11.4.3 once the lesson is finished the page reads 'You guessed: <option>'", async () => {
    const user = userEvent.setup();
    const first = renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await user.click(screen.getByRole("radio", { name: OPTIONS[2] }));
    first.unmount();

    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expectText(`You guessed: ${OPTIONS[2]}`));
  });

  it("AC11.4.3 a finished lesson with no guess reads 'No guess made'", async () => {
    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expectText("No guess made"));
    expectNoText("You guessed:");
  });

  it("AC11.4.3 the page works when the browser's storage throws", async () => {
    const denied = () => {
      throw new DOMException("The operation is insecure.", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(denied);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(denied);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(denied);
    const user = userEvent.setup();
    const first = renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await user.click(screen.getByRole("radio", { name: OPTIONS[0] }));
    expect(screen.getByRole("radio", { name: OPTIONS[0] })).toBeChecked();
    first.unmount();

    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expectText("No guess made"));
  });

  it("AC11.4.3 the page works when the browser's storage cannot be reached at all", async () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("Access is denied for this document.", "SecurityError");
    });
    const user = userEvent.setup();
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await user.click(screen.getByRole("radio", { name: OPTIONS[1] }));
    expect(screen.getByRole("radio", { name: OPTIONS[1] })).toBeChecked();
  });

  it("AC11.4.3 before the lesson is finished 'Why it happens' shows only after 'Show the explanation now'", async () => {
    const user = userEvent.setup();
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    expectNoText(LAB_LESSONS[1].why);
    await user.click(screen.getByRole("button", { name: "Show the explanation now" }));
    await waitFor(() => expectText(LAB_LESSONS[1].why));
    expectText("Why it happens");
  });

  it("AC11.4.3 once the lesson is finished 'Why it happens' shows without pressing anything", async () => {
    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expectText(LAB_LESSONS[1].why));
    expectText("Why it happens");
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.4 running and stopping
// ---------------------------------------------------------------------------------------------

describe("run and stop", () => {
  const NOTE = "On the CPU, about 16 minutes. It never uses the GPU, so a GPU run keeps going.";

  it("AC11.4.4 the run button's note names the CPU, the minutes and that a GPU run keeps going", async () => {
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    expect(runButton()).toBeEnabled();
    expectText(NOTE);
  });

  it("AC11.4.4 'Run this lesson' calls POST /lab/{lesson}/run and then shows the variant and step", async () => {
    fakeTimers();
    let started = false;
    const api = fakeApi({
      getLab: async () => (started ? listWith({ l02: "running" }, "l02") : labList()),
      getLabLesson: async (lessonId: string) =>
        lessonId === "l02" && started ? l02Running() : labLesson(lessonId),
      runLabLesson: async (lessonId: string) => {
        started = true;
        return { lesson: lessonId, state: "running" as const };
      },
    });
    renderPage("/lab?lesson=l02", { api });
    await settle();
    expect(screen.getByRole("heading", { name: "Lesson 2: Learning rate" })).toBeInTheDocument();
    fireEvent.click(runButton());
    await settle();
    await advance(2000);
    await settle();
    expect(api.runLabLesson).toHaveBeenCalledTimes(1);
    expect(api.runLabLesson).toHaveBeenCalledWith("l02");
    expectText("Variant 2 of 4: Learning rate 1e-4, step 30 of 120");
    expect(screen.getByRole("button", { name: "Stop the lesson" })).toBeInTheDocument();
  });

  it("AC11.4.4 'Stop the lesson' calls POST /lab/stop", async () => {
    const user = userEvent.setup();
    const api = labApi(listWith({ l02: "running" }, "l02"), { l02: l02Running() });
    renderPage("/lab?lesson=l02", { api });
    await findLessonHeading(2, "Learning rate");
    await user.click(await screen.findByRole("button", { name: "Stop the lesson" }));
    await waitFor(() => expect(api.stopLab).toHaveBeenCalledTimes(1));
  });

  it("AC11.4.4 refreshes a running lesson every 2 seconds until its state is not running", async () => {
    fakeTimers();
    let current: LabLesson = l02Running();
    const api = fakeApi({
      getLab: async () =>
        current.status.state === "running"
          ? listWith({ l02: "running" }, "l02")
          : listWith({ l02: "finished" }),
      getLabLesson: async (lessonId: string) =>
        lessonId === "l02" ? current : labLesson(lessonId),
    });
    renderPage("/lab?lesson=l02", { api });
    await settle();
    expectText("Variant 2 of 4: Learning rate 1e-4, step 30 of 120");

    const first = lessonCalls(api, "l02");
    expect(first).toBeGreaterThan(0);
    await advance(1900);
    expect(lessonCalls(api, "l02")).toBe(first);
    await advance(100);
    await settle();
    const second = lessonCalls(api, "l02");
    expect(second).toBeGreaterThan(first);
    await advance(2000);
    await settle();
    const third = lessonCalls(api, "l02");
    expect(third).toBeGreaterThan(second);

    current = L02_DONE;
    await advance(2000);
    await settle();
    const afterFinish = lessonCalls(api, "l02");
    expect(afterFinish).toBeGreaterThan(third);
    expectNoText("Variant 2 of 4: Learning rate 1e-4, step 30 of 120");
    await advance(8000);
    await settle();
    expect(lessonCalls(api, "l02")).toBe(afterFinish);
    expect(screen.queryByRole("button", { name: "Stop the lesson" })).toBeNull();
  });

  it("AC11.4.4 while another lesson runs, 'Run this lesson' is disabled and names the running lesson", async () => {
    renderPage("/lab?lesson=l02", { api: labApi(listWith({ l03: "running" }, "l03")) });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expect(runButton()).toBeDisabled());
    const around = norm(runButton().parentElement?.textContent);
    expect(around).toMatch(/Lesson 3|Epochs and overfitting/);
  });

  it("AC11.4.4 a 409 lab_busy answer shows its message", async () => {
    const user = userEvent.setup();
    const message = "A lab run is already active: l03";
    const api = fakeApi({
      getLab: async () => labList(),
      getLabLesson: async (lessonId: string) => labLesson(lessonId),
      runLabLesson: async () => {
        throw new ApiError(409, "lab_busy", message);
      },
    });
    renderPage("/lab?lesson=l02", { api });
    await findLessonHeading(2, "Learning rate");
    await user.click(runButton());
    await waitFor(() => expectText(message));
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.5 charts and results table
// ---------------------------------------------------------------------------------------------

describe("charts and results table", () => {
  const L02_LABELS = LAB_LESSONS[1].variants.map((v) => v.label);
  const L02_NAMES = LAB_LESSONS[1].variants.map((v) => v.name);

  async function openL02Done(): Promise<void> {
    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expect(document.querySelector('[data-chart="train-loss"]')).not.toBeNull());
  }

  it("AC11.4.5 a 'Training loss' chart draws one line per variant with a legend of their labels", async () => {
    await openL02Done();
    expect(screen.getAllByText("Training loss").length).toBeGreaterThan(0);
    const el = chart("train-loss");
    const series = [...el.querySelectorAll<HTMLElement>("[data-series]")];
    expect(series.map((s) => s.getAttribute("data-series"))).toEqual(L02_NAMES);
    for (const s of series) expect(s.getAttribute("data-points")).toBe(String(TOTAL));
    for (const label of L02_LABELS) expect(norm(el.textContent)).toContain(label);
  });

  it("AC11.4.5 a 'Dev loss' chart draws one line per variant with a legend of their labels", async () => {
    await openL02Done();
    expect(screen.getAllByText("Dev loss").length).toBeGreaterThan(0);
    const el = chart("dev-loss");
    const series = [...el.querySelectorAll<HTMLElement>("[data-series]")];
    expect(series.map((s) => s.getAttribute("data-series"))).toEqual(L02_NAMES);
    for (const s of series) expect(s.getAttribute("data-points")).toBe("11");
    for (const label of L02_LABELS) expect(norm(el.textContent)).toContain(label);
  });

  it("AC11.4.5 the results table lists each variant's figures in the stated formats", async () => {
    await openL02Done();
    const table = resultsTable(L02_LABELS);
    expectTokens(rowText(table, "Learning rate 1e-3"), [
      "196,608",
      "20",
      "0.7",
      "1.25",
      "0.912",
      "2.800",
      "1.523",
      "1.401",
      "8",
      "0%",
      "94%",
      "5%",
    ]);
    expectTokens(rowText(table, "Learning rate 1e-4"), [
      "0.6",
      "1.80",
      "1.912",
      "1.734",
      "84%",
      "3%",
    ]);
    expectTokens(rowText(table, "Learning rate 1e-2"), ["2.00", "6.214", "7.105", "2.800"]);
    expect(headerTexts(table).some((h) => /padding/i.test(h))).toBe(false);
  });

  it("AC11.4.5 for l12 the table also lists tokenize seconds, re-tokenize seconds per step and padding", async () => {
    renderPage("/lab?lesson=l12", {
      api: labApi(listWith({ l12: "finished" }), { l12: L12_DONE }),
    });
    await findLessonHeading(12, "Where the time goes");
    const labels = LAB_LESSONS[11].variants.map((v) => v.label);
    const table = await waitFor(() => resultsTable(labels));
    const headers = headerTexts(table);
    expect(headers.some((h) => /tokeniz/i.test(h) && !/re-?tokeniz/i.test(h))).toBe(true);
    expect(headers.some((h) => /re-?tokeniz/i.test(h))).toBe(true);
    expect(headers.some((h) => /padding/i.test(h))).toBe(true);
    const once = rowText(table, "Tokenize once");
    expect(once).toMatch(/(?<![\d.])2\.50?(?![\d])/);
    expectTokens(once, ["31%"]);
    expectTokens(rowText(table, "Length-grouped batches"), ["4%"]);
    expectTokens(rowText(table, "Tokenize every step"), ["0.42", "31%"]);
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.6 what happened
// ---------------------------------------------------------------------------------------------

describe("what happened", () => {
  async function open(lessonId: string, n: number, title: string, lesson: LabLesson) {
    renderPage(`/lab?lesson=${lessonId}`, {
      api: labApi(listWith({ [lessonId]: "finished" }), { [lessonId]: lesson }),
    });
    await findLessonHeading(n, title);
    await screen.findByRole("heading", { name: "What happened" });
  }

  it("AC11.4.6 names the variant with the lowest dev loss after training and its value", async () => {
    await open("l02", 2, "Learning rate", L02_DONE);
    const items = whatHappened();
    expect(
      items.some(
        (t) => t.includes("Learning rate 1e-3") && hasToken(t, "1.523") && /lowest/i.test(t),
      ),
      items.join("\n"),
    ).toBe(true);
  });

  it("AC11.4.6 states that a variant more than 0.05 above its best dev loss overfitted", async () => {
    await open("l02", 2, "Learning rate", L02_DONE);
    const items = whatHappened();
    const overfit = items.find((t) => t.includes("Learning rate 1e-3") && /overfit/i.test(t));
    expect(overfit, items.join("\n")).toBeDefined();
    expectTokens(overfit ?? "", ["1.401", "1.523", "8"]);
    expect(items.some((t) => t.includes("Learning rate 1e-5") && /overfit/i.test(t))).toBe(false);
    expect(items.some((t) => t.includes("Learning rate 1e-4") && /overfit/i.test(t))).toBe(false);
  });

  it("AC11.4.6 states that training diverged when the last training loss is above the first", async () => {
    await open("l02", 2, "Learning rate", L02_DONE);
    const items = whatHappened();
    expect(items.some((t) => t.includes("Learning rate 1e-2") && /diverg/i.test(t))).toBe(true);
    for (const label of ["Learning rate 1e-5", "Learning rate 1e-4", "Learning rate 1e-3"]) {
      expect(
        items.some((t) => t.includes(label) && /diverg/i.test(t)),
        label,
      ).toBe(false);
    }
  });

  it("AC11.4.6 states that training diverged when the last training loss is missing", async () => {
    await open("l10", 10, "Warm-up and schedule", L10_DONE);
    const items = whatHappened();
    expect(items.some((t) => t.includes("Hot start") && /diverg/i.test(t))).toBe(true);
    expect(items.some((t) => t.includes("Constant") && /diverg/i.test(t))).toBe(false);
  });

  it("AC11.4.6 for l09 names the variant with the higher accuracy and the format rates instead", async () => {
    await open("l09", 9, "Answer format", L09_DONE);
    const items = whatHappened();
    const text = items.join(" ");
    expect(items.some((t) => t.includes("Step by step") && /accuracy/i.test(t))).toBe(true);
    expectTokens(text, ["94%", "69%"]);
    expect(hasToken(text, "0.412"), text).toBe(false);
  });

  it("AC11.4.6 for l11 states the spread of the last dev loss across seeds and that it is noise", async () => {
    await open("l11", 11, "Seed noise", L11_DONE);
    const items = whatHappened();
    const spread = items.find((t) => hasToken(t, "0.036"));
    expect(spread, items.join("\n")).toBeDefined();
    expect(items.join(" ")).toMatch(/noise/i);
  });

  it("AC11.4.6 for l12 states tokenize time, re-tokenize cost per step and the padding fractions", async () => {
    await open("l12", 12, "Where the time goes", L12_DONE);
    const text = whatHappened().join(" ");
    expect(text).toMatch(/(?<![\d.])2\.50?(?![\d])/);
    expectTokens(text, ["0.42", "31%", "4%"]);
    expect(text).toMatch(/(?<![\d.])(25|33)%/);
  });

  it("AC11.4.6 a lesson that is not finished has no 'What happened' list", async () => {
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    expect(screen.queryByRole("heading", { name: "What happened" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.7 answers before and after, big runs, check question
// ---------------------------------------------------------------------------------------------

describe("answers before and after", () => {
  async function openL02Done(): Promise<HTMLSelectElement> {
    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    const heading = await screen.findByRole("heading", { name: "Answers before and after" });
    const select = [...document.querySelectorAll<HTMLSelectElement>("select")].find((s) =>
      follows(heading, s),
    );
    if (!select) throw new Error('No <select> after "Answers before and after"');
    return select;
  }

  it("AC11.4.7 the select lists the variants with the lowest dev loss first and chosen", async () => {
    const select = await openL02Done();
    const options = [...select.options].map((o) => norm(o.textContent));
    expect(options[0]).toBe("Learning rate 1e-3");
    expect([...options].sort()).toEqual(LAB_LESSONS[1].variants.map((v) => v.label).sort());
    expect(norm(select.selectedOptions[0]?.textContent)).toBe("Learning rate 1e-3");
  });

  it("AC11.4.7 shows each sample's question, right answer, and answers before and after", async () => {
    await openL02Done();
    expectText(MIA.question);
    expectText(MIA.before);
    expectText(MIA.after);
    expect(hasToken(norm(mainEl().textContent), MIA.gold)).toBe(true);
    expectNoText(EGGS.question);
  });

  it("AC11.4.7 choosing another variant shows its samples", async () => {
    const user = userEvent.setup();
    const select = await openL02Done();
    await user.selectOptions(select, "Learning rate 1e-4");
    await waitFor(() => expectText(EGGS.question));
    expectText(EGGS.before);
    expectText(EGGS.after);
    expect(hasToken(norm(mainEl().textContent), EGGS.gold)).toBe(true);
    expectNoText(MIA.question);
  });

  it("AC11.4.7 shows 'For the big runs' with the big-run text and 'Check question' with its question", async () => {
    await openL02Done();
    expect(screen.getByRole("heading", { name: "For the big runs" })).toBeInTheDocument();
    expectText(LAB_LESSONS[1].big_run);
    expect(screen.getByRole("heading", { name: "Check question" })).toBeInTheDocument();
    expectText(LAB_LESSONS[1].check);
  });
});

// ---------------------------------------------------------------------------------------------
// AC11.4.8 loading, error, never run, charts hidden from assistive technology
// ---------------------------------------------------------------------------------------------

describe("states", () => {
  it("AC11.4.8 shows 'Reading the lab…' while the lab list loads", async () => {
    const api = fakeApi({ getLab: () => new Promise<LabList>(() => {}) });
    renderPage("/lab", { api });
    expect(await screen.findByText("Reading the lab…")).toBeInTheDocument();
  });

  it("AC11.4.8 shows the error's message with a 'Try again' button that reads the lab again", async () => {
    const user = userEvent.setup();
    let calls = 0;
    const api = fakeApi({
      getLab: async () => {
        calls += 1;
        if (calls === 1) throw new ApiError(0, "unreachable", "The run service is not reachable.");
        return labList();
      },
    });
    renderPage("/lab", { api });
    await waitFor(() => expectText("The run service is not reachable."));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await findLessonList();
    expect(api.getLab).toHaveBeenCalledTimes(2);
  });

  it("AC11.4.8 a lesson that has never run says 'Not run yet' and draws no chart", async () => {
    renderPage("/lab?lesson=l02", { api: labApi(labList()) });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expectText(NOT_RUN_TEXT));
    expect(document.querySelector("[data-chart]")).toBeNull();
  });

  it("AC11.4.8 the charts are hidden from assistive technology and their facts are in the table", async () => {
    renderPage("/lab?lesson=l02", {
      api: labApi(listWith({ l02: "finished" }), { l02: L02_DONE }),
    });
    await findLessonHeading(2, "Learning rate");
    await waitFor(() => expect(document.querySelectorAll("[data-chart]")).toHaveLength(2));
    for (const el of document.querySelectorAll<HTMLElement>("[data-chart]")) {
      expect(el.closest('[aria-hidden="true"]')).not.toBeNull();
    }
    const table = resultsTable(LAB_LESSONS[1].variants.map((v) => v.label));
    expect(table.closest('[aria-hidden="true"]')).toBeNull();
    expectNoText(NOT_RUN_TEXT);
  });
});

// ---------------------------------------------------------------------------------------------
// AC4.1.4 full width
// ---------------------------------------------------------------------------------------------

describe("full width", () => {
  function classesOf(el: Element): string[] {
    return (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
  }

  it("AC4.1.4 the Lab page's outer container spans the window less the gutter, with no width cap", async () => {
    renderPage("/lab", { api: labApi(labList()) });
    await findLessonHeading(1, "What a fine-tune does");
    const main = document.querySelector("main#main");
    expect(main).not.toBeNull();
    const container = main?.firstElementChild;
    expect(container).toBeTruthy();
    const classes = classesOf(container as Element);
    expect(classes).toContain(GUTTER);
    expect(classes.filter((c) => c.startsWith("max-w-"))).toEqual([]);
    expect(classes).not.toContain("mx-auto");
    for (const el of document.querySelectorAll("[class]")) {
      const cls = el.getAttribute("class") ?? "";
      expect(cls).not.toContain("max-w-[1280px]");
      expect(cls).not.toContain("max-w-[var(--content-width)]");
    }
  });

  it("AC4.1.4 the top bar row stays full width and shows the Lab link after Reasoning", async () => {
    renderPage("/lab", { api: labApi(labList()) });
    await findLessonHeading(1, "What a fine-tune does");
    const row = screen.getByRole("navigation", { name: "Main" });
    const classes = classesOf(row);
    expect(classes).toContain(GUTTER);
    expect(classes.filter((c) => c.startsWith("max-w-"))).toEqual([]);
    const reasoning = within(row).getByRole("link", { name: "Reasoning" });
    const lab = within(row).getByRole("link", { name: "Lab" });
    expect(follows(reasoning, lab)).toBe(true);
  });
});
