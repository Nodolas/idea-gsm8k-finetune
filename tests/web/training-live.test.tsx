/**
 * Part W3 (u5-website): the training page's live view, US4.5 (AC4.5.1-AC4.5.5; AC4.5.6 is
 * [manual]) and the failure panel of US3.5. The page reads only the fake Api: `getStatus` and
 * `listRuns` on load, `getMetrics` for a past run, and C7 events pushed with `api.stream.*`.
 * W4's run controls (dials, confirm, queue) are tested in run-controls.test.tsx, not here.
 */
import type { MetricsLine, Run, Status } from "@/lib/api";
import { fakeApi, metricsLine, Q06, Q17, run, serviceStatus, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

const LIVE = "q06-sft-dev-3";

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
function liveApi(runId: string = LIVE, method = "sft"): FakeApi {
  return fakeApi({
    getStatus: async () => running(runId),
    listRuns: async () => ({ runs: [activeRun(runId, method)], skipped_rows: 0 }),
  });
}

/** Renders /training, waits for its stream, and sends `status` as the stream would. */
async function openTraining(api: FakeApi, status?: Status) {
  const result = renderPage("/training", { api });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  if (status) api.stream.status(status);
  return result;
}

/** The hourglass band: the element carrying `data-fraction` (W3 interface). */
async function hourglassBand(): Promise<HTMLElement> {
  return waitFor(() => {
    const band = document.querySelector<HTMLElement>("[data-fraction]");
    if (!band) throw new Error("no element with data-fraction (hourglass band) yet");
    return band;
  });
}

function mainText(): string {
  return document.querySelector("main#main")?.textContent ?? "";
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

/** Four lines of a supervised run: three logging steps, then a dev evaluation at step 120. */
const SFT_LINES: MetricsLine[] = [
  metricsLine({
    step: 40,
    total_steps: 400,
    loss: 1.8,
    learning_rate: 2e-4,
    elapsed_s: 380,
    eta_s: 3420,
  }),
  metricsLine({
    step: 80,
    total_steps: 400,
    loss: 1.1,
    learning_rate: 1.9e-4,
    elapsed_s: 760,
    eta_s: 3040,
  }),
  metricsLine({
    step: 120,
    total_steps: 400,
    loss: 0.94,
    learning_rate: 1.8e-4,
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

afterEach(() => {
  vi.useRealTimers();
});

describe("training page, live view (US4.5)", () => {
  it("AC4.5.1 draws loss, learning rate and dev accuracy curves with step, elapsed time and time left for a supervised run", async () => {
    const user = userEvent.setup();
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES);

    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(band).toHaveTextContent(/30%/);
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.3);
    const progress = within(band).getByRole("progressbar", { name: "Run progress" });
    expect(progress).toHaveAttribute("aria-valuenow", "120");
    expect(progress).toHaveAttribute("aria-valuemax", "400");
    // Elapsed 1150 s and 2640 s left: h:mm as drawn in the mockup, or formatDuration's minutes.
    expect(band).toHaveTextContent(/elapsed\s*(0:19|~?19 min)/i);
    expect(band).toHaveTextContent(/left\s*(~?0:44|~?44 min)/i);

    expect(seriesPoints(await showCurve(user, "Loss"))).toEqual([3]);
    expect(seriesPoints(await showCurve(user, "Learning rate"))).toEqual([3]);
    expect(seriesPoints(await showCurve(user, "Dev accuracy"))).toEqual([1]);
    expect(screen.queryByRole("tab", { name: "Reward" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "KL" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Answer length" })).not.toBeInTheDocument();
  });

  it("AC4.5.1 also draws reward, KL and answer length curves for a reinforcement-learning run", async () => {
    const user = userEvent.setup();
    const rl = "q06-grpo-dev-1";
    const api = liveApi(rl, "grpo");
    await openTraining(api, running(rl));
    sendLines(
      api,
      [
        metricsLine({ step: 5, total_steps: 50, reward: 0.2, kl: 0.01, answer_length: 210 }),
        metricsLine({ step: 10, total_steps: 50, reward: 0.35, kl: 0.02, answer_length: 180 }),
      ],
      rl,
    );

    expect(seriesPoints(await showCurve(user, "Loss"))).toEqual([2]);
    expect(seriesPoints(await showCurve(user, "Learning rate"))).toEqual([2]);
    expect(await screen.findByRole("tab", { name: "Dev accuracy" })).toBeInTheDocument();
    expect(seriesPoints(await showCurve(user, "Reward"))).toEqual([2]);
    expect(seriesPoints(await showCurve(user, "KL"))).toEqual([2]);
    expect(seriesPoints(await showCurve(user, "Answer length"))).toEqual([2]);
  });

  it("AC4.5.1 reads No estimate yet when a line has no time remaining", async () => {
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, [metricsLine({ step: 3, total_steps: 400, eta_s: null })]);

    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 3 \/ 400/i));
    expect(band).toHaveTextContent("No estimate yet");
  });

  it("AC4.5.2 a new stream line updates the curves and the step counter without a reload", async () => {
    const user = userEvent.setup();
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES.slice(0, 2));

    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 80 \/ 400/i));
    const loss = await showCurve(user, "Loss");
    expect(seriesPoints(loss)).toEqual([2]);
    const loadsBefore = api.listRuns.mock.calls.length;

    api.stream.metric({ ...SFT_LINES[2], run_id: LIVE }, 3);

    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(within(band).getByRole("progressbar", { name: "Run progress" })).toHaveAttribute(
      "aria-valuenow",
      "120",
    );
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.3);
    expect(seriesPoints(screen.getByRole("figure", { name: /^Loss curve/ }))).toEqual([3]);
    // The same band is still on screen and nothing was fetched again: no reload.
    expect(document.querySelector("[data-fraction]")).toBe(band);
    expect(api.listRuns.mock.calls.length).toBe(loadsBefore);
    expect(api.stream.openCount).toBe(1);
  });

  it("AC4.5.2 drops a replayed line with the same run id and line number", async () => {
    const user = userEvent.setup();
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES.slice(0, 3));
    // A reconnect replays the active run's lines from line 1 (batch-4 Settled details).
    sendLines(api, SFT_LINES.slice(0, 3));

    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(seriesPoints(await showCurve(user, "Loss"))).toEqual([3]);

    api.stream.metric(
      { ...metricsLine({ step: 160, total_steps: 400, loss: 0.9 }), run_id: LIVE },
      4,
    );
    await waitFor(() => expect(band).toHaveTextContent(/step 160 \/ 400/i));
    expect(seriesPoints(screen.getByRole("figure", { name: /^Loss curve/ }))).toEqual([4]);
  });

  it("AC4.5.2 keeps line 1 of a new run even after line 1 of the previous run", async () => {
    const user = userEvent.setup();
    const next = "q06-sft-dev-4";
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES.slice(0, 2));
    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 80 \/ 400/i));

    api.getStatus.mockResolvedValue(running(next));
    api.listRuns.mockResolvedValue({ runs: [activeRun(next)], skipped_rows: 0 });
    api.stream.status(running(next));
    api.stream.metric(
      { ...metricsLine({ step: 10, total_steps: 200, loss: 2.1 }), run_id: next },
      1,
    );

    await waitFor(() => expect(band).toHaveTextContent(/step 10 \/ 200/i));
    expect(band).toHaveTextContent(next);
    expect(seriesPoints(await showCurve(user, "Loss"))).toEqual([1]);
  });

  it("AC4.5.2 opens the stream once and closes it when the page is left", async () => {
    const api = liveApi();
    const { unmount } = await openTraining(api, running());
    sendLines(api, SFT_LINES);
    api.stream.status(running());
    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(api.stream.openCount).toBe(1);

    unmount();
    expect(api.stream.isOpen).toBe(false);
  });

  it("AC4.5.3 shows Live updates paused, reconnecting with the last update time when the stream drops, and clears when it opens again", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-04T20:31:07Z") });
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES.slice(0, 3));
    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(mainText()).not.toMatch(/Live updates paused/);

    vi.setSystemTime(new Date("2026-11-04T20:31:40Z"));
    api.stream.drop();

    await waitFor(() => expect(mainText()).toMatch(/Live updates paused, reconnecting/));
    expect(mainText()).toMatch(/last update 20:31:07/);
    expect(mainText()).not.toMatch(/20:31:40/);
    // The band keeps the last known progress while paused.
    expect(Number((await hourglassBand()).getAttribute("data-fraction"))).toBeCloseTo(0.3);

    api.stream.open();
    await waitFor(() => expect(mainText()).not.toMatch(/Live updates paused/));
  });

  it("AC4.5.3 the paused line also clears on the next event after a drop", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-04T20:31:07Z") });
    const api = liveApi();
    await openTraining(api, running());
    sendLines(api, SFT_LINES.slice(0, 2));
    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/step 80 \/ 400/i));

    api.stream.drop();
    await waitFor(() => expect(mainText()).toMatch(/Live updates paused, reconnecting/));

    vi.setSystemTime(new Date("2026-11-04T20:31:12Z"));
    api.stream.metric({ ...SFT_LINES[2], run_id: LIVE }, 3);
    await waitFor(() => expect(band).toHaveTextContent(/step 120 \/ 400/i));
    expect(mainText()).not.toMatch(/Live updates paused/);
  });

  it("AC4.5.3 shows the paused line even when the stream drops before any update", async () => {
    const api = liveApi();
    await openTraining(api);
    api.stream.drop();
    await waitFor(() => expect(mainText()).toMatch(/Live updates paused, reconnecting/));
  });

  it("AC4.5.4 shows Waiting for first step... while a started run has no metrics line, then the step", async () => {
    const api = liveApi();
    await openTraining(api, running());

    expect(await screen.findByText("Waiting for first step...")).toBeInTheDocument();
    const band = await hourglassBand();
    expect(Number(band.getAttribute("data-fraction"))).toBe(0);
    expect(screen.queryByText("No run yet. Set the dials and press Start run.")).toBeNull();

    sendLines(api, SFT_LINES.slice(0, 1));
    await waitFor(() => expect(band).toHaveTextContent(/step 40 \/ 400/i));
    expect(screen.queryByText("Waiting for first step...")).toBeNull();
  });

  it("AC4.5.4 with no run ever reads No run yet. Set the dials and press Start run. and the past runs list reads None yet", async () => {
    const api = fakeApi();
    renderPage("/training", { api });

    expect(
      await screen.findByText("No run yet. Set the dials and press Start run."),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: /past runs/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("None yet")).toBeInTheDocument();
    expect(screen.queryByText("Waiting for first step...")).toBeNull();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("AC4.5.4 does not claim No run yet when past runs exist", async () => {
    const api = fakeApi({
      listRuns: async () => ({
        runs: [run({ run_id: "q06-sft-dev-2", started_at: "2026-11-04T20:10:00Z" })],
        skipped_rows: 0,
      }),
    });
    renderPage("/training", { api });

    await pastRunRow("q06-sft-dev-2");
    expect(screen.queryByText("No run yet. Set the dials and press Start run.")).toBeNull();
    expect(screen.queryByText("None yet")).toBeNull();
  });
});

describe("training page, past runs (AC4.5.5)", () => {
  const PAST: Run[] = [
    activeRun("q17-sft-dev-1", "sft", Q17),
    run({
      run_id: "q17-sft-dev-2",
      model: Q17,
      dev_accuracy: null,
      minutes: null,
      date: null,
      started_at: null,
      status: "queued",
    }),
    run({
      run_id: "q06-sft-dev-2",
      dev_accuracy: 0.47,
      minutes: 23.4,
      date: "2026-11-04T20:33:24Z",
      started_at: "2026-11-04T20:10:00Z",
      status: "finished",
    }),
    run({
      run_id: "q06-sft-dev-1",
      dev_accuracy: null,
      minutes: 7,
      date: "2026-11-04T19:09:00Z",
      started_at: "2026-11-04T19:02:00Z",
      status: "stopped",
    }),
    run({
      run_id: "q06-base-dev-1",
      method: "base",
      dev_accuracy: 0.5,
      minutes: 2,
      date: "2026-11-03T21:42:00Z",
      started_at: null,
      status: "failed",
    }),
  ];

  const STOPPED_LINES: MetricsLine[] = [
    metricsLine({ step: 10, total_steps: 400, loss: 1.9, run_id: "q06-sft-dev-1" }),
    metricsLine({ step: 20, total_steps: 400, loss: 1.5, run_id: "q06-sft-dev-1" }),
    metricsLine({ step: 30, total_steps: 400, loss: 1.3, run_id: "q06-sft-dev-1" }),
  ];

  function pastApi(): FakeApi {
    return fakeApi({
      getStatus: async () => running("q17-sft-dev-1"),
      listRuns: async () => ({ runs: PAST.map((r) => ({ ...r })), skipped_rows: 0 }),
      getMetrics: async (id: string) =>
        id === "q06-sft-dev-1" ? { lines: STOPPED_LINES, next: 3 } : { lines: [], next: 0 },
    });
  }

  it("AC4.5.5 lists past runs with run id, status word and icon, start time, minutes and dev accuracy", async () => {
    renderPage("/training", { api: pastApi() });

    const finished = await pastRunRow("q06-sft-dev-2");
    expect(screen.getByRole("columnheader", { name: /run id/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /status/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /started/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /min/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /dev/i })).toBeInTheDocument();

    const finishedWord = within(finished).getByText("FINISHED");
    expect(finishedWord.closest("td")?.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(within(finished).getByText("2026-11-04 20:10")).toBeInTheDocument();
    expect(within(finished).getByText("23")).toBeInTheDocument();
    expect(within(finished).getByText("47.0%")).toBeInTheDocument();

    const stopped = await pastRunRow("q06-sft-dev-1");
    expect(within(stopped).getByText("STOPPED")).toBeInTheDocument();
    expect(within(stopped).getByText("2026-11-04 19:02")).toBeInTheDocument();
    expect(within(stopped).getByText("7")).toBeInTheDocument();
    expect(within(stopped).getByText("--")).toBeInTheDocument();

    const failed = await pastRunRow("q06-base-dev-1");
    const failedWord = within(failed).getByText("FAILED");
    expect(failedWord.closest("td")?.querySelector('[aria-hidden="true"]')).not.toBeNull();
    // No start time: "--"; dev accuracy 50.0%.
    expect(within(failed).getByText("--")).toBeInTheDocument();
    expect(within(failed).getByText("50.0%")).toBeInTheDocument();

    expect(within(await pastRunRow("q17-sft-dev-1")).getByText("RUNNING")).toBeInTheDocument();
    expect(within(await pastRunRow("q17-sft-dev-2")).getByText("QUEUED")).toBeInTheDocument();
  });

  it("AC4.5.5 opening a past run shows its curves labelled with its run id, and Back to live returns", async () => {
    const user = userEvent.setup();
    const api = pastApi();
    renderPage("/training", { api });
    await pastRunRow("q06-sft-dev-1");

    await user.click(control("Open q06-sft-dev-1"));

    expect(
      await screen.findByRole("heading", { name: /Viewing q06-sft-dev-1/ }),
    ).toBeInTheDocument();
    expect(api.getMetrics.mock.calls.some(([id]) => id === "q06-sft-dev-1")).toBe(true);
    const loss = await showCurve(user, "Loss");
    expect(loss).toHaveAccessibleName(/^Loss curve: .*q06-sft-dev-1/);
    expect(seriesPoints(loss)).toEqual([3]);

    await user.click(screen.getByRole("button", { name: "Back to live" }));
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: /Viewing q06-sft-dev-1/ })).toBeNull(),
    );
  });

  it("AC4.5.5 opening a past run moves focus to the curves heading", async () => {
    const user = userEvent.setup();
    renderPage("/training", { api: pastApi() });
    await pastRunRow("q06-sft-dev-2");

    await user.click(control("Open q06-sft-dev-2"));

    const heading = await screen.findByRole("heading", { name: /Viewing q06-sft-dev-2/ });
    await waitFor(() => expect(heading).toHaveFocus());
  });

  it("AC4.5.5 a past run without metrics reads No curve recorded for its run id", async () => {
    const user = userEvent.setup();
    renderPage("/training", { api: pastApi() });
    await pastRunRow("q06-base-dev-1");

    await user.click(control("Open q06-base-dev-1"));

    expect(await screen.findByText("No curve recorded for q06-base-dev-1")).toBeInTheDocument();
  });
});

describe("training page, failed run (US3.5)", () => {
  const LOG = [
    "Step 36/400 loss 1.12",
    "Traceback (most recent call last):",
    "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB",
  ];

  /** The service's shape after a failed run: IDLE, with the failed run in `last_run`. */
  function failedStatus(reason: string, logTail: string[]): Status {
    return serviceStatus({
      status: "IDLE",
      last_run: serviceStatus({
        status: "FAILED",
        run_id: "q06-base-dev-1",
        reason,
        log_tail: logTail,
        started_at: "2026-11-03T21:40:00Z",
      }),
    });
  }

  it("AC3.5.1 shows a failed run's reason and opens its last log lines from Show log", async () => {
    const user = userEvent.setup();
    const status = failedStatus("GPU out of memory", LOG);
    const api = fakeApi({
      getStatus: async () => status,
      listRuns: async () => ({
        runs: [run({ run_id: "q06-base-dev-1", method: "base", status: "failed" })],
        skipped_rows: 0,
      }),
    });
    await openTraining(api, status);

    const band = await hourglassBand();
    await waitFor(() => expect(band).toHaveTextContent(/FAILED/));
    expect(band).toHaveTextContent("GPU out of memory");

    const showLog = await waitFor(() => control("Show log"));
    await user.click(showLog);

    const dialog = await screen.findByRole("dialog", { name: /Why q06-base-dev-1 failed/ });
    expect(dialog).toHaveTextContent("GPU out of memory");
    for (const line of LOG) expect(dialog).toHaveTextContent(line);

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(control("Show log")).toHaveFocus());
  });

  it("AC3.5.3 shows Run log could not be read naming the file", async () => {
    const reason = "Run log could not be read: outputs/q06-base-dev-1/run.log";
    const status = failedStatus(reason, []);
    const api = fakeApi({ getStatus: async () => status });
    await openTraining(api, status);

    await waitFor(() => expect(mainText()).toContain(reason));
  });
});
