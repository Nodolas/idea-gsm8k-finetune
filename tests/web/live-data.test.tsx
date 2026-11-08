/**
 * Part W1 (u5-website, batch-6): the training page's live data. AC4.5.7 is the "Live numbers"
 * panel, AC4.5.8 the "Recent steps" table and AC4.5.10 the "GPU" panel. The page reads only the
 * fake Api: C7 events pushed with `api.stream.*` for the live run, `getMetrics` for a past run and
 * `getGpu` for the GPU panel. The tests use only the DOM contract of construction/batch-6.md
 * (regions named by their h2, `data-stat` / `data-part` / `data-step`) and the exact value formats
 * listed there; every expected string below is worked out by hand from the data next to it.
 */
import {
  UNREACHABLE_MESSAGE,
  type Api,
  type Gpu,
  type MetricsLine,
  type Run,
  type Status,
} from "@/lib/api";
import {
  apiError,
  fakeApi,
  gpu,
  metricsLine,
  Q06,
  run,
  serviceStatus,
  type FakeApi,
} from "@/test/fake-api";
import { act, renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

const LIVE = "q06-sft-dev-3";
const PAST = "q06-sft-dev-1";
const TOTAL = 1744;
const DASH = "—";
const MINUS = "−";
const DOT = "·";
/** The clock the live tests pin: the stream's `lastUpdate` is this when their lines arrive. */
const PINNED = new Date("2026-11-04T20:31:07Z");

/* ---------------------------------------------------------------- harness (as training-live) */

function normalize(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

function running(runId: string = LIVE): Status {
  return serviceStatus({ status: "RUNNING", run_id: runId, started_at: "2026-11-04T20:10:00Z" });
}

function activeRun(runId: string, method = "sft", model = Q06): Run {
  return run({
    run_id: runId,
    model,
    method,
    dev_accuracy: null,
    minutes: null,
    date: null,
    started_at: "2026-11-04T20:10:00Z",
    status: "running",
  });
}

/** A fake Api whose service reports `runId` as the active run. */
function liveApi(runId: string = LIVE, method = "sft", overrides: Partial<Api> = {}): FakeApi {
  return fakeApi({
    getStatus: async () => running(runId),
    listRuns: async () => ({ runs: [activeRun(runId, method)], skipped_rows: 0 }),
    ...overrides,
  });
}

/** Renders /training, waits for its stream, and sends `status` as the stream would. */
async function openTraining(api: FakeApi, status?: Status) {
  const result = renderPage("/training", { api });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  if (status) api.stream.status(status);
  return result;
}

function sendLines(api: FakeApi, lines: MetricsLine[], runId: string = LIVE, from = 1) {
  lines.forEach((line, i) => api.stream.metric({ ...line, run_id: runId }, from + i));
}

/** Pins `Date` (only) so the stream's `lastUpdate` is `PINNED` when the lines are sent. */
function pinClock(): void {
  vi.useFakeTimers({ toFake: ["Date"], now: PINNED });
}

/** Opens /training for a live run under a pinned clock and sends `lines` as stream lines. */
async function openLive(
  lines: MetricsLine[],
  runId: string = LIVE,
  method = "sft",
): Promise<FakeApi> {
  pinClock();
  const api = liveApi(runId, method);
  await openTraining(api, running(runId));
  sendLines(api, lines, runId);
  return api;
}

/** The hourglass band: the element carrying `data-fraction`. */
async function hourglassBand(): Promise<HTMLElement> {
  return waitFor(() => {
    const band = document.querySelector<HTMLElement>("[data-fraction]");
    if (!band) throw new Error("no element with data-fraction (hourglass band) yet");
    return band;
  });
}

/** Point counts of a MetricChart figure, one per series (`data-points`). */
function seriesPoints(figure: HTMLElement): number[] {
  return [...figure.querySelectorAll("[data-series]")].map((el) =>
    Number(el.getAttribute("data-points")),
  );
}

/** Selects a curve tab and returns its MetricChart figure ("<Label> curve: ..."). */
async function showCurve(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(await screen.findByRole("tab", { name: label }));
  return screen.findByRole("figure", { name: new RegExp(`^${label} curve`) });
}

/** The past-runs table row whose run id cell reads `runId`. */
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

/** A control named `name` that may be a button or a link. */
function control(name: string | RegExp): HTMLElement {
  return screen.queryByRole("link", { name }) ?? screen.getByRole("button", { name });
}

/** A fake Api with one finished past run whose metrics come from `getMetrics`. */
function pastApi(lines: MetricsLine[]): FakeApi {
  return fakeApi({
    listRuns: async () => ({
      runs: [
        run({
          run_id: PAST,
          status: "finished",
          dev_accuracy: 0.62,
          minutes: 23.4,
          date: "2026-11-04T20:33:24Z",
          started_at: "2026-11-04T20:10:00Z",
        }),
      ],
      skipped_rows: 0,
    }),
    getMetrics: async (id: string) =>
      id === PAST
        ? { lines: lines.map((line) => ({ ...line, run_id: PAST })), next: lines.length }
        : { lines: [], next: 0 },
  });
}

/** Renders /training with a finished past run and opens it from Past runs. */
async function openPastRun(lines: MetricsLine[]): Promise<FakeApi> {
  const user = userEvent.setup();
  const api = pastApi(lines);
  renderPage("/training", { api });
  await pastRunRow(PAST);
  await user.click(control(`Open ${PAST}`));
  await screen.findByRole("heading", { name: new RegExp(`Viewing ${PAST}`) });
  return api;
}

/* ------------------------------------------------------------------------------ test data */

/** step, loss, learning rate, gradient norm, elapsed seconds. */
type StepRow = readonly [number, number, number, number, number];

/**
 * Thirteen logging steps of a 1744-step run (2 epochs: epoch = 2 * step / 1744). Time left is
 * 2460 s at step 130 and 20 s more per earlier step. Pace: 129 s at step 30 to 309 s at step
 * 130 is 1.80 s/step; the 10 newest step lines (step 40 at 150 s) would give 1.77 and all
 * thirteen 2.48, so the 11-line window is checked by the speed.
 */
const STEP_ROWS: StepRow[] = [
  [10, 2.0, 1e-4, 0.9, 12],
  [20, 1.6, 1.5e-4, 1.34, 40],
  [30, 1.3, 2e-4, 0.8, 129],
  [40, 1.1, 2e-4, 0.7, 150],
  [50, 1.0, 2e-4, 0.65, 165],
  [60, 0.9, 2e-4, 0.6, 183],
  [70, 0.8, 2e-4, 0.55, 201],
  [80, 0.7, 2e-4, 0.5, 219],
  [90, 0.6, 2e-4, 0.52, 237],
  [100, 0.55, 1.9e-4, 0.48, 255],
  [110, 0.5, 1.9e-4, 0.46, 273],
  [120, 0.45, 1.8e-4, 0.44, 291],
  [130, 0.5, 1.7e-4, 0.4213, 309],
];

/** The step after the last of `STEP_ROWS`. */
const NEXT_ROW: StepRow = [140, 0.4, 1.6e-4, 0.4, 327];

function etaFor(step: number): number {
  return 2460 + (130 - step) * 20;
}

function stepLine([step, loss, rate, grad, elapsed]: StepRow): MetricsLine {
  return metricsLine({
    step,
    total_steps: TOTAL,
    loss,
    learning_rate: rate,
    grad_norm: grad,
    epoch: (2 * step) / TOTAL,
    elapsed_s: elapsed,
    eta_s: etaFor(step),
  });
}

/** A dev-accuracy line: no loss, rate, gradient norm or epoch (AC2.2.6). */
function devLine(step: number, accuracy: number, elapsed: number): MetricsLine {
  return metricsLine({
    step,
    total_steps: TOTAL,
    loss: null,
    learning_rate: null,
    grad_norm: null,
    epoch: null,
    dev_accuracy: accuracy,
    elapsed_s: elapsed,
    eta_s: etaFor(step),
  });
}

/** The 13 step lines with a dev line after step 40 (64.1%) and one after step 80 (62.0%). */
function mainLines(): MetricsLine[] {
  const lines: MetricsLine[] = [];
  for (const row of STEP_ROWS) {
    lines.push(stepLine(row));
    if (row[0] === 40) lines.push(devLine(40, 0.641, 152));
    if (row[0] === 80) lines.push(devLine(80, 0.62, 224));
  }
  return lines;
}

const MAIN_LINES = mainLines();

/** A line for a small 100-step run; `partial` overrides the defaults. */
function smallLine(partial: Partial<MetricsLine>): MetricsLine {
  return metricsLine({ total_steps: 100, ...partial });
}

/* -------------------------------------------------------------------- panel readers */

interface Stat {
  label: string;
  value: string;
  meaning: string;
}

function readStat(panel: HTMLElement, key: string): Stat | null {
  const root = panel.querySelector<HTMLElement>(`[data-stat="${key}"]`);
  if (!root) return null;
  return {
    label: normalize(root.querySelector("dt")?.textContent),
    value: normalize(root.querySelector('[data-part="value"]')?.textContent),
    meaning: normalize(root.querySelector('[data-part="meaning"]')?.textContent),
  };
}

function stat(panel: HTMLElement, key: string): Stat {
  const found = readStat(panel, key);
  if (!found) throw new Error(`no data-stat="${key}" in the panel`);
  return found;
}

function values(panel: HTMLElement, keys: string[]): Record<string, string> {
  return Object.fromEntries(keys.map((key) => [key, stat(panel, key).value]));
}

function currentLive(): HTMLElement {
  return screen.getByRole("region", { name: "Live numbers" });
}

function currentRecent(): HTMLElement {
  return screen.getByRole("region", { name: "Recent steps" });
}

function currentGpu(): HTMLElement {
  return screen.getByRole("region", { name: "GPU" });
}

/** The `data-step` of every Recent steps row, in table order. */
function shownSteps(panel: HTMLElement): string[] {
  return Array.from(panel.querySelectorAll("tr[data-step]"), (row) =>
    String(row.getAttribute("data-step")),
  );
}

/** The normalised cell texts of the Recent steps row for `step`. */
function rowCells(panel: HTMLElement, step: number): string[] {
  const rows = panel.querySelectorAll(`tr[data-step="${step}"]`);
  expect(rows, `rows for step ${step}`).toHaveLength(1);
  return Array.from(rows[0].querySelectorAll("th, td"), (cell) => normalize(cell.textContent));
}

const LIVE_LABELS: Record<string, string> = {
  progress: "Progress",
  epoch: "Epoch",
  speed: "Speed",
  elapsed: "Elapsed",
  remaining: "Remaining",
  finish: "Should end at",
  loss: "Loss",
  "lowest-loss": "Lowest loss",
  "average-loss": "Average of last 10 steps",
  "loss-change": "Change since first step",
  "learning-rate": "Learning rate",
  "grad-norm": "Gradient norm",
  "dev-accuracy": "Dev accuracy",
};
const LIVE_KEYS = Object.keys(LIVE_LABELS);

afterEach(() => {
  vi.useRealTimers();
});

/* ============================================================================== AC4.5.7 */

describe("training page, Live numbers (AC4.5.7)", () => {
  it("AC4.5.7 shows a Live numbers panel with an h2 once the viewed run has a line", async () => {
    await openLive(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Live numbers" });
    expect(
      within(panel).getByRole("heading", { level: 2, name: "Live numbers" }),
    ).toBeInTheDocument();
    expect(panel.querySelector("dl")).not.toBeNull();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("AC4.5.7 shows progress, epoch, elapsed time, time remaining and the clock time the run should end", async () => {
    await openLive(MAIN_LINES);

    // Newest line: step 130 of 1744 = 7.45% -> 7.5%; epoch 2 * 130 / 1744 = 0.149; 309 s;
    // 2460 s = 41 min; stream time 20:31:07 + 41 min = 21:12:07.
    expect(values(currentLive(), ["progress", "epoch", "elapsed", "remaining", "finish"])).toEqual({
      progress: "130 / 1744 (7.5%)",
      epoch: "0.15",
      elapsed: "0:05:09",
      remaining: "~41 min",
      finish: "21:12:07",
    });
  });

  it("AC4.5.7 shows the speed over the last 11 step lines, leaving dev lines out", async () => {
    await openLive(MAIN_LINES);

    // Step lines 30..130: (309 - 129) s / (130 - 30) steps = 1.80 s/step = 33.3 steps/min.
    expect(stat(currentLive(), "speed").value).toBe(`1.80 s/step ${DOT} 33.3 steps/min`);
  });

  it("AC4.5.7 shows the latest, lowest and average of the last 10 steps loss and the change since the first step", async () => {
    await openLive(MAIN_LINES);

    // Newest 0.5, lowest 0.45; last 10 losses (steps 40..130) sum to 7.1 -> 0.71;
    // (0.5 - 2.0) / 2.0 = -75.0%.
    expect(values(currentLive(), ["loss", "lowest-loss", "average-loss", "loss-change"])).toEqual({
      loss: "0.5",
      "lowest-loss": "0.45",
      "average-loss": "0.71",
      "loss-change": `${MINUS}75.0%`,
    });
  });

  it("AC4.5.7 shows a loss that rose since the first step with a plus sign", async () => {
    await openLive([
      smallLine({ step: 5, loss: 1.0, elapsed_s: 10 }),
      smallLine({ step: 10, loss: 1.05, elapsed_s: 20 }),
    ]);

    expect(stat(currentLive(), "loss-change").value).toBe("+5.0%");
  });

  it("AC4.5.7 shows the learning rate while it is decaying", async () => {
    await openLive(MAIN_LINES);

    // Newest two non-null rates: 1.8e-4 then 1.7e-4.
    expect(stat(currentLive(), "learning-rate").value).toBe(`1.7e-4 ${DOT} decaying`);
  });

  it("AC4.5.7 shows the learning rate while it is warming up", async () => {
    await openLive([
      smallLine({ step: 5, learning_rate: 1e-4 }),
      smallLine({ step: 10, learning_rate: 1.5e-4 }),
    ]);

    expect(stat(currentLive(), "learning-rate").value).toBe(`1.5e-4 ${DOT} warming up`);
  });

  it("AC4.5.7 shows the learning rate while it is steady", async () => {
    await openLive([
      smallLine({ step: 5, learning_rate: 2e-4 }),
      smallLine({ step: 10, learning_rate: 2e-4 }),
    ]);

    expect(stat(currentLive(), "learning-rate").value).toBe(`2e-4 ${DOT} steady`);
  });

  it("AC4.5.7 shows the learning rate without a phase when only one line carries it", async () => {
    await openLive([smallLine({ step: 5, learning_rate: 2e-4 })]);

    expect(stat(currentLive(), "learning-rate").value).toBe("2e-4");
  });

  it("AC4.5.7 shows the newest and the highest gradient norm", async () => {
    await openLive(MAIN_LINES);

    // Newest 0.4213 -> 0.42; highest 1.34 (step 20) -> 1.3.
    expect(stat(currentLive(), "grad-norm").value).toBe("0.42 (highest 1.3)");
  });

  it("AC4.5.7 shows the latest and the best dev accuracy", async () => {
    await openLive(MAIN_LINES);

    // Dev lines: 64.1% at step 40, then 62.0% at step 80.
    expect(stat(currentLive(), "dev-accuracy").value).toBe("62.0% (best 64.1%)");
  });

  it("AC4.5.7 gives every number a label and a one-line plain-language meaning", async () => {
    await openLive(MAIN_LINES);

    const panel = currentLive();
    for (const key of LIVE_KEYS) {
      const root = panel.querySelector(`[data-stat="${key}"]`);
      expect(root, `data-stat="${key}"`).not.toBeNull();
      expect(root?.querySelectorAll("dt"), `${key} dt`).toHaveLength(1);
      expect(root?.querySelectorAll('dd[data-part="value"]'), `${key} value`).toHaveLength(1);
      expect(root?.querySelectorAll('dd[data-part="meaning"]'), `${key} meaning`).toHaveLength(1);
      const found = stat(panel, key);
      expect(found.label, `${key} label`).toBe(LIVE_LABELS[key]);
      expect(found.value, `${key} value`).not.toBe("");
      expect(found.meaning, `${key} meaning`).not.toBe("");
    }
  });

  it("AC4.5.7 reads — for a number no line carries and keeps the meaning", async () => {
    // An old line: no epoch, no grad_norm, no eta, no dev accuracy, one line only.
    await openLive([
      smallLine({ step: 5, loss: 1.2, learning_rate: 2e-4, elapsed_s: 10, eta_s: null }),
    ]);

    const panel = currentLive();
    expect(values(panel, LIVE_KEYS)).toEqual({
      progress: "5 / 100 (5.0%)",
      epoch: DASH,
      speed: DASH,
      elapsed: "0:00:10",
      remaining: DASH,
      finish: DASH,
      loss: "1.2",
      "lowest-loss": "1.2",
      "average-loss": "1.2",
      "loss-change": DASH,
      "learning-rate": "2e-4",
      "grad-norm": DASH,
      "dev-accuracy": DASH,
    });
    for (const key of LIVE_KEYS) expect(stat(panel, key).meaning, `${key} meaning`).not.toBe("");
  });

  it("AC4.5.7 reads — for the speed with a step difference of 0 and for the loss change from a first loss of 0", async () => {
    await openLive([
      smallLine({ step: 5, loss: 0, elapsed_s: 10 }),
      smallLine({ step: 5, loss: 0.5, elapsed_s: 12 }),
    ]);

    const panel = currentLive();
    expect(values(panel, ["speed", "loss-change", "loss", "lowest-loss", "average-loss"])).toEqual({
      speed: DASH,
      "loss-change": DASH,
      loss: "0.5",
      "lowest-loss": "0",
      "average-loss": "0.25",
    });
  });

  it("AC4.5.7 uses the newest non-null value when the newest line lacks it", async () => {
    await openLive([
      smallLine({
        step: 10,
        loss: 2.0,
        learning_rate: 1e-4,
        grad_norm: 0.9,
        epoch: 0.1,
        dev_accuracy: null,
        elapsed_s: 20,
        eta_s: 180,
      }),
      smallLine({
        step: 20,
        loss: 1.5,
        learning_rate: 1.5e-4,
        grad_norm: 0.8,
        epoch: 0.2,
        dev_accuracy: null,
        elapsed_s: 40,
        eta_s: 160,
      }),
      smallLine({
        step: 30,
        loss: null,
        learning_rate: null,
        grad_norm: null,
        epoch: null,
        dev_accuracy: null,
        elapsed_s: 60,
        eta_s: 140,
      }),
    ]);

    // Progress, elapsed, remaining and speed come from the newest line (step 30, 60 s, 140 s ->
    // ~2 min, (60 - 20) / (30 - 10) = 2.00 s/step); the others from the newest line that has them.
    expect(values(currentLive(), LIVE_KEYS)).toEqual({
      progress: "30 / 100 (30.0%)",
      epoch: "0.20",
      speed: `2.00 s/step ${DOT} 30.0 steps/min`,
      elapsed: "0:01:00",
      remaining: "~2 min",
      finish: "20:33:27",
      loss: "1.5",
      "lowest-loss": "1.5",
      "average-loss": "1.75",
      "loss-change": `${MINUS}25.0%`,
      "learning-rate": `1.5e-4 ${DOT} warming up`,
      "grad-norm": "0.8 (highest 0.9)",
      "dev-accuracy": DASH,
    });
  });

  it("AC4.5.7 shows reward, KL and answer length only when the lines carry them", async () => {
    const rl = "q06-grpo-dev-1";
    await openLive(
      [
        smallLine({ step: 5, reward: 0.2, kl: 0.01, answer_length: 210.4 }),
        smallLine({ step: 10, reward: 0.3527, kl: 0.0213, answer_length: 180.6 }),
      ],
      rl,
      "grpo",
    );

    const panel = currentLive();
    expect(values(panel, ["reward", "kl", "answer-length"])).toEqual({
      reward: "0.353",
      kl: "0.0213",
      "answer-length": "181",
    });
    expect([
      stat(panel, "reward").label,
      stat(panel, "kl").label,
      stat(panel, "answer-length").label,
    ]).toEqual(["Reward", "KL", "Answer length"]);
    for (const key of ["reward", "kl", "answer-length"]) {
      expect(stat(panel, key).meaning, `${key} meaning`).not.toBe("");
    }
  });

  it("AC4.5.7 leaves reward, KL and answer length out for a run whose lines do not carry them", async () => {
    await openLive(MAIN_LINES);

    const panel = currentLive();
    for (const key of ["reward", "kl", "answer-length"]) {
      expect(panel.querySelector(`[data-stat="${key}"]`), key).toBeNull();
    }
  });

  it("AC4.5.7 updates with each stream line without a reload", async () => {
    const api = await openLive(MAIN_LINES);
    expect(stat(currentLive(), "progress").value).toBe("130 / 1744 (7.5%)");
    const loads = api.listRuns.mock.calls.length;

    // The clock moves on and the next line says 39 min are left: 20:32:07 + 39 min = 21:11:07.
    vi.setSystemTime(new Date("2026-11-04T20:32:07Z"));
    api.stream.metric({ ...stepLine(NEXT_ROW), eta_s: 2340, run_id: LIVE }, MAIN_LINES.length + 1);

    // Step 140: 140 / 1744 = 8.03%, epoch 0.16, 327 s; speed over step lines 40..140 is
    // (327 - 150) / 100 = 1.77 s/step = 33.9 steps/min; last 10 losses (steps 50..140) sum to 6.4.
    expect(values(currentLive(), LIVE_KEYS)).toEqual({
      progress: "140 / 1744 (8.0%)",
      epoch: "0.16",
      speed: `1.77 s/step ${DOT} 33.9 steps/min`,
      elapsed: "0:05:27",
      remaining: "~39 min",
      finish: "21:11:07",
      loss: "0.4",
      "lowest-loss": "0.4",
      "average-loss": "0.64",
      "loss-change": `${MINUS}80.0%`,
      "learning-rate": `1.6e-4 ${DOT} decaying`,
      "grad-norm": "0.4 (highest 1.3)",
      "dev-accuracy": "62.0% (best 64.1%)",
    });
    expect(api.listRuns.mock.calls.length).toBe(loads);
    expect(api.stream.openCount).toBe(1);
  });

  it("AC4.5.7 is not shown while the live run has no lines and appears with its first line", async () => {
    pinClock();
    const api = liveApi();
    await openTraining(api, running());

    expect(await screen.findByText("Waiting for first step...")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Live numbers" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Live numbers" })).toBeNull();

    sendLines(api, MAIN_LINES.slice(0, 1));
    expect(await screen.findByRole("region", { name: "Live numbers" })).toBeInTheDocument();
    expect(stat(currentLive(), "progress").value).toBe("10 / 1744 (0.6%)");
  });

  it("AC4.5.7 is not shown when there is no run at all", async () => {
    renderPage("/training", { api: fakeApi() });

    expect(
      await screen.findByText("No run yet. Set the dials and press Start run."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Live numbers" })).toBeNull();
  });

  it("AC4.5.7 shows for a past run opened from Past runs, with the finish time reading —", async () => {
    await openPastRun(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Live numbers" });
    expect(values(panel, LIVE_KEYS)).toEqual({
      progress: "130 / 1744 (7.5%)",
      epoch: "0.15",
      speed: `1.80 s/step ${DOT} 33.3 steps/min`,
      elapsed: "0:05:09",
      remaining: "~41 min",
      finish: DASH,
      loss: "0.5",
      "lowest-loss": "0.45",
      "average-loss": "0.71",
      "loss-change": `${MINUS}75.0%`,
      "learning-rate": `1.7e-4 ${DOT} decaying`,
      "grad-norm": "0.42 (highest 1.3)",
      "dev-accuracy": "62.0% (best 64.1%)",
    });
    for (const key of LIVE_KEYS) expect(stat(panel, key).meaning, `${key} meaning`).not.toBe("");
  });

  it("AC4.5.7 is not shown for a past run without lines", async () => {
    await openPastRun([]);

    expect(await screen.findByText(`No curve recorded for ${PAST}`)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Live numbers" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Live numbers" })).toBeNull();
  });
});

/* ============================================================================== AC4.5.8 */

describe("training page, Recent steps (AC4.5.8)", () => {
  it("AC4.5.8 lists the 10 newest step lines newest first, each row carrying its step as data-step", async () => {
    await openLive(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Recent steps" });
    expect(within(panel).getByRole("heading", { level: 2, name: "Recent steps" })).toBeVisible();
    expect(within(panel).getByRole("table")).toBeInTheDocument();
    expect(shownSteps(panel)).toEqual([
      "130",
      "120",
      "110",
      "100",
      "90",
      "80",
      "70",
      "60",
      "50",
      "40",
    ]);
  });

  it("AC4.5.8 has the columns Step, Loss, Learning rate, Grad norm and Elapsed", async () => {
    await openLive(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Recent steps" });
    const headerRow = panel.querySelector("thead tr") ?? panel.querySelector("tr:not([data-step])");
    expect(headerRow, "a header row").not.toBeNull();
    expect(
      Array.from(headerRow?.querySelectorAll("th, td") ?? [], (cell) =>
        normalize(cell.textContent),
      ),
    ).toEqual(["Step", "Loss", "Learning rate", "Grad norm", "Elapsed"]);
  });

  it("AC4.5.8 formats step, loss, learning rate, gradient norm and elapsed time in each row", async () => {
    await openLive(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Recent steps" });
    expect(rowCells(panel, 130)).toEqual(["130", "0.5", "1.7e-4", "0.42", "0:05:09"]);
    expect(rowCells(panel, 120)).toEqual(["120", "0.45", "1.8e-4", "0.44", "0:04:51"]);
    expect(rowCells(panel, 100)).toEqual(["100", "0.55", "1.9e-4", "0.48", "0:04:15"]);
    expect(rowCells(panel, 40)).toEqual(["40", "1.1", "2e-4", "0.7", "0:02:30"]);
  });

  it("AC4.5.8 leaves lines that only carry a dev accuracy out of the table", async () => {
    const api = await openLive(MAIN_LINES);

    // The dev line after step 80 is not a second row for step 80 and kept step 40 in the 10.
    const panel = await screen.findByRole("region", { name: "Recent steps" });
    expect(panel.querySelectorAll('tr[data-step="80"]')).toHaveLength(1);
    expect(rowCells(panel, 80)).toEqual(["80", "0.7", "2e-4", "0.5", "0:03:39"]);
    expect(shownSteps(panel)).toHaveLength(10);

    // A dev line as the newest line adds no row and does not blank the top row.
    api.stream.metric({ ...devLine(130, 0.65, 312), run_id: LIVE }, MAIN_LINES.length + 1);
    const after = currentRecent();
    expect(shownSteps(after)).toHaveLength(10);
    expect(shownSteps(after)[0]).toBe("130");
    expect(rowCells(after, 130)).toEqual(["130", "0.5", "1.7e-4", "0.42", "0:05:09"]);
  });

  it("AC4.5.8 lists every step line when there are fewer than 10", async () => {
    await openLive(STEP_ROWS.slice(0, 3).map(stepLine));

    expect(shownSteps(await screen.findByRole("region", { name: "Recent steps" }))).toEqual([
      "30",
      "20",
      "10",
    ]);
  });

  it("AC4.5.8 reads — for a value a line does not carry", async () => {
    await openLive([
      // An old line: no grad_norm and no epoch field, no learning rate.
      smallLine({ step: 5, loss: 1.2, learning_rate: null, elapsed_s: 10 }),
      smallLine({ step: 6, loss: null, learning_rate: 2e-4, grad_norm: null, elapsed_s: 11 }),
    ]);

    const panel = await screen.findByRole("region", { name: "Recent steps" });
    expect(shownSteps(panel)).toEqual(["6", "5"]);
    expect(rowCells(panel, 6)).toEqual(["6", DASH, "2e-4", DASH, "0:00:11"]);
    expect(rowCells(panel, 5)).toEqual(["5", "1.2", DASH, DASH, "0:00:10"]);
  });

  it("AC4.5.8 puts a new stream line at the top without a reload", async () => {
    const api = await openLive(MAIN_LINES);
    expect(shownSteps(currentRecent())[0]).toBe("130");
    const loads = api.listRuns.mock.calls.length;

    api.stream.metric({ ...stepLine(NEXT_ROW), run_id: LIVE }, MAIN_LINES.length + 1);

    const panel = currentRecent();
    expect(shownSteps(panel)).toEqual([
      "140",
      "130",
      "120",
      "110",
      "100",
      "90",
      "80",
      "70",
      "60",
      "50",
    ]);
    expect(rowCells(panel, 140)).toEqual(["140", "0.4", "1.6e-4", "0.4", "0:05:27"]);
    expect(api.listRuns.mock.calls.length).toBe(loads);
    expect(api.stream.openCount).toBe(1);
  });

  it("AC4.5.8 sits above the Past runs list", async () => {
    await openLive(MAIN_LINES);

    const recent = await screen.findByRole("heading", { level: 2, name: "Recent steps" });
    const past = await screen.findByRole("heading", { level: 2, name: /past runs/i });
    expect(recent.compareDocumentPosition(past) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("AC4.5.8 lists the recent steps of a past run opened from Past runs", async () => {
    await openPastRun(MAIN_LINES);

    const panel = await screen.findByRole("region", { name: "Recent steps" });
    expect(shownSteps(panel)).toEqual([
      "130",
      "120",
      "110",
      "100",
      "90",
      "80",
      "70",
      "60",
      "50",
      "40",
    ]);
    expect(rowCells(panel, 130)).toEqual(["130", "0.5", "1.7e-4", "0.42", "0:05:09"]);
  });

  it("AC4.5.8 is not shown while the live run has no lines and appears with its first line", async () => {
    const api = liveApi();
    await openTraining(api, running());

    expect(await screen.findByText("Waiting for first step...")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Recent steps" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Recent steps" })).toBeNull();

    sendLines(api, MAIN_LINES.slice(0, 1));
    expect(await screen.findByRole("region", { name: "Recent steps" })).toBeInTheDocument();
    expect(shownSteps(currentRecent())).toEqual(["10"]);
  });

  it("AC4.5.8 is not shown for a past run without lines", async () => {
    await openPastRun([]);

    expect(await screen.findByText(`No curve recorded for ${PAST}`)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Recent steps" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Recent steps" })).toBeNull();
  });
});

/* ============================================================================= AC4.5.10 */

/** What `gpu()` shows: 6048 / 1024 = 5.9 GB of 8192 / 1024 = 8.0 GB, 161.7 W rounds to 162. */
const GPU_VALUES: Record<string, string> = {
  utilization: "97%",
  memory: "5.9 / 8.0 GB",
  temperature: "59 °C",
  power: "162 / 200 W",
  clock: "1920 / 2100 MHz",
};
const GPU_KEYS = Object.keys(GPU_VALUES);
const GPU_LABELS: Record<string, string> = {
  utilization: "Utilisation",
  memory: "Memory",
  temperature: "Temperature",
  power: "Power",
  clock: "Clock",
};
const GPU_NAME = "NVIDIA GeForce RTX 3060 Ti";

/** A `Gpu` that says it is not available: every figure null. */
function noGpu(reason: string): Gpu {
  return gpu({
    available: false,
    reason,
    name: null,
    utilization_pct: null,
    memory_used_mb: null,
    memory_total_mb: null,
    temperature_c: null,
    power_w: null,
    power_limit_w: null,
    sm_clock_mhz: null,
    sm_clock_max_mhz: null,
  });
}

/** A promise settled later by `resolve`. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

/** Fakes only the interval timers, so the 3-second refresh is driven by `advance`. */
function fakeIntervals(): void {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function expectGpuValues(expected: Record<string, string>): Promise<void> {
  await waitFor(() => {
    expect(values(currentGpu(), Object.keys(expected))).toEqual(expected);
  });
}

async function expectUnavailable(reason: string): Promise<void> {
  await waitFor(() => {
    expect(within(currentGpu()).getByText(`GPU stats unavailable: ${reason}`)).toBeInTheDocument();
  });
  expect(currentGpu().querySelectorAll("[data-stat]")).toHaveLength(0);
  expect(currentGpu().querySelector('[data-part="name"]')).toBeNull();
}

/** The page around the GPU panel still works: h1, the live band and a curve. */
async function expectPageStillWorks(api: FakeApi): Promise<void> {
  const user = userEvent.setup();
  await openTraining(api, running());
  sendLines(api, [
    metricsLine({ step: 40, total_steps: 400 }),
    metricsLine({ step: 80, total_steps: 400 }),
  ]);

  expect(screen.getByRole("heading", { level: 1, name: /training/i })).toBeInTheDocument();
  const band = await hourglassBand();
  await waitFor(() => expect(band).toHaveTextContent(/step 80 \/ 400/i));
  expect(seriesPoints(await showCurve(user, "Loss"))).toEqual([2]);
}

describe("training page, GPU panel (AC4.5.10)", () => {
  it("AC4.5.10 shows a GPU panel with the name, utilisation, memory, temperature, power and clock", async () => {
    renderPage("/training", { api: fakeApi({ getGpu: async () => gpu() }) });

    const panel = await screen.findByRole("region", { name: "GPU" });
    expect(within(panel).getByRole("heading", { level: 2, name: "GPU" })).toBeInTheDocument();
    await expectGpuValues(GPU_VALUES);
    expect(normalize(currentGpu().querySelector('p[data-part="name"]')?.textContent)).toBe(
      GPU_NAME,
    );
    expect(currentGpu().textContent).not.toMatch(/unavailable/i);
    expect(screen.queryByText("Reading the GPU…")).toBeNull();
  });

  it("AC4.5.10 gives every GPU figure a label and a one-line plain-language meaning", async () => {
    renderPage("/training", { api: fakeApi({ getGpu: async () => gpu() }) });
    await expectGpuValues(GPU_VALUES);

    const panel = currentGpu();
    for (const key of GPU_KEYS) {
      const root = panel.querySelector(`[data-stat="${key}"]`);
      expect(root?.querySelectorAll("dt"), `${key} dt`).toHaveLength(1);
      expect(root?.querySelectorAll('dd[data-part="value"]'), `${key} value`).toHaveLength(1);
      expect(root?.querySelectorAll('dd[data-part="meaning"]'), `${key} meaning`).toHaveLength(1);
      const found = stat(panel, key);
      expect(found.label, `${key} label`).toBe(GPU_LABELS[key]);
      expect(found.meaning, `${key} meaning`).not.toBe("");
    }
  });

  it("AC4.5.10 reads — for a figure the GPU does not report", async () => {
    const api = fakeApi({
      getGpu: async () =>
        gpu({
          utilization_pct: null,
          memory_used_mb: null,
          temperature_c: null,
          power_w: null,
          sm_clock_mhz: null,
        }),
    });
    renderPage("/training", { api });

    await expectGpuValues({
      utilization: DASH,
      memory: `${DASH} / 8.0 GB`,
      temperature: DASH,
      power: `${DASH} / 200 W`,
      clock: `${DASH} / 2100 MHz`,
    });
    for (const key of GPU_KEYS) {
      expect(stat(currentGpu(), key).meaning, `${key} meaning`).not.toBe("");
    }
  });

  it("AC4.5.10 reads — for the limit or total the GPU does not report", async () => {
    const api = fakeApi({
      getGpu: async () =>
        gpu({ memory_total_mb: null, power_limit_w: null, sm_clock_max_mhz: null }),
    });
    renderPage("/training", { api });

    await expectGpuValues({
      utilization: "97%",
      memory: `5.9 / ${DASH} GB`,
      temperature: "59 °C",
      power: `162 / ${DASH} W`,
      clock: `1920 / ${DASH} MHz`,
    });
  });

  it("AC4.5.10 reads GPU stats unavailable with the reason when the GPU says available is false", async () => {
    const api = fakeApi({ getGpu: async () => noGpu("nvidia-smi was not found") });
    renderPage("/training", { api });

    await expectUnavailable("nvidia-smi was not found");
    expect(screen.queryByText("Reading the GPU…")).toBeNull();
  });

  it("AC4.5.10 reads GPU stats unavailable with the default reason of the fake service", async () => {
    renderPage("/training", { api: fakeApi() });

    await expectUnavailable("No NVIDIA GPU in the tests");
  });

  it("AC4.5.10 reads GPU stats unavailable with the error message when the read fails", async () => {
    const api = fakeApi({
      getGpu: async () => {
        throw apiError("unreachable", UNREACHABLE_MESSAGE);
      },
    });
    renderPage("/training", { api });

    await expectUnavailable(UNREACHABLE_MESSAGE);
  });

  it("AC4.5.10 reads GPU stats unavailable with the message of a plain error", async () => {
    const api = fakeApi({
      getGpu: async () => {
        throw new Error("the GPU read exploded");
      },
    });
    renderPage("/training", { api });

    await expectUnavailable("the GPU read exploded");
  });

  it("AC4.5.10 reads Reading the GPU… until the first answer arrives", async () => {
    const first = deferred<Gpu>();
    const api = fakeApi({ getGpu: () => first.promise });
    renderPage("/training", { api });

    const panel = await screen.findByRole("region", { name: "GPU" });
    expect(within(panel).getByText("Reading the GPU…")).toBeInTheDocument();
    expect(panel.querySelectorAll("[data-stat]")).toHaveLength(0);
    expect(panel.textContent).not.toMatch(/unavailable/i);

    await act(async () => {
      first.resolve(gpu());
    });
    await expectGpuValues(GPU_VALUES);
    expect(screen.queryByText("Reading the GPU…")).toBeNull();
  });

  it("AC4.5.10 reads the GPU again every 3 seconds and shows the changed values", async () => {
    fakeIntervals();
    const answers = [
      gpu(),
      gpu({
        utilization_pct: 40,
        memory_used_mb: 2048,
        temperature_c: 52,
        power_w: 90.4,
        sm_clock_mhz: 1500,
      }),
      gpu({ utilization_pct: 12, power_w: 55, sm_clock_mhz: 900 }),
    ];
    let next = 0;
    const api = fakeApi({ getGpu: async () => answers[Math.min(next++, answers.length - 1)] });
    renderPage("/training", { api });

    await expectGpuValues(GPU_VALUES);
    const first = api.getGpu.mock.calls.length;
    expect(first).toBeGreaterThanOrEqual(1);

    await advance(2900);
    expect(api.getGpu.mock.calls.length).toBe(first);
    expect(stat(currentGpu(), "utilization").value).toBe("97%");

    await advance(100);
    expect(api.getGpu.mock.calls.length).toBe(first + 1);
    await expectGpuValues({
      utilization: "40%",
      memory: "2.0 / 8.0 GB",
      temperature: "52 °C",
      power: "90 / 200 W",
      clock: "1500 / 2100 MHz",
    });

    await advance(3000);
    expect(api.getGpu.mock.calls.length).toBe(first + 2);
    await expectGpuValues({
      utilization: "12%",
      memory: "5.9 / 8.0 GB",
      power: "55 / 200 W",
      clock: "900 / 2100 MHz",
    });
  });

  it("AC4.5.10 keeps reading every 3 seconds after an unavailable answer and shows the stats when the GPU returns", async () => {
    fakeIntervals();
    const api = fakeApi({ getGpu: async () => gpu() });
    api.getGpu.mockRejectedValueOnce(apiError("internal", "The GPU read failed"));
    api.getGpu.mockResolvedValueOnce(noGpu("nvidia-smi was not found"));
    renderPage("/training", { api });

    await expectUnavailable("The GPU read failed");
    await advance(3000);
    await expectUnavailable("nvidia-smi was not found");
    await advance(3000);
    await expectGpuValues(GPU_VALUES);
    expect(currentGpu().textContent).not.toMatch(/unavailable/i);
  });

  it("AC4.5.10 stops reading the GPU when the page is left", async () => {
    fakeIntervals();
    const api = fakeApi({ getGpu: async () => gpu() });
    const { unmount } = renderPage("/training", { api });
    await expectGpuValues(GPU_VALUES);
    const first = api.getGpu.mock.calls.length;

    await advance(3000);
    expect(api.getGpu.mock.calls.length).toBe(first + 1);

    unmount();
    const atLeave = api.getGpu.mock.calls.length;
    await advance(12000);
    expect(api.getGpu.mock.calls.length).toBe(atLeave);
  });

  it("AC4.5.10 shows the GPU panel on a page with no run", async () => {
    renderPage("/training", { api: fakeApi({ getGpu: async () => gpu() }) });

    expect(
      await screen.findByText("No run yet. Set the dials and press Start run."),
    ).toBeInTheDocument();
    await expectGpuValues(GPU_VALUES);
  });

  it("AC4.5.10 keeps the rest of the page working when the GPU read fails", async () => {
    const api = liveApi(LIVE, "sft", {
      getGpu: async () => {
        throw apiError("unreachable", UNREACHABLE_MESSAGE);
      },
    });
    await expectPageStillWorks(api);
    await expectUnavailable(UNREACHABLE_MESSAGE);
  });

  it("AC4.5.10 keeps the rest of the page working when the GPU is not available", async () => {
    const api = liveApi(LIVE, "sft", { getGpu: async () => noGpu("nvidia-smi was not found") });
    await expectPageStillWorks(api);
    await expectUnavailable("nvidia-smi was not found");
  });
});
