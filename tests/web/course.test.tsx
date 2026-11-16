/**
 * Part W (u12-learning-course, batch-13): the Course page and the landing card (US12.5,
 * AC12.5.1-AC12.5.11, AC12.5.13) and the Training page's "Course" mark (AC12.3.8, web side).
 *
 * Text, roles and data-* hooks only, never pixels. Hooks the page provides for these tests
 * (beyond the exact texts of the spec):
 * - the shown step is one `<article data-step="<id>">`; the step list is a list whose innermost
 *   items (`<li>`) read "Step N · <title>" with the state word and the kind word, each with one
 *   button or link that chooses the step;
 * - each part has an element `[data-part-progress="<n>"]` carrying its done count as text
 *   ("D of T");
 * - each run of a gpu step is an element `[data-run="<run>"]` holding its model, changes,
 *   estimate, state word and result;
 * - quiz questions are native radio groups: `role="group"` named by the prompt, one native
 *   `radio` per option; after "Check my answers" the right option of a question carries
 *   `data-right-option`;
 * - c02: one `[data-model="<model id>"]` block per model holding its token counts, and the
 *   sample's first tokens as `[data-token-chip]` elements; c03: one
 *   `[data-bar="weights-by-part"]` (Qwen3-0.6B) with one `[data-segment="<part>"]` per part
 *   (embeddings, attention, mlp, norms, head) beside a table with the numbers;
 * - c24: each comparison row (a `<tr>`) holds one `[data-interval-bar]`.
 */
import {
  ApiError,
  type Api,
  type CourseComparisonRow,
  type CourseMemoryRow,
  type CourseOverview,
  type CourseRun,
  type CourseStep,
  type CourseStepSummary,
  type Status,
} from "@/lib/api";
import {
  apiError,
  COURSE_PARTS,
  COURSE_STEPS,
  courseArchitectures,
  courseOverview,
  courseRun,
  courseStep,
  fakeApi,
  LAB_LESSONS,
  Q06,
  Q17,
  run,
  serviceStatus,
  type FakeApi,
} from "@/test/fake-api";
import { act, renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

const GUTTER = "px-[var(--gutter)]";
const PROSE_CAP = "max-w-[75ch]";
const ROUTES = ["/", "/scores", "/training", "/reasoning", "/lab", "/course"] as const;
const KIND_WORDS = {
  gpu: "GPU run",
  inspect: "CPU inspection",
  lab: "Lab lesson",
  read: "Reading",
} as const;
const STATE_WORDS = {
  "not-started": "Not started",
  "in-progress": "In progress",
  done: "Done",
} as const;
const HELD_BY_OTHER = "q06-sft-dev-1";

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

/** The smallest elements whose text holds `text` (it may be split across child elements). */
function elementsWithText(text: string, scope: ParentNode = document.body): HTMLElement[] {
  const wanted = norm(text);
  return [...scope.querySelectorAll<HTMLElement>("*")].filter((el) => {
    if (!norm(el.textContent).includes(wanted)) return false;
    return ![...el.children].some((child) => norm(child.textContent).includes(wanted));
  });
}

function expectText(text: string, scope: ParentNode = document.body): void {
  expect(elementsWithText(text, scope), `text on the page: ${text}`).not.toHaveLength(0);
}

function expectNoText(text: string, scope: ParentNode = document.body): void {
  expect(elementsWithText(text, scope), `text not on the page: ${text}`).toHaveLength(0);
}

function follows(first: Node, second: Node): boolean {
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

function classesOf(el: Element): string[] {
  return (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
}

/** An element, or one of its ancestors, carries the 75-character prose cap. */
function hasProseCap(el: Element): boolean {
  for (let node: Element | null = el; node; node = node.parentElement) {
    if (classesOf(node).includes(PROSE_CAP)) return true;
  }
  return false;
}

const doneSteps = (count: number): Partial<CourseStepSummary>[] =>
  Array.from({ length: count }, () => ({
    state: "done" as const,
    run_done: true,
    quiz_passed: true,
  }));

function stepTitle(stepId: string): string {
  return COURSE_STEPS.find((step) => step.id === stepId)?.title ?? stepId;
}

interface CourseApiOptions {
  overview?: CourseOverview;
  steps?: Record<string, CourseStep>;
  status?: Status;
  extra?: Partial<Api>;
}

/** A fake Api for the course: an overview, some prepared steps (others are the defaults). */
function courseApi(options: CourseApiOptions = {}): FakeApi {
  const status = options.status;
  return fakeApi({
    getCourse: async () => options.overview ?? courseOverview(),
    getCourseStep: async (id: string) => options.steps?.[id] ?? courseStep(id),
    ...(status ? { getStatus: async () => status } : {}),
    ...options.extra,
  });
}

/** Renders `/course?step=<id>` and waits for the shown step. */
async function showStep(api: FakeApi, stepId: string, search = "") {
  const rendered = renderPage(`/course?step=${stepId}${search}`, { api });
  const article = await waitFor(() => {
    const el = document.querySelector<HTMLElement>(`[data-step="${stepId}"]`);
    if (!el) throw new Error(`no [data-step="${stepId}"]`);
    return el;
  });
  return { ...rendered, article };
}

function runRow(runName: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(`[data-run="${runName}"]`);
  if (!el) throw new Error(`no [data-run="${runName}"]`);
  return el;
}

async function findRunRow(runName: string): Promise<HTMLElement> {
  return waitFor(() => runRow(runName));
}

function tableRow(pattern: RegExp | string): HTMLElement {
  const wanted = typeof pattern === "string" ? new RegExp(escapeRe(pattern)) : pattern;
  const row = screen.getAllByRole("row").find((tr) => wanted.test(norm(tr.textContent)));
  if (!row) throw new Error(`no table row matching ${String(wanted)}`);
  return row;
}

/** The innermost list item of the step list that reads "Step N · <title>". */
function stepItem(number: number): HTMLElement {
  const title = COURSE_STEPS[number - 1].title;
  const wanted = `Step ${number} · ${title}`;
  const item = screen
    .getAllByRole("listitem")
    .find((li) => !li.querySelector("li") && norm(li.textContent).includes(wanted));
  if (!item) throw new Error(`no list item for "${wanted}"`);
  return item;
}

function controlIn(item: HTMLElement): HTMLElement {
  const control = within(item).queryByRole("button") ?? within(item).queryByRole("link");
  if (!control) throw new Error(`no button or link in "${norm(item.textContent)}"`);
  return control;
}

function groupFor(prompt: string): HTMLElement {
  return screen.getByRole("group", { name: new RegExp(escapeRe(prompt)) });
}

type User = ReturnType<typeof userEvent.setup>;

/** Chooses one option (by index) per question of the shown step. */
async function choose(user: User, stepId: string, choices: number[]): Promise<void> {
  const questions = courseStep(stepId).questions;
  for (let i = 0; i < choices.length; i += 1) {
    const radios = within(groupFor(questions[i].prompt)).getAllByRole("radio");
    await user.click(radios[choices[i]]);
  }
}

const RIGHT_OPTIONS = [0, 2];
const EXPLANATIONS = ["Because the first option is the right one.", "Because the third one is it."];

/** A fake Api for a step's quiz: answers are checked against RIGHT_OPTIONS and remembered. */
function quizApi(
  stepId: string,
  base: Partial<CourseStep> = {},
  extra: Partial<Api> = {},
): FakeApi {
  let submitted: number[] | null = null;
  return fakeApi({
    getCourse: async () => courseOverview(),
    getCourseStep: async (id: string) => {
      const step = courseStep(id, id === stepId ? base : {});
      if (id !== stepId || !submitted) return step;
      const passed = submitted.every((answer, i) => answer === RIGHT_OPTIONS[i]);
      return {
        ...step,
        questions: step.questions.map((q, i) => ({
          ...q,
          answered: true,
          right: RIGHT_OPTIONS[i],
          explanation: EXPLANATIONS[i],
        })),
        step: {
          ...step.step,
          quiz_passed: passed,
          state: passed && step.step.run_done ? ("done" as const) : ("in-progress" as const),
        },
      };
    },
    submitCourseQuiz: async (_id: string, answers: number[]) => {
      submitted = answers;
      const results = answers.map((answer, i) => ({
        right: answer === RIGHT_OPTIONS[i],
        right_option: RIGHT_OPTIONS[i],
        explanation: EXPLANATIONS[i],
      }));
      return { results, passed: results.every((r) => r.right), attempts: 1 };
    },
    ...extra,
  });
}

/** A leaf element reading exactly `word` inside `scope`. */
function hasWord(scope: Element, word: string): boolean {
  return [...scope.querySelectorAll("*")].some(
    (el) => el.children.length === 0 && norm(el.textContent) === word,
  );
}

/** Fakes the timers that drive the 3-second refresh; no waitFor, findBy or userEvent then. */
function fakeTimers(): void {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function settle(): Promise<void> {
  for (let i = 0; i < 6; i += 1) await advance(0);
}

function stepCalls(api: FakeApi, stepId: string): number {
  return api.getCourseStep.mock.calls.filter(([id]) => id === stepId).length;
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------------------------
// AC12.5.1 top bar link, progress, parts, first-try, continue
// ---------------------------------------------------------------------------------------------

describe("AC12.5.1 top bar and progress", () => {
  for (const route of ROUTES) {
    it(`AC12.5.1 the top bar has a Course link to /course after Lab on ${route}`, async () => {
      renderPage(route, { api: courseApi() });
      const bar = await screen.findByRole("banner");
      const lab = within(bar).getByRole("link", { name: "Lab" });
      const course = within(bar).getByRole("link", { name: "Course" });
      expect(course).toHaveAttribute("href", "/course");
      expect(follows(lab, course)).toBe(true);
      if (route === "/course") expect(course).toHaveAttribute("aria-current", "page");
      else expect(course).not.toHaveAttribute("aria-current", "page");
    });
  }

  it("AC12.5.1 shows the progress line, the first-try line and a Continue button", async () => {
    const api = courseApi({
      overview: courseOverview({
        steps: doneSteps(7),
        first_try_right: 9,
        questions_answered: 12,
      }),
    });
    renderPage("/course", { api });
    await waitFor(() => expectText("Your progress: 7 of 24 steps done (29 %)"));
    expectText("First-try answers right: 9 of 12");
    expect(
      screen.getByRole("button", { name: "Continue with step 8: Learning rate" }),
    ).toBeInTheDocument();
  });

  it("AC12.5.1 shows one bar per part with its done count as text", async () => {
    const api = courseApi({
      overview: courseOverview({ steps: doneSteps(7) }),
    });
    renderPage("/course", { api });
    await waitFor(() => expectText("Your progress: 7 of 24 steps done"));
    // Parts 1 and 2 hold steps 1 and 2-6, part 3 holds steps 7-18; step 7 is done.
    const expected = ["1 of 1", "5 of 5", "1 of 12", "0 of 2", "0 of 4"];
    expected.forEach((count, i) => {
      const bar = document.querySelector<HTMLElement>(`[data-part-progress="${i + 1}"]`);
      expect(bar, `part ${i + 1} progress`).not.toBeNull();
      expect(norm(bar?.textContent)).toContain(count);
    });
  });

  it("AC12.5.1 Continue opens the next step", async () => {
    const user = userEvent.setup();
    const api = courseApi({ overview: courseOverview({ steps: doneSteps(7) }) });
    const { router } = renderPage("/course?step=c01", { api });
    await user.click(
      await screen.findByRole("button", { name: "Continue with step 8: Learning rate" }),
    );
    await waitFor(() =>
      expect(new URLSearchParams(router.state.location.search).get("step")).toBe("c08"),
    );
    await waitFor(() => expect(api.openCourseStep).toHaveBeenCalledWith("c08"));
    await waitFor(() => expect(document.querySelector('[data-step="c08"]')).not.toBeNull());
  });

  it("AC12.5.1 reads Course complete when no step is left", async () => {
    const api = courseApi({ overview: courseOverview({ steps: doneSteps(24) }) });
    renderPage("/course", { api });
    await waitFor(() => expectText("Your progress: 24 of 24 steps done (100 %)"));
    expectText("Course complete");
    expect(screen.queryByRole("button", { name: /^Continue with step/ })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.2 the parts and steps list
// ---------------------------------------------------------------------------------------------

describe("AC12.5.2 the parts and steps list", () => {
  it("AC12.5.2 lists the five parts and all 24 steps as 'Step N · <title>' with state and kind in words", async () => {
    const api = courseApi({
      overview: courseOverview({
        steps: [{ state: "done" }, { state: "done" }, { state: "in-progress" }],
      }),
    });
    renderPage("/course", { api });
    await waitFor(() => stepItem(1));
    for (const title of COURSE_PARTS) {
      expect(
        elementsWithText(title.replace(/^\d+\.\s*/, "")).length,
        `part title ${title}`,
      ).toBeGreaterThan(0);
    }
    COURSE_STEPS.forEach((step, i) => {
      const text = norm(stepItem(i + 1).textContent);
      expect(text, `kind of step ${i + 1}`).toContain(KIND_WORDS[step.kind]);
    });
    expect(norm(stepItem(1).textContent)).toContain(STATE_WORDS.done);
    expect(norm(stepItem(2).textContent)).toContain(STATE_WORDS.done);
    expect(norm(stepItem(3).textContent)).toContain(STATE_WORDS["in-progress"]);
    expect(norm(stepItem(4).textContent)).toContain(STATE_WORDS["not-started"]);
    expect(norm(stepItem(24).textContent)).toContain(STATE_WORDS["not-started"]);
  });

  it("AC12.5.2 with no step in the address the next step is shown", async () => {
    const api = courseApi({ overview: courseOverview({ steps: doneSteps(7) }) });
    renderPage("/course", { api });
    await waitFor(() => expect(api.getCourseStep).toHaveBeenCalledWith("c08"));
    await waitFor(() => expect(document.querySelector('[data-step="c08"]')).not.toBeNull());
    expect(await screen.findByRole("heading", { name: "Why this step" })).toBeInTheDocument();
  });

  it("AC12.5.2 with every step done the first step is shown", async () => {
    const api = courseApi({ overview: courseOverview({ steps: doneSteps(24) }) });
    renderPage("/course", { api });
    await waitFor(() => expect(api.getCourseStep).toHaveBeenCalledWith("c01"));
    await waitFor(() => expect(document.querySelector('[data-step="c01"]')).not.toBeNull());
  });

  it("AC12.5.2 choosing a step shows it, sets ?step= and calls POST /course/{step}/open", async () => {
    const user = userEvent.setup();
    const api = courseApi();
    const { router } = renderPage("/course?step=c01", { api });
    await waitFor(() => stepItem(3));
    await user.click(controlIn(stepItem(3)));
    await waitFor(() =>
      expect(new URLSearchParams(router.state.location.search).get("step")).toBe("c03"),
    );
    await waitFor(() => expect(api.openCourseStep).toHaveBeenCalledWith("c03"));
    await waitFor(() => expect(api.getCourseStep).toHaveBeenCalledWith("c03"));
    await waitFor(() => expect(document.querySelector('[data-step="c03"]')).not.toBeNull());
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.3 the shown step, section order, questions behind a button
// ---------------------------------------------------------------------------------------------

describe("AC12.5.3 the shown step", () => {
  it("AC12.5.3 shows why, body, run area, questions and own words in this order", async () => {
    const { article } = await showStep(courseApi(), "c01");
    const title = stepTitle("c01");
    const why = await screen.findByRole("heading", { name: "Why this step" });
    const whyText = elementsWithText(`Why ${title} comes now.`, article)[0];
    const body = elementsWithText("A second paragraph.", article)[0];
    const runButton = screen.getByRole("button", { name: "Run this step" });
    const check = screen.getByRole("heading", { name: "Check what you learned" });
    const own = screen.getByRole("heading", { name: "In your own words" });
    expect(whyText).toBeDefined();
    expect(body).toBeDefined();
    const chain = [why, whyText, body, runButton, check, own];
    for (let i = 0; i + 1 < chain.length; i += 1) {
      expect(follows(chain[i], chain[i + 1]), `section ${i} before ${i + 1}`).toBe(true);
    }
    expectText(`In your own words: what did ${title} show?`, article);
  });

  it("AC12.5.3 hides the questions behind 'I have read this, show the questions' until the run part is done", async () => {
    const user = userEvent.setup();
    const { article } = await showStep(courseApi(), "c01");
    const prompt = courseStep("c01").questions[0].prompt;
    const reveal = await screen.findByRole("button", {
      name: "I have read this, show the questions",
    });
    expectNoText(prompt, article);
    expect(screen.queryByRole("radio")).toBeNull();
    await user.click(reveal);
    expect(await screen.findByRole("group", { name: new RegExp(escapeRe(prompt)) })).toBeVisible();
    expect(screen.getAllByRole("radio").length).toBeGreaterThan(0);
  });

  it("AC12.5.3 shows the questions at once when the step's run part is done", async () => {
    const base = courseStep("c01");
    const api = courseApi({
      steps: {
        c01: courseStep("c01", {
          step: { ...base.step, run_done: true, state: "in-progress" },
          runs: [courseRun({ run: "base-06", state: "finished", accuracy: 0.4 })],
        }),
      },
    });
    const { article } = await showStep(api, "c01");
    expect(
      await screen.findByRole("group", { name: new RegExp(escapeRe(base.questions[0].prompt)) }),
    ).toBeInTheDocument();
    expect(
      within(article).queryByRole("button", { name: "I have read this, show the questions" }),
    ).toBeNull();
  });

  it("AC12.5.3 always shows the questions of a read step", async () => {
    const { article } = await showStep(courseApi(), "c06");
    expect(
      await screen.findByRole("group", {
        name: new RegExp(escapeRe(courseStep("c06").questions[0].prompt)),
      }),
    ).toBeInTheDocument();
    expect(
      within(article).queryByRole("button", { name: "I have read this, show the questions" }),
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.4 the gpu run area
// ---------------------------------------------------------------------------------------------

describe("AC12.5.4 the gpu run area", () => {
  it("AC12.5.4 lists each run with its model, changes and estimate, measured or not", async () => {
    const api = courseApi({
      steps: {
        c05: courseStep("c05", {
          runs: [
            courseRun({ run: "pythia", estimate_minutes: 1, estimate_measured: true }),
            courseRun({ run: "smollm2", estimate_minutes: 2, changes: "method base" }),
            courseRun({ run: "qwen25", estimate_minutes: 3 }),
            courseRun({ run: "qwen3-17", estimate_minutes: 6 }),
          ],
        }),
      },
    });
    await showStep(api, "c05");
    const pythia = norm((await findRunRow("pythia")).textContent);
    expect(pythia).toContain("EleutherAI/pythia-31m");
    expect(pythia).toContain("about 1 min on the GPU");
    expect(pythia).not.toContain("estimate, not measured yet");
    const smol = norm(runRow("smollm2").textContent);
    expect(smol).toContain("HuggingFaceTB/SmolLM2-360M");
    expect(smol).toContain("method base");
    expect(smol).toContain("about 2 min on the GPU");
    expect(smol).toContain("(estimate, not measured yet)");
    expect(norm(runRow("qwen25").textContent)).toContain("Qwen/Qwen2.5-0.5B");
    expect(norm(runRow("qwen3-17").textContent)).toContain(`${Q17}`);
    expect(norm(runRow("qwen3-17").textContent)).toContain("about 6 min on the GPU");
    const order = ["pythia", "smollm2", "qwen25", "qwen3-17"].map(runRow);
    for (let i = 0; i + 1 < order.length; i += 1)
      expect(follows(order[i], order[i + 1])).toBe(true);
  });

  it("AC12.5.4 'Run this step' calls POST /course/{step}/run and reads the step again", async () => {
    const user = userEvent.setup();
    const api = courseApi();
    await showStep(api, "c01");
    const before = api.getCourseStep.mock.calls.length;
    await user.click(await screen.findByRole("button", { name: "Run this step" }));
    await waitFor(() => expect(api.runCourseStep).toHaveBeenCalledWith("c01"));
    expect(api.runCourseStep).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(api.getCourseStep.mock.calls.length).toBeGreaterThan(before));
  });

  it("AC12.5.4 names each run's state in words", async () => {
    const states: Array<[CourseRun["state"], RegExp]> = [
      ["not-run", /not run/i],
      ["queued", /queued/i],
      ["running", /running/i],
      ["failed", /failed/i],
      ["stopped", /stopped/i],
    ];
    for (const [state, word] of states) {
      const api = courseApi({
        steps: {
          c01: courseStep("c01", {
            runs: [courseRun({ run: "base-06", state, attempt_id: "course-c01-base-06-1" })],
          }),
        },
      });
      const { unmount } = await showStep(api, "c01");
      expect(norm((await findRunRow("base-06")).textContent), state).toMatch(word);
      unmount();
    }
  });

  it("AC12.5.4 links to the Training page while a run runs, and only then", async () => {
    const running = courseApi({
      steps: {
        c20: courseStep("c20", {
          runs: [
            courseRun({
              run: "lora",
              command: "train",
              state: "running",
              attempt_id: "course-c20-lora-1",
            }),
            courseRun({
              run: "qlora",
              command: "train",
              state: "queued",
              attempt_id: "course-c20-qlora-1",
            }),
          ],
        }),
      },
    });
    const first = await showStep(running, "c20");
    const link = await within(await findRunRow("lora")).findByRole("link", {
      name: "Watch it on the Training page",
    });
    expect(link).toHaveAttribute("href", "/training");
    expect(
      within(runRow("qlora")).queryByRole("link", { name: "Watch it on the Training page" }),
    ).toBeNull();
    first.unmount();

    const idle = courseApi({
      steps: {
        c01: courseStep("c01", {
          runs: [
            courseRun({ run: "base-06", state: "failed", attempt_id: "course-c01-base-06-1" }),
          ],
        }),
      },
    });
    await showStep(idle, "c01");
    await findRunRow("base-06");
    expect(screen.queryByRole("link", { name: "Watch it on the Training page" })).toBeNull();
  });

  it("AC12.5.4 says which run holds the GPU, and that the step's runs wait in the queue, when another run holds it", async () => {
    const api = courseApi({
      status: serviceStatus({
        status: "RUNNING",
        run_id: HELD_BY_OTHER,
        started_at: "2026-11-16T20:10:00Z",
      }),
    });
    await showStep(api, "c01");
    await waitFor(() => expectText(HELD_BY_OTHER));
    expect(norm(document.body.textContent)).toMatch(/wait.*queue/i);
  });

  it("AC12.5.4 a 409 course_busy answer shows its message", async () => {
    const user = userEvent.setup();
    const message = "A run of this step is already queued or running.";
    const api = courseApi({
      extra: {
        runCourseStep: async () => {
          throw apiError("course_busy", message);
        },
      },
    });
    await showStep(api, "c01");
    await user.click(await screen.findByRole("button", { name: "Run this step" }));
    await waitFor(() => expectText(message));
  });

  it("AC12.5.4 a finished run shows its accuracy on 100 problems with its interval and minutes", async () => {
    const api = courseApi({
      steps: {
        c01: courseStep("c01", {
          runs: [
            courseRun({
              run: "base-06",
              state: "finished",
              attempt_id: "course-c01-base-06-1",
              accuracy: 0.41,
              interval_low: 0.32,
              interval_high: 0.5,
              minutes: 7,
              value: 0.41,
              metric: "accuracy",
            }),
          ],
        }),
      },
    });
    await showStep(api, "c01");
    const text = norm((await findRunRow("base-06")).textContent);
    expect(text).toMatch(/100 problems/);
    expect(text).toMatch(/\b41(\.0)?\b/);
    expect(text).toMatch(/\b32(\.0)?\b/);
    expect(text).toMatch(/\b50(\.0)?\b/);
    expect(text).toMatch(/\b7 min/);
    expect(text).toMatch(/finished|done/i);
  });

  it("AC12.5.4 refreshes the step every 3 seconds while one of its runs is queued or running", async () => {
    fakeTimers();
    let state: CourseRun["state"] = "running";
    const api = fakeApi({
      getCourse: async () => courseOverview(),
      getCourseStep: async (id: string) =>
        id === "c01"
          ? courseStep("c01", {
              runs: [courseRun({ run: "base-06", state, attempt_id: "course-c01-base-06-1" })],
            })
          : courseStep(id),
    });
    renderPage("/course?step=c01", { api });
    await settle();
    const first = stepCalls(api, "c01");
    expect(first).toBeGreaterThan(0);
    await advance(2800);
    expect(stepCalls(api, "c01")).toBe(first);
    await advance(200);
    await settle();
    const second = stepCalls(api, "c01");
    expect(second).toBeGreaterThan(first);
    await advance(3000);
    await settle();
    const third = stepCalls(api, "c01");
    expect(third).toBeGreaterThan(second);

    state = "finished";
    await advance(3000);
    await settle();
    const afterFinish = stepCalls(api, "c01");
    expect(afterFinish).toBeGreaterThan(third);
    await advance(12000);
    await settle();
    expect(stepCalls(api, "c01")).toBe(afterFinish);
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.5 the inspect steps
// ---------------------------------------------------------------------------------------------

describe("AC12.5.5 the inspect steps", () => {
  const MODELS = courseArchitectures().models.map((model, i) => ({
    ...model,
    problem_tokens: 41 + i,
    prompt_tokens: 640 + 11 * i,
  }));
  const ARCH = { ...courseArchitectures(), models: MODELS };

  function inspectApi(stepId: string, withData = true): FakeApi {
    return courseApi({
      steps: { [stepId]: courseStep(stepId, { architectures: withData ? ARCH : null }) },
    });
  }

  it("AC12.5.5 c02 shows the sample's first tokens as separate chips and the token counts per model", async () => {
    await showStep(inspectApi("c02"), "c02");
    await waitFor(() =>
      expect(document.querySelectorAll("[data-token-chip]").length).toBeGreaterThanOrEqual(8),
    );
    const chips = [...document.querySelectorAll("[data-token-chip]")].map((c) =>
      norm(c.textContent),
    );
    expect(chips).toContain("Jan");
    expect(chips).toContain("ducks");
    MODELS.forEach((model) => {
      const block = document.querySelector<HTMLElement>(`[data-model="${model.id}"]`);
      expect(block, `block of ${model.id}`).not.toBeNull();
      const text = norm(block?.textContent);
      expect(hasToken(text, String(model.problem_tokens)), `problem tokens of ${model.id}`).toBe(
        true,
      );
      expect(hasToken(text, String(model.prompt_tokens)), `prompt tokens of ${model.id}`).toBe(
        true,
      );
    });
  });

  it("AC12.5.5 c03 shows Qwen3-0.6B's weights by part as a stacked bar and a table", async () => {
    await showStep(inspectApi("c03"), "c03");
    await waitFor(() =>
      expect(document.querySelector('[data-bar="weights-by-part"]')).not.toBeNull(),
    );
    expect(document.querySelectorAll("[data-bar]")).toHaveLength(1);
    for (const part of ["embeddings", "attention", "mlp"]) {
      expect(
        document.querySelector(`[data-bar="weights-by-part"] [data-segment="${part}"]`),
        `segment ${part}`,
      ).not.toBeNull();
    }
    const table = screen.getByRole("table");
    const text = norm(table.textContent);
    expect(text).toMatch(/embeddings/i);
    expect(text).toMatch(/attention/i);
    expect(text).toMatch(/MLP/i);
    expect(text).toMatch(/norms/i);
    expect(text).toMatch(/head/i);
    expect(text).toMatch(/155[.,]\d/);
    expect(text).toMatch(/176[.,]\d/);
    expect(text).toMatch(/264[.,]\d/);
    expect(text).toMatch(/596[.,]\d/);
  });

  it("AC12.5.5 c04 shows the course models side by side in a table with every field", async () => {
    const models = [...MODELS];
    models[0] = {
      ...models[0],
      heads: 4,
      kv_heads: 4,
      attention: "multi-head",
      mlp_matrices: 2,
      tied_embeddings: false,
      activation: "gelu",
    };
    const api = courseApi({
      steps: { c04: courseStep("c04", { architectures: { ...ARCH, models } }) },
    });
    await showStep(api, "c04");
    const table = await screen.findByRole("table");
    const text = norm(table.textContent);
    for (const model of models) expect(text, model.id).toContain(model.id);
    for (const family of ["gpt_neox", "llama", "qwen2", "qwen3"]) expect(text).toContain(family);
    for (const word of ["Apache-2.0", "grouped-query", "multi-head", "rotary", "silu", "gelu"]) {
      expect(text, word).toContain(word);
    }
    expect(text).toMatch(/c1899de/);
    for (const token of ["28", "1024", "3072", "128", "4"])
      expect(hasToken(text, token)).toBe(true);
    expect(text).toMatch(/151,?936/);
    expect(text).toMatch(/32,?768/);
    expect(text).toMatch(/1\.19/);
    const labels = [
      /layers/i,
      /width/i,
      /heads/i,
      /key-value|kv/i,
      /head size/i,
      /MLP/i,
      /vocab/i,
      /context/i,
      /tied/i,
      /position/i,
      /activation/i,
      /licen[cs]e/i,
      /bf16/i,
      /4-bit/i,
      /embeddings/i,
      /tokens/i,
    ];
    for (const label of labels) expect(text, String(label)).toMatch(label);
  });

  it("AC12.5.5 before architectures.json exists the run area offers 'Read the model designs (CPU, under a minute)'", async () => {
    const user = userEvent.setup();
    const api = inspectApi("c02", false);
    await showStep(api, "c02");
    const button = await screen.findByRole("button", {
      name: "Read the model designs (CPU, under a minute)",
    });
    await user.click(button);
    await waitFor(() => expect(api.runCourseStep).toHaveBeenCalledWith("c02"));
    expect(document.querySelector("[data-token-chip]")).toBeNull();
  });

  it("AC12.5.5 once architectures.json exists the run area no longer offers to read the designs", async () => {
    await showStep(inspectApi("c04"), "c04");
    await screen.findByRole("table");
    expect(
      screen.queryByRole("button", { name: "Read the model designs (CPU, under a minute)" }),
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.6 the lab steps
// ---------------------------------------------------------------------------------------------

describe("AC12.5.6 the lab steps", () => {
  it("AC12.5.6 shows the lesson's title, question and state and a link to the lesson in the Lab", async () => {
    const lesson = LAB_LESSONS[0];
    const api = courseApi({
      steps: {
        c07: courseStep("c07", {
          lesson: {
            id: "l01",
            number: 1,
            title: lesson.title,
            question: lesson.question,
            state: "running",
          },
        }),
      },
    });
    const { article } = await showStep(api, "c07");
    await waitFor(() => expectText(lesson.question, article));
    expectText(lesson.title, article);
    expect(norm(article.textContent)).toMatch(/running/i);
    const link = within(article).getByRole("link", { name: "Open lesson 1 in the Lab" });
    expect(link).toHaveAttribute("href", "/lab?lesson=l01");
  });

  it("AC12.5.6 links lesson 2 to /lab?lesson=l02 and following the link opens the Lab", async () => {
    const user = userEvent.setup();
    const { router } = await showStep(courseApi(), "c08");
    await user.click(await screen.findByRole("link", { name: "Open lesson 2 in the Lab" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/lab"));
    expect(new URLSearchParams(router.state.location.search).get("lesson")).toBe("l02");
  });

  it("AC12.5.6 shows the questions once the lesson is finished (the run part is done)", async () => {
    const base = courseStep("c07");
    const api = courseApi({
      steps: {
        c07: courseStep("c07", {
          step: { ...base.step, run_done: true, state: "in-progress" },
          lesson: base.lesson ? { ...base.lesson, state: "finished" } : null,
        }),
      },
    });
    await showStep(api, "c07");
    expect(await screen.findAllByRole("radio")).not.toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.7 the quiz
// ---------------------------------------------------------------------------------------------

describe("AC12.5.7 the quiz", () => {
  it("AC12.5.7 'Check my answers' sends the chosen options and shows Right or Not quite, the right option and the explanation", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06");
    await showStep(api, "c06");
    await choose(user, "c06", [0, 1]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await waitFor(() => expect(api.submitCourseQuiz).toHaveBeenCalledWith("c06", [0, 1]));

    const [q1, q2] = courseStep("c06").questions;
    const first = groupFor(q1.prompt);
    const second = groupFor(q2.prompt);
    await waitFor(() => expect(within(first).getAllByText(/^Right\b/)).not.toHaveLength(0));
    expect(within(second).getAllByText(/^Not quite/)).not.toHaveLength(0);
    expect(within(first).queryByText(/^Not quite/)).toBeNull();
    expectText(EXPLANATIONS[0], first);
    expectText(EXPLANATIONS[1], second);
    const rightOfSecond = second.querySelector("[data-right-option]");
    expect(rightOfSecond, "the right option of question 2 is marked").not.toBeNull();
    expect(norm(rightOfSecond?.textContent)).toContain("Choice C");
    expect(norm(first.querySelector("[data-right-option]")?.textContent)).toContain("Option one");
    expectNoText("Quiz passed");
  });

  it("AC12.5.7 'Try again' clears the choices after a wrong answer", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06");
    await showStep(api, "c06");
    await choose(user, "c06", [0, 1]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => expectNoText("Not quite"));
    for (const radio of screen.getAllByRole("radio")) expect(radio).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Check my answers" })).toBeInTheDocument();
  });

  it("AC12.5.7 with every answer right the step reads Quiz passed", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06");
    await showStep(api, "c06");
    await choose(user, "c06", [0, 2]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await waitFor(() => expectText("Quiz passed"));
    expect(api.submitCourseQuiz).toHaveBeenCalledWith("c06", [0, 2]);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("AC12.5.7 the step reads Done once its run part is done and its quiz passed", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06");
    const { article } = await showStep(api, "c06");
    expect(hasWord(article, "Done")).toBe(false);
    await choose(user, "c06", [0, 2]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await waitFor(() => expect(hasWord(article, "Done")).toBe(true));
  });

  it("AC12.5.7 a passed quiz without a finished run part does not read Done", async () => {
    const user = userEvent.setup();
    const api = quizApi("c01");
    const { article } = await showStep(api, "c01");
    await user.click(
      await screen.findByRole("button", { name: "I have read this, show the questions" }),
    );
    await choose(user, "c01", [0, 2]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await waitFor(() => expectText("Quiz passed"));
    expect(hasWord(article, "Done")).toBe(false);
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.8 in your own words
// ---------------------------------------------------------------------------------------------

describe("AC12.5.8 in your own words", () => {
  const MODEL_ANSWER = "A model answer that says it in a few plain sentences.";

  it("AC12.5.8 'Save my answer' saves through PUT /course/{step}/own-words and shows 'One way to say it' with the model answer", async () => {
    const user = userEvent.setup();
    const api = courseApi({
      extra: {
        saveCourseOwnWords: async () => ({
          saved_at: "2026-11-16T20:00:00Z",
          model_answer: MODEL_ANSWER,
        }),
      },
    });
    await showStep(api, "c06");
    expectNoText("One way to say it");
    await user.type(await screen.findByRole("textbox"), "The base model has not seen the format.");
    await user.click(screen.getByRole("button", { name: "Save my answer" }));
    await waitFor(() =>
      expect(api.saveCourseOwnWords).toHaveBeenCalledWith(
        "c06",
        "The base model has not seen the format.",
      ),
    );
    await waitFor(() => expectText("One way to say it"));
    expectText(MODEL_ANSWER);
    const label = elementsWithText("One way to say it")[0];
    expect(follows(screen.getByRole("textbox"), label)).toBe(true);
  });

  it("AC12.5.8 a saved answer is shown again when the step is opened and can be changed", async () => {
    const user = userEvent.setup();
    const base = courseStep("c06");
    const api = courseApi({
      steps: {
        c06: courseStep("c06", { own_words: "My first answer.", model_answer: MODEL_ANSWER }),
      },
      extra: {
        saveCourseOwnWords: async () => ({
          saved_at: "2026-11-16T20:05:00Z",
          model_answer: MODEL_ANSWER,
        }),
      },
    });
    await showStep(api, "c06");
    const box = await screen.findByRole("textbox");
    expect(box).toHaveValue("My first answer.");
    expectText("One way to say it");
    expectText(MODEL_ANSWER);
    expectText(base.own_words_prompt);
    await user.clear(box);
    await user.type(box, "My changed answer.");
    await user.click(screen.getByRole("button", { name: "Save my answer" }));
    await waitFor(() =>
      expect(api.saveCourseOwnWords).toHaveBeenCalledWith("c06", "My changed answer."),
    );
  });

  it("AC12.5.8 a 422 invalid_text answer shows its message", async () => {
    const user = userEvent.setup();
    const message = "The answer must be 1 to 4,000 characters.";
    const api = courseApi({
      extra: {
        saveCourseOwnWords: async () => {
          throw apiError("invalid_text", message);
        },
      },
    });
    await showStep(api, "c06");
    await user.type(await screen.findByRole("textbox"), "x");
    await user.click(screen.getByRole("button", { name: "Save my answer" }));
    await waitFor(() => expectText(message));
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.9 c19 memory table and c24 comparison
// ---------------------------------------------------------------------------------------------

describe("AC12.5.9 c19 and c24", () => {
  const MEMORY: CourseMemoryRow[] = [
    {
      model: "EleutherAI/pythia-31m",
      full_gb: 0.5,
      lora_gb: 0.1,
      qlora_gb: 0.1,
      full_fits: true,
      lora_fits: true,
      qlora_fits: true,
    },
    {
      model: Q06,
      full_gb: 9.6,
      lora_gb: 2.1,
      qlora_gb: 1.4,
      full_fits: false,
      lora_fits: true,
      qlora_fits: true,
    },
  ];

  it("AC12.5.9 c19 shows the memory table with 'Fits in 8 GB' or 'Does not fit' in words", async () => {
    const api = courseApi({ steps: { c19: courseStep("c19", { memory: MEMORY }) } });
    await showStep(api, "c19");
    await waitFor(() => tableRow(Q06));
    const big = tableRow(Q06);
    expect(within(big).getAllByText(/Fits in 8 GB/)).toHaveLength(2);
    expect(within(big).getAllByText(/Does not fit/)).toHaveLength(1);
    const text = norm(big.textContent);
    expect(text).toMatch(/9\.6/);
    expect(text).toMatch(/2\.1/);
    expect(text).toMatch(/1\.4/);
    const small = tableRow("EleutherAI/pythia-31m");
    expect(within(small).getAllByText(/Fits in 8 GB/)).toHaveLength(3);
    expect(within(small).queryByText(/Does not fit/)).toBeNull();
  });

  it("AC12.5.9 c19 with no figures yet says neither Fits nor Does not fit", async () => {
    await showStep(courseApi(), "c19");
    await waitFor(() => tableRow(Q06));
    expectNoText("Fits in 8 GB");
    expectNoText("Does not fit");
  });

  const COMPARISON: CourseComparisonRow[] = [
    {
      step: "c01",
      run: "base-06",
      attempt_id: "course-c01-base-06-1",
      model: Q06,
      method: "base",
      accuracy: 0.41,
      interval_low: 0.32,
      interval_high: 0.5,
      gain_pts: null,
      noise: null,
      minutes: 7,
    },
    {
      step: "c21",
      run: "sft",
      attempt_id: "course-c21-sft-1",
      model: Q06,
      method: "sft",
      accuracy: 0.47,
      interval_low: 0.38,
      interval_high: 0.56,
      gain_pts: 6,
      noise: "within noise",
      minutes: 12,
    },
  ];

  it("AC12.5.9 c24 draws each interval as a bar and shows its numbers in the table", async () => {
    const api = courseApi({ steps: { c24: courseStep("c24", { comparison: COMPARISON }) } });
    await showStep(api, "c24");
    await waitFor(() => tableRow(/c21/));
    const base = tableRow(/c01/);
    const sft = tableRow(/c21/);
    expect(base.querySelectorAll("[data-interval-bar]")).toHaveLength(1);
    expect(sft.querySelectorAll("[data-interval-bar]")).toHaveLength(1);
    const baseText = norm(base.textContent);
    expect(baseText).toMatch(/\b41(\.0)?\b/);
    expect(baseText).toMatch(/\b32(\.0)?\b/);
    expect(baseText).toMatch(/\b50(\.0)?\b/);
    expect(baseText).toMatch(/\b7\b/);
    const sftText = norm(sft.textContent);
    expect(sftText).toMatch(/\b47(\.0)?\b/);
    expect(sftText).toMatch(/\b38(\.0)?\b/);
    expect(sftText).toMatch(/\b56(\.0)?\b/);
    expect(sftText).toMatch(/\b12\b/);
  });

  it("AC12.5.9 c24 marks a gain inside the noise with 'within noise'", async () => {
    const api = courseApi({ steps: { c24: courseStep("c24", { comparison: COMPARISON }) } });
    await showStep(api, "c24");
    await waitFor(() => tableRow(/c21/));
    expect(norm(tableRow(/c21/).textContent)).toContain("within noise");
    expect(norm(tableRow(/c01/).textContent)).not.toContain("within noise");
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.10 the landing page's "Your course" card
// ---------------------------------------------------------------------------------------------

describe("AC12.5.10 the landing card", () => {
  const DESCRIPTION = "Teaching small open models grade-school math, one measured run at a time.";

  function landingApi(): FakeApi {
    return courseApi({
      overview: courseOverview({ steps: doneSteps(7), first_try_right: 9, questions_answered: 12 }),
    });
  }

  async function findCard(): Promise<HTMLElement> {
    return waitFor(() => {
      const el = elementsWithText("Your course")[0];
      if (!el) throw new Error("no Your course card");
      return el;
    });
  }

  it("AC12.5.10 shows a 'Your course' card with the progress line and a Continue the course link", async () => {
    renderPage("/", { api: landingApi() });
    await findCard();
    await waitFor(() => expectText("Your progress: 7 of 24 steps done (29 %)"));
    const link = screen.getByRole("link", { name: "Continue the course" });
    expect(link.getAttribute("href")).toMatch(/^\/course/);
  });

  it("AC12.5.10 the card is its own block after the buttons block, outside the headline section", async () => {
    renderPage("/", { api: landingApi() });
    const heading = await findCard();
    const main = document.querySelector("main#main");
    const root = main?.firstElementChild as Element;
    expect(classesOf(root)).toContain("min-h-[calc(100svh-3.5rem)]");
    const section = document.querySelector<HTMLElement>("main [data-motion]") as HTMLElement;
    expect(section).not.toBeNull();
    expect(section).toHaveAttribute("data-align", "center");
    expect(classesOf(section)).toContain("flex-1");
    expect(section.contains(heading)).toBe(false);

    const block = [...root.children].find((child) => child.contains(heading));
    expect(block, "the card sits inside the window-height container").toBeDefined();
    expect(block).not.toBe(section);
    expect(block?.contains(screen.getByText(DESCRIPTION))).toBe(false);
    expect(follows(screen.getByRole("link", { name: "See scores" }), heading)).toBe(true);
    const classes = classesOf(block as Element);
    expect(classes).toContain(GUTTER);
    expect(classes.filter((c) => c.startsWith("max-w-"))).toEqual([]);
  });

  it("AC12.5.10 when the overview fails the card shows the error's message and the rest of the page renders", async () => {
    const message = "The course progress could not be read.";
    const api = courseApi({
      extra: {
        getCourse: async () => {
          throw new ApiError(500, "progress_unreadable", message, "outputs/course/progress.json");
        },
      },
    });
    renderPage("/", { api });
    await waitFor(() => expectText(message));
    expect(await screen.findByRole("heading", { level: 1, name: "gsm8k" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to training" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See scores" })).toBeInTheDocument();
    expectText(DESCRIPTION);
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.11 loading, errors, keyboard
// ---------------------------------------------------------------------------------------------

describe("AC12.5.11 loading, errors and keyboard", () => {
  it("AC12.5.11 shows 'Reading the course…' while the overview loads", async () => {
    const api = courseApi({
      extra: { getCourse: () => new Promise<CourseOverview>(() => {}) },
    });
    renderPage("/course", { api });
    expect(await screen.findByText("Reading the course…")).toBeInTheDocument();
  });

  it("AC12.5.11 shows the error's message with a 'Try again' button that reads the overview again", async () => {
    const user = userEvent.setup();
    let calls = 0;
    const api = courseApi({
      extra: {
        getCourse: async () => {
          calls += 1;
          if (calls === 1)
            throw new ApiError(0, "unreachable", "The run service is not reachable.");
          return courseOverview();
        },
      },
    });
    renderPage("/course", { api });
    await waitFor(() => expectText("The run service is not reachable."));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => stepItem(1));
    expect(api.getCourse).toHaveBeenCalledTimes(2);
    expectText("Your progress: 0 of 24 steps done (0 %)");
  });

  it("AC12.5.11 a step that fails to load shows the error's message with a 'Try again' button", async () => {
    const user = userEvent.setup();
    let calls = 0;
    const message = "Step c03 could not be read.";
    const api = courseApi({
      extra: {
        getCourseStep: async (id: string) => {
          if (id === "c03") {
            calls += 1;
            if (calls === 1) throw apiError("internal", message);
          }
          return courseStep(id);
        },
      },
    });
    renderPage("/course?step=c03", { api });
    await waitFor(() => expectText(message));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(document.querySelector('[data-step="c03"]')).not.toBeNull());
    expect(calls).toBe(2);
  });

  it("AC12.5.11 the Continue button is reached with Tab and works with Enter", async () => {
    const user = userEvent.setup();
    const api = courseApi({ overview: courseOverview({ steps: doneSteps(7) }) });
    renderPage("/course?step=c01", { api });
    const button = await screen.findByRole("button", {
      name: "Continue with step 8: Learning rate",
    });
    document.body.focus();
    for (let i = 0; i < 80 && document.activeElement !== button; i += 1) await user.tab();
    expect(document.activeElement).toBe(button);
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.openCourseStep).toHaveBeenCalledWith("c08"));
  });

  it("AC12.5.11 a step in the list is reached with Tab and chosen with Enter", async () => {
    const user = userEvent.setup();
    const api = courseApi();
    const { router } = renderPage("/course?step=c01", { api });
    await waitFor(() => stepItem(3));
    const control = controlIn(stepItem(3));
    expect(["BUTTON", "A"]).toContain(control.tagName);
    document.body.focus();
    for (let i = 0; i < 120 && document.activeElement !== control; i += 1) await user.tab();
    expect(document.activeElement).toBe(control);
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(new URLSearchParams(router.state.location.search).get("step")).toBe("c03"),
    );
  });

  it("AC12.5.11 the quiz is answered with the keyboard", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06");
    await showStep(api, "c06");
    const [q1] = courseStep("c06").questions;
    const radios = within(groupFor(q1.prompt)).getAllByRole("radio");
    expect(radios[0].tagName).toBe("INPUT");
    radios[0].focus();
    await user.keyboard(" ");
    expect(radios[0]).toBeChecked();
    const second = within(groupFor(courseStep("c06").questions[1].prompt)).getAllByRole("radio");
    second[2].focus();
    await user.keyboard(" ");
    const check = screen.getByRole("button", { name: "Check my answers" });
    check.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.submitCourseQuiz).toHaveBeenCalledWith("c06", [0, 2]));
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.5.13 full width and prose line length
// ---------------------------------------------------------------------------------------------

describe("AC12.5.13 full width", () => {
  it("AC12.5.13 the container spans the window less the gutter and sets no maximum width", async () => {
    await showStep(courseApi(), "c01");
    const main = document.querySelector("main#main");
    const container = main?.firstElementChild as Element;
    expect(container).not.toBeNull();
    const classes = classesOf(container);
    expect(classes).toContain(GUTTER);
    expect(classes.filter((c) => c.startsWith("max-w-"))).toEqual([]);
    for (const el of document.querySelectorAll("[class]")) {
      for (const cap of ["max-w-[1280px]", "max-w-[var(--content-width)]"]) {
        expect(classesOf(el)).not.toContain(cap);
      }
    }
  });

  it("AC12.5.13 the step's prose keeps at most 75 characters per line", async () => {
    const user = userEvent.setup();
    const api = quizApi("c06", { own_words: "My answer.", model_answer: "The model's answer." });
    const { article } = await showStep(api, "c06");
    await choose(user, "c06", [0, 1]);
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    await waitFor(() => expectText(EXPLANATIONS[1]));
    const prose = [
      elementsWithText(`Why ${stepTitle("c06")} comes now.`, article)[0],
      elementsWithText("A second paragraph.", article)[0],
      elementsWithText(EXPLANATIONS[0], article)[0],
      elementsWithText(EXPLANATIONS[1], article)[0],
      elementsWithText("The model's answer.", article)[0],
    ];
    prose.forEach((el, i) => {
      expect(el, `prose element ${i}`).toBeDefined();
      expect(hasProseCap(el), `prose element ${i} carries ${PROSE_CAP}`).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------------------------
// AC12.3.8 (web side) the Training page marks course runs
// ---------------------------------------------------------------------------------------------

describe("AC12.3.8 the Training page's past runs mark course runs", () => {
  async function pastRunRow(runId: string): Promise<HTMLElement> {
    return waitFor(() => {
      const row = screen
        .getAllByText(runId)
        .map((el) => el.closest("tr"))
        .find((tr): tr is HTMLTableRowElement => tr !== null);
      if (!row) throw new Error(`no table row for ${runId}`);
      return row;
    });
  }

  function pastApi(courseRunFields: Partial<ReturnType<typeof run>>): FakeApi {
    return fakeApi({
      listRuns: async () => ({
        runs: [
          run({
            run_id: "course-c01-base-06-1",
            method: "base",
            dev_accuracy: null,
            minutes: null,
            date: null,
            started_at: "2026-11-16T10:00:00Z",
            status: "finished",
            ...courseRunFields,
          }),
          run({
            run_id: "q06-sft-dev-2",
            dev_accuracy: 0.47,
            minutes: 23,
            started_at: "2026-11-04T20:10:00Z",
            status: "finished",
          }),
        ],
        skipped_rows: 0,
      }),
    });
  }

  it("AC12.3.8 marks a run whose id starts with course- as Course and shows its status", async () => {
    renderPage("/training", { api: pastApi({}) });
    const row = await pastRunRow("course-c01-base-06-1");
    expect(within(row).getByText("Course")).toBeInTheDocument();
    expect(within(row).getByText("FINISHED")).toBeInTheDocument();
    const other = await pastRunRow("q06-sft-dev-2");
    expect(within(other).queryByText("Course")).toBeNull();
    expect(within(other).getByText("47.0%")).toBeInTheDocument();
  });

  it("AC12.3.8 shows no accuracy or minutes for a course run", async () => {
    renderPage("/training", {
      api: pastApi({ dev_accuracy: 0.41, minutes: 9, date: "2026-11-16T10:09:00Z" }),
    });
    const row = await pastRunRow("course-c01-base-06-1");
    expect(within(row).getByText("Course")).toBeInTheDocument();
    expect(within(row).queryByText("41.0%")).toBeNull();
    expect(within(row).queryByText("9")).toBeNull();
  });
});
