/**
 * Batch-9 (u5-website), part T: the token-by-token walkthrough of the training page, US4.8
 * (AC4.8.1-AC4.8.7), plus the Size note of construction/batch-9.md (drawings at most two-thirds
 * of the window and centred, prose at most 75 characters a line). The drawing is decorative, so
 * the tests read the walkthrough's text and its `data-*` markers.
 *
 * What the tests assume the builder provides:
 * - `StepWalkthrough` from `web/src/components/step-walkthrough.tsx`, with the same props as
 *   `FinetuneView`: `runId`, `method`, `model`, `liveLines`, `live`, optional `loading`. It reads
 *   the run's config with `api.getRun(runId)` (`batch_size`, `cot_temperature`) and, for a run
 *   that is not live, its stored lines with `api.getMetrics(runId)`.
 * - `WALKTHROUGH_SAMPLE` from `web/src/lib/walkthrough.ts`: `{ prompt: readonly string[];
 *   answer: readonly string[] }`, the built-in sample's question and answer as word-piece tokens.
 * - The root element carries `data-walkthrough` (`training`, `generation` or `none`),
 *   `data-phase` (the shown phase in lower case) and `data-motion` (`live` or `still`). With a
 *   walkthrough it is a region (a `section` with `aria-labelledby` its heading) named "One
 *   training step, token by token" or "How the model writes an answer, token by token".
 * - Each phase is a list item `[data-phase-key="<lower case name>"]` holding an `h3` with the
 *   name and a `[data-part="meaning"]` line; the shown one carries `aria-current="step"`.
 * - `[data-part="phase-detail"]`: the shown phase's facts as text (not hidden), with the figures
 *   in `[data-figure="batch-size" | "loss" | "grad-norm" | "learning-rate" | "temperature"]`,
 *   formatted like the fine-tuning view (`formatLoss`, `formatGrad`, `formatRate`), "—" when
 *   missing.
 * - The drawing: every `[data-part="drawing"]` carries `aria-hidden="true"`, `mx-auto` and
 *   `max-w-[66vw]`. Only the shown phase's drawing is in the DOM. Token chips are
 *   `[data-token="<token text>"][data-role="prompt" | "answer" | "pad"]`; the prompt chips sit in
 *   a `[data-group]` labelled "no loss" (its text or `aria-label`). Predict draws one
 *   `[data-predict]` per answer token with `data-input` (the token) and `data-target` (the token
 *   it must guess). In the generation walkthrough the answer chips are the tokens written so far.
 * - `[data-part="note"]`: what is an illustration and what is measured; it and the phase detail
 *   carry `max-w-[75ch]`.
 * - Buttons "Pause walkthrough" / "Play walkthrough", "Previous phase", "Next phase". The phase
 *   clock is a `setInterval` or `setTimeout` of 1.8 s; CSS animations in
 *   `web/src/styles/walkthrough.css` run only under `[data-motion="live"]`.
 */
import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";

import { StepWalkthrough } from "@/components/step-walkthrough";
import type { Api, MetricsLine, Run, RunConfig, Status } from "@/lib/api";
import { ApiProvider } from "@/lib/api-context";
import { WALKTHROUGH_SAMPLE } from "@/lib/walkthrough";
import { fakeApi, metricsLine, Q17, run, serviceStatus, type FakeApi } from "@/test/fake-api";
import { setReducedMotion } from "@/test/setup";
import { act, fireEvent, renderPage, screen, waitFor, within } from "@/test/utils";

const LIVE = "q17-sft-dev-1";
const PHASE_MS = 1800;
const CSS = resolve(process.cwd(), "web/src/styles/walkthrough.css");

const TRAINING = "One training step, token by token";
const GENERATION = "How the model writes an answer, token by token";
const EMPTY = "Start a run to see how a step works.";

const TRAINING_PHASES = [
  ["tokenize", "Tokenize"],
  ["batch", "Batch"],
  ["embed", "Embed"],
  ["forward", "Forward"],
  ["predict", "Predict"],
  ["loss", "Loss"],
  ["backward", "Backward"],
  ["update", "Update"],
] as const;

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

function activeRun(runId: string, method: string): Run {
  return run({
    run_id: runId,
    model: Q17,
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
  settings?: RunConfig;
}

/** A fake Api whose service reports one active run of `method` on Qwen3-1.7B. */
function liveApi({ runId = LIVE, method = "sft", settings = {} }: LiveOptions = {}): FakeApi {
  return fakeApi({
    getStatus: async () => running(runId),
    listRuns: async () => ({ runs: [activeRun(runId, method)], skipped_rows: 0 }),
    getRun: async (id: string) => ({
      run_id: id,
      config: config({ method, ...settings }),
      status: {},
      timings: {},
    }),
  });
}

/** Three step lines of a supervised run, then a dev evaluation line at step 120 (no loss). */
const STEP_LINES: MetricsLine[] = [
  metricsLine({ step: 40, total_steps: 400, loss: 1.8, learning_rate: 2e-4, grad_norm: 0.9 }),
  metricsLine({ step: 80, total_steps: 400, loss: 1.1, learning_rate: 1.9e-4, grad_norm: 0.61 }),
  metricsLine({ step: 120, total_steps: 400, loss: 0.94, learning_rate: 1.8e-4, grad_norm: 0.42 }),
  metricsLine({
    step: 120,
    total_steps: 400,
    loss: null,
    learning_rate: null,
    dev_accuracy: 0.47,
  }),
];

function sendLines(api: FakeApi, lines: MetricsLine[], runId: string = LIVE, from = 1) {
  lines.forEach((line, i) => api.stream.metric({ ...line, run_id: runId }, from + i));
}

/** Renders /training, waits for its stream, and sends `status` as the stream would. */
async function openTraining(
  api: FakeApi,
  { status, reducedMotion }: { status?: Status; reducedMotion?: boolean } = {},
) {
  const result = renderPage("/training", { api, reducedMotion });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  if (status) api.stream.status(status);
  return result;
}

interface Props {
  runId?: string | null;
  method?: string | null;
  lines?: readonly MetricsLine[];
  live?: boolean;
}

function walkthrough({ runId = LIVE, method = "sft", lines = [], live = true }: Props = {}) {
  return (
    <StepWalkthrough runId={runId} method={method} model={Q17} liveLines={lines} live={live} />
  );
}

/** Renders the walkthrough alone under `api`; `rerender` keeps the providers. */
function renderAlone(ui: ReactNode, api: Api) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider api={api}>
      <MemoryRouter>{children}</MemoryRouter>
    </ApiProvider>
  );
  return render(<>{ui}</>, { wrapper });
}

/** Lets pending promises (the run's settings) settle while timers may be fake. */
async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function useFakeClock() {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
}

function tick(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

/** The walkthrough's root as it is now. */
function root(): HTMLElement {
  const el = document.querySelector<HTMLElement>("[data-walkthrough]");
  if (!el) throw new Error("the walkthrough is not on the page");
  return el;
}

function phase(): string | null {
  return root().getAttribute("data-phase");
}

function phaseItems(): HTMLElement[] {
  return [...root().querySelectorAll<HTMLElement>("[data-phase-key]")];
}

function phaseItem(key: string): HTMLElement {
  const el = root().querySelector<HTMLElement>(`[data-phase-key="${key}"]`);
  if (!el) throw new Error(`no phase ${key}`);
  return el;
}

function detail(): HTMLElement {
  const el = root().querySelector<HTMLElement>('[data-part="phase-detail"]');
  if (!el) throw new Error("no phase detail");
  return el;
}

function figure(name: string): HTMLElement {
  const el = detail().querySelector<HTMLElement>(`[data-figure="${name}"]`);
  if (!el) throw new Error(`no figure ${name} in the ${phase()} phase`);
  return el;
}

function chips(role: string): HTMLElement[] {
  return [...root().querySelectorAll<HTMLElement>(`[data-token][data-role="${role}"]`)];
}

function tokens(role: string): string[] {
  return chips(role).map((el) => el.getAttribute("data-token") ?? "");
}

function button(name: string): HTMLElement {
  return within(root()).getByRole("button", { name });
}

function nextPhase() {
  fireEvent.click(button("Next phase"));
}

/** Clicks Next phase until `key` is shown. */
function goTo(key: string) {
  for (let i = 0; i < 40 && phase() !== key; i += 1) nextPhase();
  expect(phase()).toBe(key);
}

/** Renders the walkthrough of a live sft run, waits for its settings, and pauses it. */
async function pausedTraining(lines: readonly MetricsLine[] = STEP_LINES, settings?: RunConfig) {
  const api = liveApi({ settings });
  renderAlone(walkthrough({ lines }), api);
  await screen.findByRole("region", { name: TRAINING });
  await waitFor(() => expect(api.getRun).toHaveBeenCalled());
  fireEvent.click(button("Pause walkthrough"));
  return api;
}

/** The current phase item is the only one with aria-current, and matches data-phase. */
function expectCurrent(key: string) {
  expect(phase()).toBe(key);
  const current = phaseItems().filter((el) => el.getAttribute("aria-current") === "step");
  expect(current).toHaveLength(1);
  expect(current[0]).toHaveAttribute("data-phase-key", key);
}

afterEach(() => {
  vi.useRealTimers();
});

describe("walkthrough: the eight phases of a training step (AC4.8.1)", () => {
  it("AC4.8.1 lists Tokenize, Batch, Embed, Forward, Predict, Loss, Backward and Update in order, each with a meaning", async () => {
    renderAlone(walkthrough(), liveApi());

    const region = await screen.findByRole("region", { name: TRAINING });
    expect(region).toHaveAttribute("data-walkthrough", "training");
    const items = phaseItems();
    expect(items.map((el) => el.getAttribute("data-phase-key"))).toEqual(
      TRAINING_PHASES.map(([key]) => key),
    );
    expect(items.map((el) => el.querySelector("h3")?.textContent?.trim())).toEqual(
      TRAINING_PHASES.map(([, name]) => name),
    );
    for (const item of items) {
      const meaning = item.querySelector('[data-part="meaning"]')?.textContent?.trim() ?? "";
      expect(meaning.length).toBeGreaterThan(15);
      expect(meaning).not.toContain("\n");
    }
  });

  it("AC4.8.1 marks the shown phase with aria-current and names it in data-phase", async () => {
    await pausedTraining();

    expectCurrent("tokenize");
    expect(root()).toHaveAttribute("data-phase", "tokenize");
    nextPhase();
    expectCurrent("batch");
    nextPhase();
    expectCurrent("embed");
  });

  it("AC4.8.1 shows the training walkthrough on the training page for sft, terse, optuna and selfcot runs", async () => {
    for (const method of ["sft", "terse", "optuna", "selfcot"]) {
      const runId = `q17-${method}-dev-1`;
      const api = liveApi({ runId, method });
      const { unmount } = await openTraining(api, { status: running(runId) });

      const region = await screen.findByRole("region", { name: TRAINING });
      expect(region).toHaveAttribute("data-walkthrough", "training");
      expect(phaseItems()).toHaveLength(8);
      const shown = phase() ?? "";
      expect(TRAINING_PHASES.map(([key]) => key)).toContain(shown);
      expectCurrent(shown);
      unmount();
    }
  });

  it("AC4.8.1 sits right after the fine-tuning view on the training page", async () => {
    const api = liveApi();
    await openTraining(api, { status: running() });

    const finetune = await screen.findByRole("region", { name: "How the model is fine-tuned" });
    const walk = await screen.findByRole("region", { name: TRAINING });
    const next = finetune.nextElementSibling;
    expect(next === walk || (next?.contains(walk) ?? false)).toBe(true);
  });
});

describe("walkthrough: Tokenize, once before step 1 (AC4.8.2)", () => {
  it("AC4.8.2 says the training set was tokenized once, before step 1, and each step only pads its batch", async () => {
    await pausedTraining();
    goTo("tokenize");

    const text = detail().textContent ?? "";
    expect(text).toMatch(/whole training set/i);
    expect(text).toMatch(/tokenized once/i);
    expect(text).toMatch(/before step 1/i);
    expect(text).toMatch(/pads?/i);
    expect(text).toMatch(/rectangle/i);
    expect(text).toMatch(/no text is tokenized again/i);
  });

  it("AC4.8.2 shows the sample example as chips: question tokens as prompt in a no-loss group, answer tokens as answer", async () => {
    await pausedTraining();
    goTo("tokenize");

    expect(WALKTHROUGH_SAMPLE.prompt.length).toBeGreaterThanOrEqual(3);
    expect(WALKTHROUGH_SAMPLE.answer.length).toBeGreaterThanOrEqual(3);
    expect(tokens("prompt")).toEqual([...WALKTHROUGH_SAMPLE.prompt]);
    expect(tokens("answer")).toEqual([...WALKTHROUGH_SAMPLE.answer]);

    const groups = new Set(chips("prompt").map((el) => el.closest("[data-group]")));
    expect(groups.size).toBe(1);
    const [group] = [...groups];
    expect(group).not.toBeNull();
    const label = `${group?.getAttribute("aria-label") ?? ""} ${group?.textContent ?? ""}`;
    expect(label).toMatch(/no loss/i);
    for (const chip of chips("answer")) expect(chip.closest("[data-group]")).not.toBe(group);
  });
});

describe("walkthrough: the run's figures inside their phases (AC4.8.3)", () => {
  it("AC4.8.3 Batch shows the run's batch size and padding chips", async () => {
    await pausedTraining();
    goTo("batch");

    await waitFor(() => expect(figure("batch-size")).toHaveTextContent(/^4$/));
    expect(chips("pad").length).toBeGreaterThan(0);
  });

  it("AC4.8.3 Batch follows the run's own batch size", async () => {
    await pausedTraining(STEP_LINES, { batch_size: 8 });
    goTo("batch");

    await waitFor(() => expect(figure("batch-size")).toHaveTextContent(/^8$/));
  });

  it("AC4.8.3 Predict pairs every answer token with the next token it must guess, shifted by one", async () => {
    await pausedTraining();
    goTo("predict");

    const pairs = [...root().querySelectorAll<HTMLElement>("[data-predict]")];
    const inputs = pairs.map((el) => el.getAttribute("data-input"));
    const targets = pairs.map((el) => el.getAttribute("data-target"));
    expect(inputs).toEqual([...WALKTHROUGH_SAMPLE.answer]);
    for (let i = 0; i < pairs.length - 1; i += 1) expect(targets[i]).toBe(inputs[i + 1]);
    expect((targets[targets.length - 1] ?? "").length).toBeGreaterThan(0);
  });

  it("AC4.8.3 Loss shows the newest step line's loss and says only answer tokens count", async () => {
    await pausedTraining();
    goTo("loss");

    expect(figure("loss")).toHaveTextContent(/^0\.94$/);
    expect(detail()).toHaveTextContent(/only (the )?answer tokens count/i);
  });

  it("AC4.8.3 Backward shows the newest gradient norm and says the gradient stops at the frozen weights", async () => {
    await pausedTraining();
    goTo("backward");

    expect(figure("grad-norm")).toHaveTextContent(/^0\.42$/);
    expect(detail()).toHaveTextContent(/stops at the frozen weights/i);
  });

  it("AC4.8.3 Backward reads a dash when the newest step line has no gradient norm", async () => {
    await pausedTraining([metricsLine({ step: 7, total_steps: 100, loss: 1.2, grad_norm: null })]);
    goTo("backward");

    expect(figure("grad-norm")).toHaveTextContent(/^—$/);
  });

  it("AC4.8.3 Update shows the newest learning rate and says only the LoRA matrices A and B change", async () => {
    await pausedTraining();
    goTo("update");

    expect(figure("learning-rate")).toHaveTextContent(/^1\.8e-4$/);
    expect(detail()).toHaveTextContent(/only the LoRA matrices A and B change/i);
  });

  it("AC4.8.3 with no step line yet the phases still show, with dashes for the figures", async () => {
    await pausedTraining([]);

    expect(phaseItems()).toHaveLength(8);
    goTo("loss");
    expect(figure("loss")).toHaveTextContent(/^—$/);
    goTo("backward");
    expect(figure("grad-norm")).toHaveTextContent(/^—$/);
    goTo("update");
    expect(figure("learning-rate")).toHaveTextContent(/^—$/);
  });

  it("AC4.8.3 reads the live run's newest figures on the training page", async () => {
    const api = liveApi();
    await openTraining(api, { status: running(), reducedMotion: true });
    sendLines(api, STEP_LINES);

    await screen.findByRole("region", { name: TRAINING });
    goTo("loss");
    await waitFor(() => expect(figure("loss")).toHaveTextContent(/^0\.94$/));
    goTo("backward");
    expect(figure("grad-norm")).toHaveTextContent(/^0\.42$/);
    goTo("update");
    expect(figure("learning-rate")).toHaveTextContent(/^1\.8e-4$/);
  });
});

describe("walkthrough: motion (AC4.8.4)", () => {
  it("AC4.8.4 carries data-motion live and moves to the next phase every 1.8 seconds, from the last back to the first", async () => {
    useFakeClock();
    renderAlone(walkthrough({ lines: STEP_LINES }), liveApi());
    await settle();

    expect(root()).toHaveAttribute("data-motion", "live");
    expect(phase()).toBe("tokenize");
    tick(PHASE_MS - 100);
    expect(phase()).toBe("tokenize");
    tick(100);
    expectCurrent("batch");
    tick(PHASE_MS * 6);
    expectCurrent("update");
    tick(PHASE_MS);
    expectCurrent("tokenize");
  });

  it("AC4.8.4 Pause walkthrough stops it and then reads Play walkthrough, which starts it again", async () => {
    useFakeClock();
    renderAlone(walkthrough({ lines: STEP_LINES }), liveApi());
    await settle();

    tick(PHASE_MS);
    expect(phase()).toBe("batch");
    fireEvent.click(button("Pause walkthrough"));
    expect(button("Play walkthrough")).toBeInTheDocument();
    expect(within(root()).queryByRole("button", { name: "Pause walkthrough" })).toBeNull();
    tick(PHASE_MS * 10);
    expect(phase()).toBe("batch");

    fireEvent.click(button("Play walkthrough"));
    expect(button("Pause walkthrough")).toBeInTheDocument();
    tick(PHASE_MS);
    expect(phase()).toBe("embed");
  });

  it("AC4.8.4 Previous phase and Next phase move one phase, playing or paused", async () => {
    useFakeClock();
    renderAlone(walkthrough({ lines: STEP_LINES }), liveApi());
    await settle();

    nextPhase();
    expectCurrent("batch");
    nextPhase();
    expectCurrent("embed");
    fireEvent.click(button("Previous phase"));
    expectCurrent("batch");

    fireEvent.click(button("Pause walkthrough"));
    nextPhase();
    expectCurrent("embed");
    fireEvent.click(button("Previous phase"));
    expectCurrent("batch");
  });

  it("AC4.8.4 a new step line from the live stream does not move the phase", async () => {
    useFakeClock();
    const api = liveApi();
    const { rerender } = renderAlone(walkthrough({ lines: STEP_LINES.slice(0, 1) }), api);
    await settle();

    fireEvent.click(button("Pause walkthrough"));
    for (let i = 0; i < 5; i += 1) nextPhase();
    expect(phase()).toBe("loss");
    expect(figure("loss")).toHaveTextContent(/^1\.8$/);

    rerender(walkthrough({ lines: STEP_LINES.slice(0, 3) }));
    await settle();
    expect(phase()).toBe("loss");
    expect(figure("loss")).toHaveTextContent(/^0\.94$/);

    // Playing: a line that arrives between two ticks does not move the phase either.
    fireEvent.click(button("Play walkthrough"));
    tick(PHASE_MS / 2);
    rerender(walkthrough({ lines: STEP_LINES }));
    await settle();
    expect(phase()).toBe("loss");
  });

  it("AC4.8.4 a new step line on the training page does not move the phase", async () => {
    const api = liveApi();
    await openTraining(api, { status: running(), reducedMotion: true });
    sendLines(api, STEP_LINES.slice(0, 1));
    await screen.findByRole("region", { name: TRAINING });
    goTo("embed");

    sendLines(api, STEP_LINES.slice(1, 3), LIVE, 2);
    await waitFor(() =>
      expect(document.querySelector("main [data-mode]")).toHaveAttribute("data-step", "120"),
    );
    expect(phase()).toBe("embed");
  });

  it("AC4.8.4 with reduce-motion on it carries data-motion still, starts paused and never moves by itself", async () => {
    setReducedMotion(true);
    useFakeClock();
    renderAlone(walkthrough({ lines: STEP_LINES }), liveApi());
    await settle();

    expect(root()).toHaveAttribute("data-motion", "still");
    expect(button("Play walkthrough")).toBeInTheDocument();
    expect(phase()).toBe("tokenize");
    tick(PHASE_MS * 20);
    expect(phase()).toBe("tokenize");
    nextPhase();
    expect(phase()).toBe("batch");
    tick(PHASE_MS * 20);
    expect(phase()).toBe("batch");
  });

  it("AC4.8.4 carries data-motion still on the training page when the system asks for reduced motion", async () => {
    const api = liveApi();
    await openTraining(api, { status: running(), reducedMotion: true });

    await screen.findByRole("region", { name: TRAINING });
    expect(root()).toHaveAttribute("data-motion", "still");
    expect(button("Play walkthrough")).toBeInTheDocument();
  });

  it("AC4.8.4 the answer walkthrough moves every 1.8 seconds too", async () => {
    useFakeClock();
    renderAlone(walkthrough({ runId: "q17-base-dev-2", method: "base" }), liveApi());
    await settle();

    expect(root()).toHaveAttribute("data-motion", "live");
    expect(phase()).toBe("tokenize");
    tick(PHASE_MS - 100);
    expect(phase()).toBe("tokenize");
    tick(100);
    expectCurrent("forward");
  });

  it("AC4.8.4 nothing moves under data-motion still: every animation and transition needs data-motion live", () => {
    const css = readFileSync(CSS, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(css).toMatch(/@keyframes/);
    // Drop the @keyframes blocks (two levels of braces), then read each plain rule.
    const plain = css.replace(/@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, "");
    const moving = /(^|[;{\s])(animation|animation-name|transition|transition-property)\s*:/;
    let rules = 0;
    for (const match of plain.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const [, selector, body] = match;
      if (!moving.test(body)) continue;
      if (/:\s*none\s*(;|$)/.test(body.trim())) continue;
      rules += 1;
      for (const part of selector.split(",")) {
        expect(part).toContain('[data-motion="live"]');
      }
    }
    expect(rules).toBeGreaterThan(0);
  });
});

describe("walkthrough: how a model writes an answer (AC4.8.5)", () => {
  it("AC4.8.5 lists Tokenize, Forward, Choose, Append and Stop for base and best runs, and says the weights do not change", async () => {
    for (const method of ["base", "best"]) {
      const runId = `q17-${method}-dev-1`;
      const { unmount } = renderAlone(walkthrough({ runId, method }), liveApi({ runId, method }));

      const region = await screen.findByRole("region", { name: GENERATION });
      expect(region).toHaveAttribute("data-walkthrough", "generation");
      expect(screen.queryByRole("region", { name: TRAINING })).toBeNull();
      expect(phaseItems().map((el) => el.getAttribute("data-phase-key"))).toEqual([
        "tokenize",
        "forward",
        "choose",
        "append",
        "stop",
      ]);
      expect(phaseItems().map((el) => el.querySelector("h3")?.textContent?.trim())).toEqual([
        "Tokenize",
        "Forward",
        "Choose",
        "Append",
        "Stop",
      ]);
      expect(region).toHaveTextContent("The weights do not change.");
      expectCurrent(phase() ?? "");
      unmount();
    }
  });

  it("AC4.8.5 adds a Check phase for cotgen: the answer is kept only when its final number is right", async () => {
    const runId = "q17-cotgen-train-1";
    renderAlone(walkthrough({ runId, method: "cotgen" }), liveApi({ runId, method: "cotgen" }));

    const region = await screen.findByRole("region", { name: GENERATION });
    expect(phaseItems().map((el) => el.getAttribute("data-phase-key"))).toEqual([
      "tokenize",
      "forward",
      "choose",
      "append",
      "stop",
      "check",
    ]);
    expect(phaseItem("check").querySelector("h3")).toHaveTextContent("Check");
    const meaning = phaseItem("check").querySelector('[data-part="meaning"]');
    expect(meaning).toHaveTextContent(/kept/i);
    expect(meaning).toHaveTextContent(/final number/i);
    expect(region).toHaveTextContent("The weights do not change.");
  });

  it("AC4.8.5 Choose takes the most likely token for base and best", async () => {
    for (const method of ["base", "best"]) {
      const runId = `q17-${method}-dev-1`;
      const api = liveApi({ runId, method });
      const { unmount } = renderAlone(walkthrough({ runId, method }), api);
      await screen.findByRole("region", { name: GENERATION });
      await waitFor(() => expect(api.getRun).toHaveBeenCalled());
      fireEvent.click(button("Pause walkthrough"));
      goTo("choose");

      expect(detail()).toHaveTextContent(/most likely token/i);
      expect(detail().querySelector('[data-figure="temperature"]')).toBeNull();
      unmount();
    }
  });

  it("AC4.8.5 Choose samples at temperature 0.7 for cotgen when the config has no cot_temperature", async () => {
    const runId = "q17-cotgen-train-1";
    const api = liveApi({ runId, method: "cotgen" });
    renderAlone(walkthrough({ runId, method: "cotgen" }), api);
    await screen.findByRole("region", { name: GENERATION });
    await waitFor(() => expect(api.getRun).toHaveBeenCalled());
    fireEvent.click(button("Pause walkthrough"));
    goTo("choose");

    expect(detail()).toHaveTextContent(/sampl/i);
    expect(detail()).not.toHaveTextContent(/most likely token/i);
    await waitFor(() => expect(figure("temperature")).toHaveTextContent(/^0\.7$/));
  });

  it("AC4.8.5 Choose samples at the config's cot_temperature for cotgen", async () => {
    const runId = "q17-cotgen-train-1";
    const api = liveApi({ runId, method: "cotgen", settings: { cot_temperature: 0.9 } });
    renderAlone(walkthrough({ runId, method: "cotgen" }), api);
    await screen.findByRole("region", { name: GENERATION });
    fireEvent.click(button("Pause walkthrough"));
    goTo("choose");

    await waitFor(() => expect(figure("temperature")).toHaveTextContent(/^0\.9$/));
  });

  it("AC4.8.5 the answer grows by one token at each Append up to the sample answer's length, then starts again at Tokenize", async () => {
    for (const method of ["base", "cotgen"]) {
      const runId = `q17-${method}-dev-1`;
      const { unmount } = renderAlone(walkthrough({ runId, method }), liveApi({ runId, method }));
      await screen.findByRole("region", { name: GENERATION });
      fireEvent.click(button("Pause walkthrough"));
      expect(phase()).toBe("tokenize");
      expect(chips("answer")).toHaveLength(0);

      const seen: string[] = ["tokenize"];
      let written = 0;
      for (let i = 0; i < 1000; i += 1) {
        const before = phase();
        nextPhase();
        const now = phase() ?? "";
        seen.push(now);
        expectCurrent(now);
        if (now === "tokenize") break;
        if (now === "append") {
          expect(before).toBe("choose");
          written += 1;
        }
        if (now === "choose") expect(before).toBe("forward");
        expect(chips("answer")).toHaveLength(written);
        expect(tokens("answer")).toEqual(WALKTHROUGH_SAMPLE.answer.slice(0, written));
      }

      expect(seen[seen.length - 1]).toBe("tokenize");
      expect(written).toBe(WALKTHROUGH_SAMPLE.answer.length);
      expect(chips("answer")).toHaveLength(0);
      const lastAppend = seen.lastIndexOf("append");
      const tail = seen.slice(lastAppend + 1, -1);
      expect(tail).toEqual(method === "cotgen" ? ["stop", "check"] : ["stop"]);
      expect(seen.filter((key) => key === "stop")).toHaveLength(1);
      unmount();
    }
  });

  it("AC4.8.5 shows the answer walkthrough on the training page for a cotgen run", async () => {
    const runId = "q17-cotgen-train-1";
    const api = liveApi({ runId, method: "cotgen" });
    await openTraining(api, { status: running(runId) });

    const region = await screen.findByRole("region", { name: GENERATION });
    expect(region).toHaveAttribute("data-walkthrough", "generation");
    expect(region).toHaveTextContent("The weights do not change.");
    expect(phaseItems()).toHaveLength(6);
    expectCurrent(phase() ?? "");
    expect(screen.queryByRole("region", { name: TRAINING })).toBeNull();
  });
});

describe("walkthrough: drawing and text (AC4.8.6)", () => {
  it("AC4.8.6 hides the drawing from assistive technology and keeps the same facts as text", async () => {
    await pausedTraining();

    for (const key of ["tokenize", "batch", "predict", "loss"]) {
      goTo(key);
      const drawings = [...root().querySelectorAll('[data-part="drawing"]')];
      expect(drawings.length).toBeGreaterThan(0);
      for (const drawing of drawings) expect(drawing).toHaveAttribute("aria-hidden", "true");
      expect(detail().closest('[aria-hidden="true"]')).toBeNull();
      expect((detail().textContent ?? "").trim().length).toBeGreaterThan(20);
    }
    goTo("loss");
    expect(figure("loss").closest('[aria-hidden="true"]')).toBeNull();
    for (const item of phaseItems()) expect(item.closest('[aria-hidden="true"]')).toBeNull();
  });

  it("AC4.8.6 says the sample text is an illustration and the loss, gradient norm and learning rate are measured", async () => {
    await pausedTraining();

    const note = root().querySelector<HTMLElement>('[data-part="note"]');
    expect(note).not.toBeNull();
    expect(note?.closest('[aria-hidden="true"]')).toBeNull();
    expect(note).toHaveTextContent(/sample/i);
    expect(note).toHaveTextContent(/illustration/i);
    expect(note).toHaveTextContent(/measured/i);
    expect(note).toHaveTextContent(/loss/i);
    expect(note).toHaveTextContent(/gradient norm/i);
    expect(note).toHaveTextContent(/learning rate/i);
  });

  it("AC4.8.6 the answer walkthrough hides its drawing too and says its sample is an illustration", async () => {
    const runId = "q17-base-dev-1";
    renderAlone(walkthrough({ runId, method: "base" }), liveApi({ runId, method: "base" }));
    await screen.findByRole("region", { name: GENERATION });

    const drawings = [...root().querySelectorAll('[data-part="drawing"]')];
    expect(drawings.length).toBeGreaterThan(0);
    for (const drawing of drawings) expect(drawing).toHaveAttribute("aria-hidden", "true");
    expect(detail().closest('[aria-hidden="true"]')).toBeNull();
    const note = root().querySelector<HTMLElement>('[data-part="note"]');
    expect(note).toHaveTextContent(/sample/i);
    expect(note).toHaveTextContent(/illustration/i);
  });

  it("AC4.8.6 the drawing is at most two-thirds of the window wide and centred, prose at most 75ch (Size note)", async () => {
    await pausedTraining();

    for (const [key] of TRAINING_PHASES) {
      goTo(key);
      const drawings = [...root().querySelectorAll('[data-part="drawing"]')];
      expect(drawings.length).toBeGreaterThan(0);
      for (const drawing of drawings) {
        expect(drawing).toHaveClass("max-w-[66vw]");
        expect(drawing).toHaveClass("mx-auto");
      }
      expect(detail()).toHaveClass("max-w-[75ch]");
    }
    expect(root().querySelector('[data-part="note"]')).toHaveClass("max-w-[75ch]");
  });

  it("AC4.8.6 the answer walkthrough's drawing keeps the same size limits (Size note)", async () => {
    const runId = "q17-cotgen-train-1";
    renderAlone(walkthrough({ runId, method: "cotgen" }), liveApi({ runId, method: "cotgen" }));
    await screen.findByRole("region", { name: GENERATION });
    fireEvent.click(button("Pause walkthrough"));

    for (const key of ["tokenize", "forward", "choose", "append"]) {
      goTo(key);
      for (const drawing of root().querySelectorAll('[data-part="drawing"]')) {
        expect(drawing).toHaveClass("max-w-[66vw]");
        expect(drawing).toHaveClass("mx-auto");
      }
      expect(detail()).toHaveClass("max-w-[75ch]");
    }
  });
});

describe("walkthrough: nothing to walk through (AC4.8.7)", () => {
  it("AC4.8.7 reads Start a run to see how a step works when no run has happened", async () => {
    await openTraining(fakeApi());

    await waitFor(() => expect(root()).toHaveTextContent(EMPTY));
    expect(root()).toHaveAttribute("data-walkthrough", "none");
    expect(phaseItems()).toHaveLength(0);
    expect(root().querySelectorAll("[data-token]")).toHaveLength(0);
  });

  it("AC4.8.7 reads the same with no run when rendered alone", async () => {
    renderAlone(walkthrough({ runId: null, method: null, live: false }), fakeApi());

    await waitFor(() => expect(root()).toHaveTextContent(EMPTY));
    expect(phaseItems()).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "Next phase" })).toBeNull();
  });

  it("AC4.8.7 reads the same for a run whose method has no walkthrough", async () => {
    const runId = "q17-grpo-dev-1";
    const api = liveApi({ runId, method: "grpo" });
    await openTraining(api, { status: running(runId) });

    await waitFor(() => expect(root()).toHaveTextContent(EMPTY));
    expect(root()).toHaveAttribute("data-walkthrough", "none");
    expect(phaseItems()).toHaveLength(0);
    expect(screen.queryByRole("region", { name: TRAINING })).toBeNull();
    expect(screen.queryByRole("region", { name: GENERATION })).toBeNull();
  });
});
