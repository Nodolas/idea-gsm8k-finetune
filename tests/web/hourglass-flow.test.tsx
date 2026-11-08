/**
 * Batch-10 part B (u5-website): the hourglass band keeps flowing while a run is RUNNING
 * (AC4.5.11) and shows evaluation progress while a run scores problems (AC4.5.12).
 *
 * jsdom has no 2D canvas context, so nothing here looks at pixels. The band's public surface is
 * the element carrying `data-fraction` (with `data-flow="on" | "off"`), its text and its
 * progressbar. The frame loop is observed through a stubbed `requestAnimationFrame` /
 * `cancelAnimationFrame` pair and a stubbed `performance.now()`, so frames run only when a test
 * steps them.
 */
import { act, render } from "@testing-library/react";

import { HourglassBand, type HourglassBandProps } from "@/components/hourglass-band";
import type { MetricsLine, Run, Status } from "@/lib/api";
import { fakeApi, metricsLine, Q06, run, serviceStatus, type FakeApi } from "@/test/fake-api";
import { setReducedMotion } from "@/test/setup";
import { renderPage, screen, waitFor } from "@/test/utils";

const LIVE = "q06-sft-dev-7";
const EVAL = "q06-base-dev-2";
const FRAME_MS = 16;

/** A controllable frame clock: frames run only when the test steps them. */
interface Frames {
  /** Callbacks requested and neither run nor cancelled yet. */
  readonly pending: number;
  /** How many frames were requested since the stub went in. */
  readonly requested: number;
  /** The ids passed to `cancelAnimationFrame`. */
  readonly cancelled: number[];
  /** Runs `count` frames, each one with every callback pending at its start. */
  step(count?: number): void;
  /** Steps frames until none is pending (at most `max`); true when the loop settled. */
  settle(max?: number): boolean;
}

let frames: Frames;

function stubFrames(): Frames {
  const pending = new Map<number, FrameRequestCallback>();
  const cancelled: number[] = [];
  let nextId = 1;
  let requested = 0;
  let clock = 1_000;

  vi.spyOn(performance, "now").mockImplementation(() => clock);
  const request = (callback: FrameRequestCallback): number => {
    const id = nextId;
    nextId += 1;
    requested += 1;
    pending.set(id, callback);
    return id;
  };
  const cancel = (id: number): void => {
    cancelled.push(id);
    pending.delete(id);
  };
  vi.stubGlobal("requestAnimationFrame", request);
  vi.stubGlobal("cancelAnimationFrame", cancel);
  if ((window as unknown) !== globalThis) {
    vi.spyOn(window, "requestAnimationFrame").mockImplementation(request);
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(cancel);
  }

  const step = (count = 1) => {
    for (let i = 0; i < count; i += 1) {
      clock += FRAME_MS;
      const batch = [...pending.values()];
      pending.clear();
      act(() => {
        for (const callback of batch) callback(clock);
      });
    }
  };

  return {
    get pending() {
      return pending.size;
    },
    get requested() {
      return requested;
    },
    cancelled,
    step,
    settle(max = 120) {
      for (let i = 0; i < max && pending.size > 0; i += 1) step();
      return pending.size === 0;
    },
  };
}

beforeEach(() => {
  frames = stubFrames();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Asserts that the band keeps asking for frames on every frame, with no new data arriving. */
function expectFlowing(): void {
  // Well past the eased fall (260 ms): a fall alone would have settled by now.
  frames.step(40);
  for (let i = 0; i < 5; i += 1) {
    const before = frames.requested;
    expect(frames.pending).toBeGreaterThan(0);
    frames.step();
    expect(frames.requested).toBeGreaterThan(before);
  }
  expect(frames.pending).toBeGreaterThan(0);
}

/** Asserts that the band asks for no frame once its drawing is settled. */
function expectSettled(): void {
  expect(frames.settle()).toBe(true);
  const before = frames.requested;
  frames.step(10);
  expect(frames.requested).toBe(before);
  expect(frames.pending).toBe(0);
}

// ---------------------------------------------------------------------------------------------
// The band on its own
// ---------------------------------------------------------------------------------------------

function bandProps(partial: Partial<HourglassBandProps> = {}): HourglassBandProps {
  return {
    status: "RUNNING",
    step: 30,
    totalSteps: 100,
    runId: LIVE,
    method: "SFT",
    model: "Qwen3-0.6B-Base",
    elapsedS: 300,
    etaS: 700,
    lastUpdate: null,
    paused: false,
    ...partial,
  };
}

/** The band element: the one carrying `data-fraction`. */
function bandNow(): HTMLElement {
  const band = document.querySelector<HTMLElement>("[data-fraction]");
  if (!band) throw new Error("no element with data-fraction (hourglass band)");
  return band;
}

/** The band's text with whitespace collapsed. */
function bandText(band: HTMLElement): string {
  return (band.textContent ?? "").replace(/\s+/g, " ");
}

// ---------------------------------------------------------------------------------------------
// The band on the training page
// ---------------------------------------------------------------------------------------------

function running(runId: string, partial: Partial<Status> = {}): Status {
  return serviceStatus({
    status: "RUNNING",
    run_id: runId,
    started_at: "2026-11-08T10:00:00Z",
    ...partial,
  });
}

function activeRun(runId: string, method: string): Run {
  return run({
    run_id: runId,
    model: Q06,
    method,
    dev_accuracy: null,
    minutes: null,
    date: null,
    started_at: "2026-11-08T10:00:00Z",
    status: "running",
  });
}

/** A fake Api whose service reports `status` and lists the active run. */
function liveApi(status: Status, method = "sft"): FakeApi {
  return fakeApi({
    getStatus: async () => status,
    listRuns: async () => ({
      runs: status.run_id ? [activeRun(status.run_id, method)] : [],
      skipped_rows: 0,
    }),
  });
}

/** Renders /training, waits for its stream, and sends `status` as the stream would. */
async function openTraining(api: FakeApi, status: Status | null, reducedMotion = false) {
  const result = renderPage("/training", { api, reducedMotion });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  if (status) api.stream.status(status);
  return result;
}

/** The band once it is on the page. */
async function hourglassBand(): Promise<HTMLElement> {
  return waitFor(() => bandNow());
}

function sendLines(api: FakeApi, runId: string, lines: MetricsLine[]): void {
  lines.forEach((line, i) => api.stream.metric({ ...line, run_id: runId }, i + 1));
}

const STEP_30: MetricsLine = metricsLine({
  step: 30,
  total_steps: 100,
  elapsed_s: 300,
  eta_s: 700,
});

/** A supervised run's lines up to its last training step. */
const TRAINED: MetricsLine[] = [
  metricsLine({ step: 200, total_steps: 400, loss: 1.1, elapsed_s: 600, eta_s: 600 }),
  metricsLine({ step: 400, total_steps: 400, loss: 0.8, elapsed_s: 1200, eta_s: 0 }),
];

describe("hourglass band flow (AC4.5.11)", () => {
  it("AC4.5.11 the band flows while RUNNING: data-flow on and frames keep coming with no new data", () => {
    render(<HourglassBand {...bandProps()} />);
    const band = bandNow();

    expect(band).toHaveAttribute("data-flow", "on");
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.3);
    expectFlowing();
    expect(bandNow()).toHaveAttribute("data-flow", "on");
    expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.3);
  });

  it("AC4.5.11 the band keeps flowing when the step share changes, and data-fraction follows the steps", () => {
    const { rerender } = render(<HourglassBand {...bandProps({ step: 30 })} />);
    frames.step(5);
    rerender(<HourglassBand {...bandProps({ step: 60 })} />);

    expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.6);
    expectFlowing();
    expect(bandNow()).toHaveAttribute("data-flow", "on");
  });

  it("AC4.5.11 the band does not flow under reduced motion: data-flow off and no repeating frame loop", () => {
    setReducedMotion(true);
    render(<HourglassBand {...bandProps()} />);

    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.3);
    expectSettled();
  });

  it("AC4.5.11 the band stops flowing when reduced motion is switched on while RUNNING", () => {
    render(<HourglassBand {...bandProps()} />);
    expect(bandNow()).toHaveAttribute("data-flow", "on");
    frames.step(3);

    act(() => setReducedMotion(true));

    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expectSettled();
  });

  it.each([
    ["IDLE", { status: "IDLE", runId: null, fraction: 1 }],
    ["STOPPED", { status: "STOPPED" }],
    ["FAILED", { status: "FAILED" }],
    ["loading", { status: null, runId: null, step: 0, totalSteps: 0 }],
  ] as Array<[string, Partial<HourglassBandProps>]>)(
    "AC4.5.11 the band does not flow while %s: data-flow off and no frame once settled",
    (_label, partial) => {
      render(<HourglassBand {...bandProps(partial)} />);

      expect(bandNow()).toHaveAttribute("data-flow", "off");
      expectSettled();
    },
  );

  it("AC4.5.11 unmounting a flowing band cancels its frame loop", () => {
    const { unmount } = render(<HourglassBand {...bandProps()} />);
    frames.step(5);
    expect(frames.pending).toBeGreaterThan(0);

    unmount();

    expect(frames.cancelled.length).toBeGreaterThan(0);
    expect(frames.pending).toBe(0);
    const before = frames.requested;
    frames.step(5);
    expect(frames.requested).toBe(before);
  });

  it("AC4.5.11 a status change from RUNNING to STOPPED cancels the loop", () => {
    const { rerender } = render(<HourglassBand {...bandProps()} />);
    frames.step(5);
    expect(frames.pending).toBeGreaterThan(0);

    rerender(<HourglassBand {...bandProps({ status: "STOPPED" })} />);

    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expect(frames.cancelled.length).toBeGreaterThan(0);
    expectSettled();
  });

  it("AC4.5.11 on the training page a RUNNING run flows between metrics lines and data-fraction stays the step share", async () => {
    const status = running(LIVE);
    const api = liveApi(status);
    await openTraining(api, status);
    sendLines(api, LIVE, [STEP_30]);
    await waitFor(() => expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.3));

    const band = await hourglassBand();
    expect(band).toHaveAttribute("data-flow", "on");
    expectFlowing();
    expect(bandNow()).toHaveAttribute("data-flow", "on");
    expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.3);
  });

  it("AC4.5.11 on the training page the band flows while the run scores problems", async () => {
    const status = running(EVAL, { evaluation: { split: "dev", scored: 120, total: 500 } });
    const api = liveApi(status, "base");
    await openTraining(api, status);
    await waitFor(() => expect(bandText(bandNow())).toContain("scoring dev 120 / 500"));

    expect(bandNow()).toHaveAttribute("data-flow", "on");
    expectFlowing();
  });

  it("AC4.5.11 on the training page under reduced motion a RUNNING run does not flow", async () => {
    const status = running(LIVE);
    const api = liveApi(status);
    await openTraining(api, status, true);
    sendLines(api, LIVE, [STEP_30]);
    await waitFor(() => expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.3));

    expect(bandNow()).toHaveAttribute("data-status", "RUNNING");
    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expectSettled();
  });

  it("AC4.5.11 on the training page an IDLE service does not flow", async () => {
    const api = fakeApi();
    await openTraining(api, serviceStatus());
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-status", "IDLE"));

    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expectSettled();
  });

  it("AC4.5.11 on the training page the band does not flow while the status is loading", async () => {
    const api = fakeApi({ getStatus: () => new Promise<Status>(() => {}) });
    renderPage("/training", { api });
    const band = await hourglassBand();

    expect(band).toHaveAttribute("data-status", "LOADING");
    expect(band).toHaveAttribute("data-flow", "off");
    expectSettled();
  });

  it("AC4.5.11 on the training page a run that stops or fails stops the flow", async () => {
    const status = running(LIVE);
    const api = liveApi(status);
    await openTraining(api, status);
    sendLines(api, LIVE, [STEP_30]);
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-flow", "on"));
    frames.step(5);

    api.stream.status(serviceStatus({ status: "STOPPED", run_id: LIVE, reason: "Stopped" }));
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-status", "STOPPED"));
    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expect(frames.cancelled.length).toBeGreaterThan(0);
    expectSettled();

    api.stream.status(running(LIVE));
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-flow", "on"));
    api.stream.status(
      serviceStatus({ status: "FAILED", run_id: LIVE, reason: "CUDA out of memory" }),
    );
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-status", "FAILED"));
    expect(bandNow()).toHaveAttribute("data-flow", "off");
    expectSettled();
  });

  it("AC4.5.11 leaving the training page cancels the band's frame loop", async () => {
    const status = running(LIVE);
    const api = liveApi(status);
    const { unmount } = await openTraining(api, status);
    sendLines(api, LIVE, [STEP_30]);
    await waitFor(() => expect(bandNow()).toHaveAttribute("data-flow", "on"));
    frames.step(5);

    unmount();

    expect(frames.pending).toBe(0);
    const before = frames.requested;
    frames.step(5);
    expect(frames.requested).toBe(before);
  });
});

describe("hourglass band evaluation progress (AC4.5.12)", () => {
  const SCORING = { split: "dev", scored: 120, total: 500 };

  it("AC4.5.12 the band takes an evaluation prop and shows scoring progress in place of the step counter", () => {
    render(<HourglassBand {...bandProps({ step: 400, totalSteps: 400, evaluation: SCORING })} />);
    const band = bandNow();

    expect(bandText(band)).toContain("scoring dev 120 / 500");
    expect(bandText(band)).toContain("24%");
    expect(bandText(band)).not.toContain("step 400 / 400");
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "120");
    expect(bar).toHaveAttribute("aria-valuemax", "500");
    expect(bar).toHaveAttribute("aria-valuetext", "scored 120 of 500 problems");
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.24);
  });

  it("AC4.5.12 on the training page an evaluation run shows scoring dev 120 / 500, 24% and the progressbar values", async () => {
    const status = running(EVAL, { evaluation: SCORING });
    const api = liveApi(status, "base");
    await openTraining(api, status);

    await waitFor(() => expect(bandText(bandNow())).toContain("scoring dev 120 / 500"));
    const band = bandNow();
    expect(bandText(band)).toContain("24%");
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "120");
    expect(bar).toHaveAttribute("aria-valuemax", "500");
    expect(bar).toHaveAttribute("aria-valuetext", "scored 120 of 500 problems");
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.24);
  });

  it("AC4.5.12 an evaluation run with no metrics lines reads Scoring the dev split, not Waiting for first step...", async () => {
    const status = running(EVAL, { evaluation: SCORING });
    const api = liveApi(status, "base");
    await openTraining(api, status);

    await waitFor(() => expect(bandText(bandNow())).toContain("Scoring the dev split"));
    expect(bandText(bandNow())).not.toContain("Training done");
    expect(screen.queryByText("Waiting for first step...")).not.toBeInTheDocument();
    expect(bandText(bandNow())).not.toContain("Waiting for first step");
  });

  it("AC4.5.12 a trained run that scores reads Training done, scoring the dev split, with scored / total as the fraction", async () => {
    const status = running(LIVE);
    const api = liveApi(status);
    await openTraining(api, status);
    sendLines(api, LIVE, TRAINED);
    await waitFor(() => expect(bandText(bandNow())).toContain("step 400 / 400"));

    api.stream.status(running(LIVE, { evaluation: SCORING }));

    await waitFor(() =>
      expect(bandText(bandNow())).toContain("Training done, scoring the dev split"),
    );
    const band = bandNow();
    expect(bandText(band)).toContain("scoring dev 120 / 500");
    expect(bandText(band)).toContain("24%");
    expect(bandText(band)).not.toContain("step 400 / 400");
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.24);
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "120");
    expect(bar).toHaveAttribute("aria-valuemax", "500");
    expect(bar).toHaveAttribute("aria-valuetext", "scored 120 of 500 problems");
  });

  it("AC4.5.12 a later status event with more problems scored updates the counter", async () => {
    const status = running(EVAL, { evaluation: SCORING });
    const api = liveApi(status, "base");
    await openTraining(api, status);
    await waitFor(() => expect(bandText(bandNow())).toContain("scoring dev 120 / 500"));

    api.stream.status(running(EVAL, { evaluation: { split: "dev", scored: 250, total: 500 } }));

    await waitFor(() => expect(bandText(bandNow())).toContain("scoring dev 250 / 500"));
    expect(bandText(bandNow())).toContain("50%");
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "250");
    expect(bar).toHaveAttribute("aria-valuetext", "scored 250 of 500 problems");
    expect(Number(bandNow().getAttribute("data-fraction"))).toBeCloseTo(0.5);
  });

  it("AC4.5.12 with evaluation null the band shows the step counter as before", async () => {
    const status = running(LIVE, { evaluation: null });
    const api = liveApi(status);
    await openTraining(api, status);
    sendLines(api, LIVE, [STEP_30]);

    await waitFor(() => expect(bandText(bandNow())).toContain("step 30 / 100"));
    const band = bandNow();
    expect(bandText(band)).toContain("30%");
    expect(bandText(band)).not.toContain("scoring");
    expect(bandText(band)).not.toMatch(/Scoring the|Training done/);
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "30");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-valuetext", "step 30 of 100");
    expect(Number(band.getAttribute("data-fraction"))).toBeCloseTo(0.3);
  });
});
