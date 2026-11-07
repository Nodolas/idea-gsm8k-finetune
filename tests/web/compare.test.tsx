/**
 * Part W2 (u5-website): comparing two picked runs on the scores page (AC4.4.1-AC4.4.3). Settings
 * come from `getRun`, curves from `getMetrics`; a missing metrics file reads as no lines (C2).
 * Curves are asserted through MetricChart's figure label and its data-series markers.
 */
import type { Api, MetricsPage, RunConfig, RunDetail, RunList } from "@/lib/api";
import { Q06, Q17, fakeApi, metricsLine, run } from "@/test/fake-api";
import { renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

type User = ReturnType<typeof userEvent.setup>;

const BL17 = run({
  run_id: "q17-base-dev-1",
  model: Q17,
  method: "base",
  dev_accuracy: 0.587,
  test_accuracy: 0.579,
  gain: null,
  minutes: 24,
  date: "2026-11-02T09:00:00Z",
});
const RUN_A = run({
  run_id: "q17-sft-dev-2",
  model: Q17,
  method: "sft",
  dev_accuracy: 0.681,
  gain: 0.094,
  minutes: 52,
  date: "2026-11-05T12:00:00Z",
});
const RUN_B = run({
  run_id: "q17-sft-dev-1",
  model: Q17,
  method: "sft",
  dev_accuracy: 0.659,
  gain: 0.072,
  minutes: 49,
  date: "2026-11-04T12:00:00Z",
});
const RUN_C = run({
  run_id: "q06-sft-dev-3",
  model: Q06,
  method: "sft",
  dev_accuracy: 0.47,
  gain: 0.057,
  minutes: 23,
  date: "2026-11-04T15:00:00Z",
});
const RUNS = [BL17, RUN_A, RUN_B, RUN_C];

function sftConfig(runId: string, learningRate: number): RunConfig {
  return {
    v: 1,
    run_id: runId,
    model: Q17,
    method: "sft",
    split: "dev",
    learning_rate: learningRate,
    epochs: 1,
    lora_rank: 16,
    lora_alpha: 32,
    max_seq_len: 512,
    train_examples: "all",
    batch_size: 4,
    warmup_ratio: 0.03,
    seed: 42,
    answer_format: "step-by-step",
  };
}

/** Run A differs from run B only in its learning rate. */
const CONFIGS: Record<string, RunConfig> = {
  "q17-sft-dev-2": sftConfig("q17-sft-dev-2", 2e-4),
  "q17-sft-dev-1": sftConfig("q17-sft-dev-1", 1e-4),
  "q06-sft-dev-3": { ...sftConfig("q06-sft-dev-3", 2e-4), model: Q06 },
};

const LINES: Record<string, MetricsPage> = {
  "q17-sft-dev-2": {
    lines: [
      metricsLine({ step: 1, total_steps: 3, loss: 1.4 }),
      metricsLine({ step: 2, total_steps: 3, loss: 1.0 }),
      metricsLine({ step: 3, total_steps: 3, loss: 0.8 }),
    ],
    next: 3,
  },
  "q17-sft-dev-1": {
    lines: [
      metricsLine({ step: 1, total_steps: 2, loss: 1.5 }),
      metricsLine({ step: 2, total_steps: 2, loss: 1.1 }),
    ],
    next: 2,
  },
};

const NO_LINES: MetricsPage = { lines: [], next: 0 };

/** Runs, folders and metrics; `withoutMetrics` lists runs that have no metrics.jsonl. */
function compareApi(withoutMetrics: string[] = []) {
  return fakeApi({
    listRuns: async (): Promise<RunList> => ({ runs: RUNS, skipped_rows: 0 }),
    getRun: async (id: string): Promise<RunDetail> => ({
      run_id: id,
      config: CONFIGS[id] ?? {},
      status: { status: "finished" },
      timings: {},
    }),
    getMetrics: async (id: string): Promise<MetricsPage> =>
      withoutMetrics.includes(id) ? NO_LINES : (LINES[id] ?? NO_LINES),
  } satisfies Partial<Api>);
}

async function ready(): Promise<void> {
  await screen.findByRole("table", { name: /Highest scores, ranked by dev accuracy/ });
}

function pickBox(runId: string): HTMLElement {
  return screen.getByRole("checkbox", { name: `Pick ${runId}` });
}

function compareButton(): HTMLElement {
  return screen.getByRole("button", { name: /^Compare/ });
}

async function pick(user: User, ...ids: string[]): Promise<void> {
  for (const id of ids) await user.click(pickBox(id));
}

/** Picks `first` then `second`, presses Compare and returns the compare section. */
async function openCompare(user: User, first: string, second: string): Promise<HTMLElement> {
  await pick(user, first, second);
  await user.click(compareButton());
  return screen.findByRole("region", { name: new RegExp(`Compare ${first} vs ${second}`) });
}

/** The settings row of a dial inside the compare section. */
function settingsRow(region: HTMLElement, label: string): HTMLElement {
  const row = within(region)
    .getAllByRole("row")
    .find((r) => within(r).queryAllByText(label).length > 0);
  if (!row) throw new Error(`No settings row for ${label}`);
  return row;
}

function seriesPoints(scope: HTMLElement): string[] {
  return Array.from(scope.querySelectorAll("[data-series]")).map(
    (s) => s.getAttribute("data-points") ?? "",
  );
}

describe("compare two runs", () => {
  it("AC4.4.1 shows settings side by side, the changed dial by text, the signed difference and both curves", async () => {
    const user = userEvent.setup();
    const api = compareApi();
    renderPage("/scores", { api });
    await ready();

    const region = await openCompare(user, "q17-sft-dev-2", "q17-sft-dev-1");

    expect(api.getRun).toHaveBeenCalledWith("q17-sft-dev-2");
    expect(api.getRun).toHaveBeenCalledWith("q17-sft-dev-1");

    const lr = await waitFor(() => settingsRow(region, "Learning rate"));
    expect(lr.textContent ?? "").toMatch(/2e-4|0\.0002/);
    expect(lr.textContent ?? "").toMatch(/1e-4|0\.0001/);
    expect(lr.textContent ?? "").toMatch(/changed/i);
    expect(settingsRow(region, "Epochs").textContent ?? "").not.toMatch(/changed/i);
    expect(settingsRow(region, "LoRA rank").textContent ?? "").not.toMatch(/changed/i);

    expect(region).toHaveTextContent("+2.2 pts");

    const figure = await within(region).findByRole("figure", { name: /^Loss curve:/ });
    const name = figure.getAttribute("aria-label") ?? "";
    expect(name).toContain("q17-sft-dev-2");
    expect(name).toContain("q17-sft-dev-1");
    await waitFor(() => expect(seriesPoints(figure).sort()).toEqual(["2", "3"]));
  });

  it("AC4.4.1 signs a negative accuracy difference with a minus (U+2212)", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: compareApi() });
    await ready();

    const region = await openCompare(user, "q17-sft-dev-1", "q17-sft-dev-2");

    await waitFor(() => expect(region).toHaveTextContent("−2.2 pts"));
    expect(region.textContent ?? "").not.toContain("-2.2 pts");
  });

  it("AC4.4.2 disables Compare with a hint until two runs are picked", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: compareApi() });
    await ready();

    expect(compareButton()).toBeDisabled();
    expect(screen.getByText(/Pick two runs to compare/)).toBeInTheDocument();

    await pick(user, "q17-sft-dev-2");
    expect(pickBox("q17-sft-dev-2")).toBeChecked();
    expect(compareButton()).toBeDisabled();
    await user.click(compareButton());
    expect(screen.queryByRole("region", { name: /^Compare/ })).not.toBeInTheDocument();

    await pick(user, "q17-sft-dev-1");
    expect(compareButton()).toBeEnabled();

    await pick(user, "q17-sft-dev-1");
    expect(pickBox("q17-sft-dev-1")).not.toBeChecked();
    expect(compareButton()).toBeDisabled();
  });

  it("AC4.4.2 refuses a third pick until one is unpicked", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: compareApi() });
    await ready();

    await pick(user, "q17-sft-dev-2", "q17-sft-dev-1", "q06-sft-dev-3");

    expect(pickBox("q06-sft-dev-3")).not.toBeChecked();
    expect(pickBox("q17-sft-dev-2")).toBeChecked();
    expect(pickBox("q17-sft-dev-1")).toBeChecked();
    expect(
      screen.getByText(/Two runs are already picked\. Unpick one first\./),
    ).toBeInTheDocument();

    await pick(user, "q17-sft-dev-2");
    await pick(user, "q06-sft-dev-3");

    expect(pickBox("q17-sft-dev-2")).not.toBeChecked();
    expect(pickBox("q06-sft-dev-3")).toBeChecked();
    expect(pickBox("q17-sft-dev-1")).toBeChecked();
  });

  it("AC4.4.3 reads No curve recorded for a run without metrics and still shows the other curve", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: compareApi(["q17-sft-dev-1"]) });
    await ready();

    const region = await openCompare(user, "q17-sft-dev-2", "q17-sft-dev-1");

    const missing = await within(region).findByText(/No curve recorded/);
    expect(missing.textContent).toContain("q17-sft-dev-1");
    expect(
      within(region).queryByText(/No curve recorded for q17-sft-dev-2/),
    ).not.toBeInTheDocument();
    const figure = await within(region).findByRole("figure", { name: /^Loss curve:/ });
    expect(figure.getAttribute("aria-label") ?? "").toContain("q17-sft-dev-2");
    await waitFor(() => expect(seriesPoints(figure)).toContain("3"));
  });

  it("AC4.4.3 reads No curve recorded for each run when neither has metrics", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: compareApi(["q17-sft-dev-2", "q17-sft-dev-1"]) });
    await ready();

    const region = await openCompare(user, "q17-sft-dev-2", "q17-sft-dev-1");

    await waitFor(() => expect(within(region).getAllByText(/No curve recorded/)).toHaveLength(2));
    expect(seriesPoints(region).filter((n) => n !== "0")).toEqual([]);
    // The settings still show without curves.
    expect(settingsRow(region, "Learning rate").textContent ?? "").toMatch(/changed/i);
  });
});
