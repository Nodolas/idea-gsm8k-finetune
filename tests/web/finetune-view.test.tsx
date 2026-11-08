/**
 * Batch-7 (u5-website): the fine-tuning view of the training page, US4.7 (AC4.7.1-AC4.7.8;
 * AC4.7.9 is [manual]). The page reads only the fake Api: `getStatus`, `listRuns`, `getRun` (the
 * run's settings) and `getMetrics` (a run that is not live), plus C7 events pushed with
 * `api.stream.*`. The drawing is decorative (`aria-hidden`), so the tests read the panel's text
 * and its `data-*` markers, which construction/batch-7.md lists.
 */
import type { MetricsLine, Run, RunConfig, Status } from "@/lib/api";
import { fakeApi, metricsLine, Q06, Q17, run, serviceStatus, type FakeApi } from "@/test/fake-api";
import { act, fireEvent, renderPage, screen, userEvent, waitFor } from "@/test/utils";

const LIVE = "q17-selfcot-dev-1";
const PAST = "q06-sft-dev-1";

/** The settings of a run folder; defaults to a 1.7B fine-tune at rank 16 and batch size 4. */
function config(partial: RunConfig = {}): RunConfig {
  return {
    model: Q17,
    method: "sft",
    learning_rate: 2e-4,
    epochs: 1,
    lora_rank: 16,
    lora_alpha: 32,
    batch_size: 4,
    ...partial,
  };
}

function running(runId: string = LIVE): Status {
  return serviceStatus({ status: "RUNNING", run_id: runId, started_at: "2026-11-08T16:50:00Z" });
}

function activeRun(runId: string, method: string, model: string): Run {
  return run({
    run_id: runId,
    model,
    method,
    dev_accuracy: null,
    minutes: null,
    date: null,
    started_at: "2026-11-08T16:50:00Z",
    status: "running",
  });
}

interface LiveOptions {
  runId?: string;
  method?: string;
  model?: string;
  settings?: RunConfig;
}

/** A fake Api whose service reports one active run of `method` on `model`. */
function liveApi({
  runId = LIVE,
  method = "sft",
  model = Q17,
  settings = {},
}: LiveOptions = {}): FakeApi {
  return fakeApi({
    getStatus: async () => running(runId),
    listRuns: async () => ({ runs: [activeRun(runId, method, model)], skipped_rows: 0 }),
    getRun: async (id: string) => ({
      run_id: id,
      config: config({ model, method, ...settings }),
      status: {},
      timings: {},
    }),
  });
}

/** Four lines of a supervised run: three step lines, then a dev evaluation at step 120. */
const STEP_LINES: MetricsLine[] = [
  metricsLine({
    step: 40,
    total_steps: 400,
    loss: 1.8,
    learning_rate: 2e-4,
    grad_norm: 0.9,
    elapsed_s: 380,
    eta_s: 3420,
  }),
  metricsLine({
    step: 80,
    total_steps: 400,
    loss: 1.1,
    learning_rate: 1.9e-4,
    grad_norm: 0.61,
    elapsed_s: 760,
    eta_s: 3040,
  }),
  metricsLine({
    step: 120,
    total_steps: 400,
    loss: 0.94,
    learning_rate: 1.8e-4,
    grad_norm: 0.42,
    elapsed_s: 1140,
    eta_s: 2640,
  }),
  metricsLine({
    step: 120,
    total_steps: 400,
    loss: null,
    learning_rate: null,
    dev_accuracy: 0.47,
    elapsed_s: 1150,
    eta_s: 2640,
  }),
];

function sendLines(api: FakeApi, lines: MetricsLine[], runId: string = LIVE, from = 1) {
  lines.forEach((line, i) => api.stream.metric({ ...line, run_id: runId }, from + i));
}

interface OpenOptions {
  status?: Status;
  reducedMotion?: boolean;
}

/** Renders /training, waits for its stream, and sends `status` as the stream would. */
async function openTraining(api: FakeApi, { status, reducedMotion }: OpenOptions = {}) {
  const result = renderPage("/training", { api, reducedMotion });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  if (status) api.stream.status(status);
  return result;
}

/** The fine-tuning panel: the region named "How the model is fine-tuned". */
async function panel(): Promise<HTMLElement> {
  return screen.findByRole("region", { name: "How the model is fine-tuned" });
}

/** The panel's root as it is now (`data-mode`, `data-view`, `data-step`, `data-motion`). */
function root(): HTMLElement {
  const el = document.querySelector<HTMLElement>("main [data-mode]");
  if (!el) throw new Error("the fine-tuning panel is not on the page");
  return el;
}

/** One `data-part` of the panel, or null. */
function part(name: string): HTMLElement | null {
  return root().querySelector<HTMLElement>(`[data-part="${name}"]`);
}

function stage(name: string): HTMLElement {
  const el = root().querySelector<HTMLElement>(`[data-stage="${name}"]`);
  if (!el) throw new Error(`no stage ${name}`);
  return el;
}

function stat(name: string): HTMLElement {
  const el = root().querySelector<HTMLElement>(`[data-stat="${name}"]`);
  if (!el) throw new Error(`no figure ${name}`);
  return el;
}

function layers(): NodeListOf<Element> {
  return root().querySelectorAll("[data-layer]");
}

function trainedAdapters(): NodeListOf<Element> {
  return root().querySelectorAll('[data-adapter][data-state="trained"]');
}

/** Waits until the panel shows the step line `step` and returns the panel root. */
async function shownStep(step: number): Promise<HTMLElement> {
  await waitFor(() => expect(root()).toHaveAttribute("data-step", String(step)));
  return root();
}

/** The ended fine-tune `PAST` (0.6B) with its lines in the run folder, nothing active. */
function endedApi(lines: MetricsLine[] = STEP_LINES): FakeApi {
  return fakeApi({
    getStatus: async () =>
      serviceStatus({
        status: "IDLE",
        last_run: serviceStatus({ status: "FINISHED", run_id: PAST }),
      }),
    listRuns: async () => ({
      runs: [run({ run_id: PAST, model: Q06, method: "sft", status: "finished" })],
      skipped_rows: 0,
    }),
    getRun: async (id: string) => ({
      run_id: id,
      config: config({ model: Q06, method: "sft" }),
      status: {},
      timings: {},
    }),
    getMetrics: async () => ({ lines, next: lines.length }),
  });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("fine-tuning view: what is frozen and what is trained (AC4.7.1)", () => {
  it("AC4.7.1 draws 28 frozen layers with a trained LoRA adapter on each, and the 1.7B weight counts at rank 16", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 1));

    const region = await panel();
    expect(region).toBeInTheDocument();
    await waitFor(() => expect(part("weights")).not.toBeNull());
    expect(root()).toHaveAttribute("data-mode", "finetune");
    expect(layers()).toHaveLength(28);
    for (const layer of layers()) expect(layer).toHaveAttribute("data-state", "frozen");
    expect(trainedAdapters()).toHaveLength(28);

    const weights = part("weights");
    expect(weights).toHaveTextContent("17,432,576 trained");
    expect(weights).toHaveTextContent("1,720,574,976 frozen");
    expect(weights).toHaveTextContent("1,738,007,552 weights");
    expect(weights).toHaveTextContent("1.0%");
  });

  it("AC4.7.1 reads the 0.6B weight counts at rank 16", async () => {
    const api = liveApi({ runId: "q06-sft-dev-3", model: Q06 });
    await openTraining(api, { status: running("q06-sft-dev-3") });
    sendLines(api, STEP_LINES.slice(0, 1), "q06-sft-dev-3");

    await panel();
    await waitFor(() => expect(part("weights")).not.toBeNull());
    expect(layers()).toHaveLength(28);
    const weights = part("weights");
    expect(weights).toHaveTextContent("10,092,544 trained");
    expect(weights).toHaveTextContent("596,049,920 frozen");
    expect(weights).toHaveTextContent("1.7%");
  });

  it("AC4.7.1 works the trained weights out from the run's LoRA rank", async () => {
    const api = liveApi({ settings: { lora_rank: 8 } });
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 1));

    await panel();
    await waitFor(() => expect(part("weights")).not.toBeNull());
    const weights = part("weights");
    expect(weights).toHaveTextContent("8,716,288 trained");
    expect(weights).toHaveTextContent("1,720,574,976 frozen");
    expect(weights).toHaveTextContent("1,729,291,264 weights");
    expect(weights).toHaveTextContent("0.5%");
  });

  it("AC4.7.1 treats selfcot, terse, optuna and grpo runs as fine-tunes too", async () => {
    for (const method of ["selfcot", "terse", "optuna", "grpo"]) {
      const runId = `q17-${method}-dev-1`;
      const api = liveApi({ runId, method });
      const { unmount } = await openTraining(api, { status: running(runId) });
      sendLines(api, STEP_LINES.slice(0, 1), runId);

      await panel();
      await waitFor(() => expect(root()).toHaveAttribute("data-mode", "finetune"));
      expect(trainedAdapters()).toHaveLength(28);
      unmount();
    }
  });
});

describe("fine-tuning view: the five stages of a step (AC4.7.2)", () => {
  it("AC4.7.2 names Read, Guess, Score, Blame and Nudge in order, each with a meaning", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES);

    await panel();
    await shownStep(120);
    const items = [...root().querySelectorAll("[data-stage]")];
    expect(items.map((el) => el.getAttribute("data-stage"))).toEqual([
      "read",
      "guess",
      "score",
      "blame",
      "nudge",
    ]);
    expect(items.map((el) => el.querySelector("h3")?.textContent)).toEqual([
      "Read",
      "Guess",
      "Score",
      "Blame",
      "Nudge",
    ]);
    for (const item of items) {
      const meaning = item.querySelector('[data-part="meaning"]')?.textContent ?? "";
      expect(meaning.trim().length).toBeGreaterThan(20);
    }
  });

  it("AC4.7.2 shows the newest step line's figures, ignoring the dev accuracy line", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES);

    await panel();
    await shownStep(120);
    await waitFor(() => expect(stage("read")).toHaveTextContent("4 examples per step"));
    const score = stage("score");
    expect(score).toHaveTextContent("loss 0.94");
    expect(score).toHaveTextContent("39% chance on the right word");
    expect(score).toHaveTextContent("47.8% lower than at step 40");
    expect(stage("blame")).toHaveTextContent("gradient norm 0.42");
    expect(stage("nudge")).toHaveTextContent("learning rate 1.8e-4");
    expect(part("progress")).toHaveTextContent("Step 120 of 400 · 480 examples seen");
  });

  it("AC4.7.2 reads the chance on the right word as e to the power of minus the loss", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, [metricsLine({ step: 5, total_steps: 100, loss: 1.8 })]);

    await panel();
    await shownStep(5);
    expect(stage("score")).toHaveTextContent("17% chance on the right word");
    expect(stage("score")).toHaveTextContent("first logged step");
  });

  it("AC4.7.2 says higher when the loss went up since the first step line", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, [
      metricsLine({ step: 10, total_steps: 100, loss: 1.0 }),
      metricsLine({ step: 20, total_steps: 100, loss: 1.25 }),
    ]);

    await panel();
    await shownStep(20);
    expect(stage("score")).toHaveTextContent("25.0% higher than at step 10");
  });

  it("AC4.7.2 reads a dash for the gradient norm of a line that has none", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, [metricsLine({ step: 7, total_steps: 100, loss: 1.2, grad_norm: null })]);

    await panel();
    await shownStep(7);
    expect(stage("blame")).toHaveTextContent("gradient norm —");
  });

  it("AC4.7.2 reads a dash for the examples per step when the run's settings lack a batch size", async () => {
    const api = liveApi({ settings: { batch_size: undefined } });
    await openTraining(api, { status: running() });
    sendLines(api, [metricsLine({ step: 7, total_steps: 100, loss: 1.2 })]);

    await panel();
    await shownStep(7);
    await waitFor(() => expect(api.getRun).toHaveBeenCalled());
    expect(stage("read")).toHaveTextContent("—");
    expect(part("progress")).toHaveTextContent("Step 7 of 100");
    expect(part("progress")).not.toHaveTextContent("examples seen");
  });
});

describe("fine-tuning view: following a live run (AC4.7.3)", () => {
  it("AC4.7.3 updates the step and the figures when a new line arrives, without a reload", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 2));

    await panel();
    await shownStep(80);
    await waitFor(() => expect(part("progress")).toHaveTextContent("Step 80 of 400"));
    expect(stage("score")).toHaveTextContent("loss 1.1");
    const pass = root().querySelector('[data-part="pass"]');
    expect(pass).toHaveAttribute("data-pass", "80");
    const loads = {
      runs: api.listRuns.mock.calls.length,
      settings: api.getRun.mock.calls.length,
    };

    api.stream.metric({ ...STEP_LINES[2], run_id: LIVE }, 3);

    await shownStep(120);
    expect(part("progress")).toHaveTextContent("Step 120 of 400 · 480 examples seen");
    expect(stage("score")).toHaveTextContent("loss 0.94");
    expect(stage("blame")).toHaveTextContent("gradient norm 0.42");
    // The passes of the drawing start again: a new element for the new step.
    const next = root().querySelector('[data-part="pass"]');
    expect(next).toHaveAttribute("data-pass", "120");
    expect(next).not.toBe(pass);
    // Nothing was fetched again and the stream stayed open once: no reload.
    expect(api.listRuns.mock.calls.length).toBe(loads.runs);
    expect(api.getRun.mock.calls.length).toBe(loads.settings);
    expect(api.stream.openCount).toBe(1);
  });
});

describe("fine-tuning view: one layer up close (AC4.7.4)", () => {
  it("AC4.7.4 names the 1.7B query projection, its adapter matrices and the scale", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 1));

    await panel();
    const figure = await screen.findByRole("figure", { name: "One layer up close" });
    expect(figure).toBeInTheDocument();
    expect(stat("frozen-matrix")).toHaveTextContent("2048 × 2048 = 4,194,304 weights");
    expect(stat("adapter-a")).toHaveTextContent("16 × 2048");
    expect(stat("adapter-b")).toHaveTextContent("2048 × 16");
    expect(stat("adapter-total")).toHaveTextContent("65,536 weights");
    expect(stat("scale")).toHaveTextContent("2 (alpha 32 / rank 16)");
  });

  it("AC4.7.4 works the 0.6B figures out from its shape and the run's settings", async () => {
    const api = liveApi({ runId: "q06-sft-dev-3", model: Q06, settings: { lora_rank: 8 } });
    await openTraining(api, { status: running("q06-sft-dev-3") });
    sendLines(api, STEP_LINES.slice(0, 1), "q06-sft-dev-3");

    await screen.findByRole("figure", { name: "One layer up close" });
    expect(stat("frozen-matrix")).toHaveTextContent("1024 × 2048 = 2,097,152 weights");
    expect(stat("adapter-a")).toHaveTextContent("8 × 1024");
    expect(stat("adapter-b")).toHaveTextContent("2048 × 8");
    expect(stat("adapter-total")).toHaveTextContent("24,576 weights");
    expect(stat("scale")).toHaveTextContent("4 (alpha 32 / rank 8)");
  });
});

describe("fine-tuning view: a run that does not change the model (AC4.7.5)", () => {
  it("AC4.7.5 says a cotgen run does not change the model and counts problems written", async () => {
    const runId = "q17-cotgen-train-1";
    const api = liveApi({ runId, method: "cotgen" });
    await openTraining(api, { status: running(runId) });
    sendLines(
      api,
      [metricsLine({ step: 90, total_steps: 1500, loss: null, learning_rate: null })],
      runId,
    );

    await panel();
    await shownStep(90);
    expect(root()).toHaveAttribute("data-mode", "reading");
    expect(part("reading-note")).toHaveTextContent(/^This run does not change the model/);
    expect(part("reading-note")?.textContent?.trim().length).toBeGreaterThan(60);
    expect(layers()).toHaveLength(28);
    expect(trainedAdapters()).toHaveLength(0);
    expect(part("progress")).toHaveTextContent("90 of 1500 problems written");
    expect(root().querySelectorAll("[data-stage]")).toHaveLength(0);
    expect(root()).not.toHaveTextContent("Score");
    expect(root()).not.toHaveTextContent("Blame");
    expect(root()).not.toHaveTextContent("Nudge");
    expect(part("weights")).toHaveTextContent("None of the 1,720,574,976 weights changes");
  });

  it("AC4.7.5 says an evaluation does not change the model and counts problems scored", async () => {
    const runId = "q17-base-dev-2";
    const api = liveApi({ runId, method: "base" });
    await openTraining(api, { status: running(runId) });
    sendLines(
      api,
      [metricsLine({ step: 300, total_steps: 1000, loss: null, learning_rate: null })],
      runId,
    );

    await panel();
    await shownStep(300);
    expect(root()).toHaveAttribute("data-mode", "reading");
    expect(part("reading-note")).toHaveTextContent(/^This run does not change the model/);
    expect(trainedAdapters()).toHaveLength(0);
    expect(part("progress")).toHaveTextContent("300 of 1000 problems scored");
    expect(root().querySelectorAll("[data-stage]")).toHaveLength(0);
  });

  it("AC4.7.5 says a finalist evaluation does not change the model either", async () => {
    const runId = "q17-best-test-1";
    const api = liveApi({ runId, method: "best" });
    await openTraining(api, { status: running(runId) });
    sendLines(
      api,
      [metricsLine({ step: 10, total_steps: 1319, loss: null, learning_rate: null })],
      runId,
    );

    await panel();
    await shownStep(10);
    expect(root()).toHaveAttribute("data-mode", "reading");
    expect(part("progress")).toHaveTextContent("10 of 1319 problems scored");
    expect(trainedAdapters()).toHaveLength(0);
  });
});

describe("fine-tuning view: empty states (AC4.7.6)", () => {
  it("AC4.7.6 reads Waiting for the first logged step before a fine-tune's first line", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });

    await panel();
    await waitFor(() =>
      expect(part("empty")).toHaveTextContent("Waiting for the first logged step"),
    );
    expect(root().querySelectorAll('[data-part="figure"]')).toHaveLength(0);

    sendLines(api, STEP_LINES.slice(0, 1));
    await shownStep(40);
    expect(part("empty")).toBeNull();
    expect(stage("score")).toHaveTextContent("loss 1.8");
  });

  it("AC4.7.6 reads No step lines were recorded for an ended fine-tune with no step line", async () => {
    const api = endedApi([]);
    await openTraining(api);

    await panel();
    await waitFor(() =>
      expect(part("empty")).toHaveTextContent("No step lines were recorded for this run."),
    );
    expect(root().querySelectorAll('[data-part="figure"]')).toHaveLength(0);
  });

  it("AC4.7.6 reads Nothing to show yet when no run has ever happened", async () => {
    const api = fakeApi();
    await openTraining(api);

    await panel();
    await waitFor(() =>
      expect(part("empty")).toHaveTextContent(
        "Nothing to show yet: start a fine-tune to watch the model change.",
      ),
    );
    expect(root().querySelectorAll("[data-stage]")).toHaveLength(0);
  });
});

describe("fine-tuning view: replay of an ended run (AC4.7.7)", () => {
  it("AC4.7.7 replays the last run after it ended with a slider over its step lines", async () => {
    const api = endedApi();
    await openTraining(api);

    const slider = await screen.findByRole("slider", { name: "Replay step" });
    expect(slider).toHaveAttribute("min", "1");
    expect(slider).toHaveAttribute("max", "3");
    expect(slider).toHaveValue("3");
    expect(root()).toHaveAttribute("data-view", "replay");
    expect(part("view-state")).toHaveTextContent("Replaying step 120 of 400");
    // The 0.6B model of this run: its weight counts follow the run, not a fixed model.
    await waitFor(() => expect(part("weights")).toHaveTextContent("10,092,544 trained"));
  });

  it("AC4.7.7 moving the slider shows that step line's figures", async () => {
    const api = endedApi();
    await openTraining(api);
    const slider = await screen.findByRole("slider", { name: "Replay step" });

    fireEvent.change(slider, { target: { value: "1" } });

    await shownStep(40);
    expect(part("view-state")).toHaveTextContent("Replaying step 40 of 400");
    expect(stage("score")).toHaveTextContent("loss 1.8");
    expect(stage("score")).toHaveTextContent("first logged step");
    expect(stage("blame")).toHaveTextContent("gradient norm 0.9");

    fireEvent.change(slider, { target: { value: "2" } });
    await shownStep(80);
    expect(part("view-state")).toHaveTextContent("Replaying step 80 of 400");
    expect(stage("score")).toHaveTextContent("loss 1.1");
    expect(stage("score")).toHaveTextContent("38.9% lower than at step 40");
  });

  it("AC4.7.7 Play replay steps through the lines to the last one and stops", async () => {
    const api = endedApi();
    await openTraining(api);
    const slider = await screen.findByRole("slider", { name: "Replay step" });
    fireEvent.change(slider, { target: { value: "1" } });
    await shownStep(40);

    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
    expect(screen.getByRole("button", { name: "Pause replay" })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(screen.getByRole("slider", { name: "Replay step" })).toHaveValue("2");
    expect(root()).toHaveAttribute("data-step", "80");

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByRole("slider", { name: "Replay step" })).toHaveValue("3");
    expect(root()).toHaveAttribute("data-step", "120");
    expect(screen.getByRole("button", { name: "Play replay" })).toBeInTheDocument();

    // Pressing Play on the last line starts the replay again from the first.
    fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
    expect(screen.getByRole("slider", { name: "Replay step" })).toHaveValue("1");
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByRole("slider", { name: "Replay step" })).toHaveValue("3");
  });

  it("AC4.7.7 Pause replay stops where it is", async () => {
    const api = endedApi();
    await openTraining(api);
    const slider = await screen.findByRole("slider", { name: "Replay step" });
    fireEvent.change(slider, { target: { value: "1" } });
    await shownStep(40);

    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
    act(() => {
      vi.advanceTimersByTime(150);
    });
    fireEvent.click(screen.getByRole("button", { name: "Pause replay" }));
    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(screen.getByRole("slider", { name: "Replay step" })).toHaveValue("2");
    expect(screen.getByRole("button", { name: "Play replay" })).toBeInTheDocument();
  });

  it("AC4.7.7 a past run opened from Past runs is replayed, and Back to live returns to the live run", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      getStatus: async () => running(),
      listRuns: async () => ({
        runs: [
          activeRun(LIVE, "selfcot", Q17),
          run({ run_id: PAST, model: Q06, method: "sft", status: "finished" }),
        ],
        skipped_rows: 0,
      }),
      getRun: async (id: string) => ({
        run_id: id,
        config: config(id === PAST ? { model: Q06 } : { method: "selfcot" }),
        status: {},
        timings: {},
      }),
      getMetrics: async (id: string) =>
        id === PAST ? { lines: STEP_LINES.slice(0, 3), next: 3 } : { lines: [], next: 0 },
    });
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 2));
    await panel();
    await shownStep(80);
    expect(root()).toHaveAttribute("data-view", "live");
    expect(part("view-state")).toHaveTextContent("Following the live run");
    expect(screen.queryByRole("slider", { name: "Replay step" })).toBeNull();

    await user.click(await screen.findByRole("button", { name: `Open ${PAST}` }));

    await screen.findByRole("slider", { name: "Replay step" });
    await shownStep(120);
    expect(root()).toHaveAttribute("data-view", "replay");
    expect(part("view-state")).toHaveTextContent("Replaying step 120 of 400");

    await user.click(screen.getByRole("button", { name: "Back to live" }));

    await shownStep(80);
    expect(root()).toHaveAttribute("data-view", "live");
    expect(part("view-state")).toHaveTextContent("Following the live run");
    expect(screen.queryByRole("slider", { name: "Replay step" })).toBeNull();
  });

  it("AC4.7.7 reads Following the live run and shows no slider while a run is live", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES);

    await panel();
    await shownStep(120);
    expect(root()).toHaveAttribute("data-view", "live");
    expect(part("view-state")).toHaveTextContent("Following the live run");
    expect(screen.queryByRole("slider", { name: "Replay step" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Play replay" })).toBeNull();
  });

  it("AC4.7.7 shows no slider for an ended run with a single step line", async () => {
    const api = endedApi(STEP_LINES.slice(0, 1));
    await openTraining(api);

    await panel();
    await shownStep(40);
    expect(part("view-state")).toHaveTextContent("Showing the last logged step");
    expect(screen.queryByRole("slider", { name: "Replay step" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Play replay" })).toBeNull();
  });
});

describe("fine-tuning view: accessibility and honesty (AC4.7.8)", () => {
  it("AC4.7.8 hides the drawing from assistive technology and keeps the same facts as text", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES);

    await panel();
    await shownStep(120);
    const drawing = root().querySelector('svg[data-part="drawing"]');
    expect(drawing).not.toBeNull();
    expect(drawing).toHaveAttribute("aria-hidden", "true");
    expect(part("progress")).toHaveTextContent("Step 120 of 400");
    expect(stage("score")).toHaveTextContent("loss 0.94");
    await waitFor(() => expect(part("weights")).toHaveTextContent("17,432,576 trained"));
  });

  it("AC4.7.8 says which figures are measured and which parts are drawn for illustration", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES);

    await panel();
    const note = part("note");
    expect(note).not.toBeNull();
    expect(note).toHaveTextContent("Measured");
    expect(note).toHaveTextContent(/step/i);
    expect(note).toHaveTextContent(/loss/i);
    expect(note).toHaveTextContent(/gradient norm/i);
    expect(note).toHaveTextContent(/learning rate/i);
    expect(note).toHaveTextContent("Drawn for illustration");
    expect(note).toHaveTextContent(/every adapter is updated on every step/i);
    expect(note).toHaveTextContent(/per-layer sizes are not recorded/i);
  });

  it("AC4.7.8 carries data-motion live by default", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });
    sendLines(api, STEP_LINES.slice(0, 1));

    await panel();
    expect(root()).toHaveAttribute("data-motion", "live");
  });

  it("AC4.7.8 carries data-motion still when the operating system asks for reduced motion", async () => {
    const api = liveApi();
    await openTraining(api, { status: running(), reducedMotion: true });
    sendLines(api, STEP_LINES.slice(0, 1));

    await panel();
    expect(root()).toHaveAttribute("data-motion", "still");
  });
});
