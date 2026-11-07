/**
 * Part W2 (u5-website): the scores page. Ranked table with baseline rows (AC4.3.1-AC4.3.3), empty
 * and error states (AC4.3.4), finalist marks (AC4.3.5) and the website side of the test-split flow
 * (US3.6: only finalists, second confirmation). Text, roles, labels and data-* only.
 */
import { vi } from "vitest";

import { UNREACHABLE_MESSAGE, type Api, type Run, type RunList } from "@/lib/api";
import { Q06, Q17, apiError, checkedRun, fakeApi, run } from "@/test/fake-api";
import { renderPage, screen, userEvent, waitFor, within } from "@/test/utils";

type User = ReturnType<typeof userEvent.setup>;

const CAPTION = /Highest scores, ranked by dev accuracy/;

/** The mockup's runs (mockups.md, Screen 2), plus a negative gain and a test-only row. */
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
const BL06 = run({
  run_id: "q06-base-dev-1",
  model: Q06,
  method: "base",
  dev_accuracy: 0.413,
  test_accuracy: 0.402,
  gain: null,
  minutes: 11,
  date: "2026-11-01T09:00:00Z",
});
const SFT17B = run({
  run_id: "q17-sft-dev-2",
  model: Q17,
  method: "sft",
  dev_accuracy: 0.681,
  test_accuracy: 0.67,
  gain: 0.094,
  minutes: 52,
  date: "2026-11-05T12:00:00Z",
});
const SFT17A = run({
  run_id: "q17-sft-dev-1",
  model: Q17,
  method: "sft",
  dev_accuracy: 0.659,
  test_accuracy: null,
  gain: 0.072,
  minutes: 49,
  date: "2026-11-04T12:00:00Z",
});
const SFT06C = run({
  run_id: "q06-sft-dev-3",
  model: Q06,
  method: "sft",
  dev_accuracy: 0.47,
  test_accuracy: null,
  gain: 0.057,
  minutes: 23,
  date: "2026-11-04T15:00:00Z",
});
const SFT06B = run({
  run_id: "q06-sft-dev-2",
  model: Q06,
  method: "sft",
  dev_accuracy: 0.393,
  test_accuracy: null,
  gain: -0.02,
  minutes: 30,
  date: "2026-11-03T15:00:00Z",
});
/** A test-split row: no dev score, so it is not a row of its own (its score joins BL17). */
const TEST17 = run({
  run_id: "q17-base-test-1",
  model: Q17,
  method: "base",
  data: "gsm8k-test",
  dev_accuracy: null,
  test_accuracy: 0.579,
  gain: null,
  minutes: 60,
  date: "2026-11-06T09:00:00Z",
});

/** Shuffled on purpose: the page ranks, the service does not. */
const RUNS: Run[] = [SFT06B, TEST17, SFT17A, BL06, SFT06C, SFT17B, BL17];
const ALL_IDS = RUNS.map((r) => r.run_id);

/** A fake api whose run list, finalist list and finalist marks stay consistent (C4, C6). */
function scoresApi(runs: Run[], marked: string[] = [], extra: Partial<Api> = {}) {
  let finalists = [...marked];
  return fakeApi({
    listRuns: async (): Promise<RunList> => ({
      runs: runs.map((r) => ({ ...r, finalist: finalists.includes(r.run_id) })),
      skipped_rows: 0,
    }),
    getFinalists: async () => [...finalists],
    markFinalist: async (id: string) => {
      if (!finalists.includes(id)) finalists = [...finalists, id];
      return [...finalists];
    },
    unmarkFinalist: async (id: string) => {
      finalists = finalists.filter((f) => f !== id);
      return [...finalists];
    },
    ...extra,
  });
}

async function findTable(): Promise<HTMLElement> {
  return screen.findByRole("table", { name: CAPTION });
}

/** Table rows that are not header rows. */
function bodyRows(table: HTMLElement): HTMLElement[] {
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("columnheader").length === 0);
}

/** The run id each body row shows, top to bottom. */
function rowIds(table: HTMLElement, ids: string[] = ALL_IDS): string[] {
  return bodyRows(table).map((row) => ids.find((id) => row.textContent?.includes(id)) ?? "?");
}

function rowFor(table: HTMLElement, id: string): HTMLElement {
  const row = bodyRows(table).find((r) => r.textContent?.includes(id));
  if (!row) throw new Error(`No table row for ${id}`);
  return row;
}

/** The trimmed text of each cell of a row. */
function cellTexts(row: HTMLElement): string[] {
  return [...within(row).queryAllByRole("cell"), ...within(row).queryAllByRole("rowheader")].map(
    (c) => (c.textContent ?? "").trim(),
  );
}

function isBaselineRow(row: HTMLElement): boolean {
  return within(row).queryAllByText("BL").length > 0;
}

/** The star is announced as "finalist" (interaction-spec ScoresTable). */
function hasFinalistMark(row: HTMLElement): boolean {
  return (
    within(row).queryAllByText(/finalist/i).length > 0 ||
    within(row).queryAllByLabelText(/finalist/i).length > 0 ||
    within(row).queryAllByTitle(/finalist/i).length > 0
  );
}

/** Picks the option whose text or value matches `pattern` in a native select. */
async function choose(user: User, select: HTMLElement, pattern: RegExp): Promise<void> {
  const option = within(select)
    .getAllByRole("option")
    .find((o) => pattern.test(o.textContent ?? "") || pattern.test((o as HTMLOptionElement).value));
  if (!option) throw new Error(`No option matching ${String(pattern)}`);
  await user.selectOptions(select, option);
}

/** Opens a row's actions menu and returns the menu item named `name`. */
async function menuItem(user: User, runId: string, name: RegExp): Promise<HTMLElement> {
  await user.click(screen.getByRole("button", { name: `Actions for ${runId}` }));
  return screen.findByRole("menuitem", { name });
}

function main(): HTMLElement {
  return screen.getByRole("main");
}

describe("scores page", () => {
  it("AC4.3.1 shows every column of a scored run under the page heading", async () => {
    renderPage("/scores", { api: scoresApi(RUNS) });
    const table = await findTable();
    expect(screen.getByRole("heading", { level: 1, name: "Highest scores" })).toBeInTheDocument();

    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent ?? "");
    for (const column of [
      /run id/i,
      /model/i,
      /method/i,
      /dev/i,
      /test/i,
      /gain/i,
      /min/i,
      /date/i,
    ]) {
      expect(headers.some((h) => column.test(h))).toBe(true);
    }

    const row = rowFor(table, "q17-sft-dev-2");
    const text = row.textContent ?? "";
    expect(text).toContain("q17-sft-dev-2");
    expect(text).toContain("1.7B");
    expect(text).toContain("68.1%");
    expect(text).toContain("67.0%");
    expect(text).toContain("+9.4 pts");
    expect(text).toContain("2026-11-05");
    const cells = cellTexts(row);
    expect(cells.some((c) => /^sft$/i.test(c))).toBe(true);
    expect(cells).toContain("52");
  });

  it("AC4.3.1 puts each model's baseline first, marked BL, then ranks by dev accuracy", async () => {
    renderPage("/scores", { api: scoresApi(RUNS) });
    const table = await findTable();
    const ids = rowIds(table);

    expect(ids.slice(0, 2).sort()).toEqual(["q06-base-dev-1", "q17-base-dev-1"]);
    expect(ids.slice(2)).toEqual([
      "q17-sft-dev-2",
      "q17-sft-dev-1",
      "q06-sft-dev-3",
      "q06-sft-dev-2",
    ]);
    expect(isBaselineRow(rowFor(table, "q17-base-dev-1"))).toBe(true);
    expect(isBaselineRow(rowFor(table, "q06-base-dev-1"))).toBe(true);
    expect(isBaselineRow(rowFor(table, "q17-sft-dev-2"))).toBe(false);
    // The baseline's own gain is not a number: a dash, never "+0.0 pts".
    expect(within(rowFor(table, "q17-base-dev-1")).getByText("—")).toBeInTheDocument();
  });

  it("AC4.3.1 breaks a dev accuracy tie in favour of the earlier run", async () => {
    const later = run({ run_id: "q06-sft-dev-5", dev_accuracy: 0.5, date: "2026-11-06T10:00:00Z" });
    const earlier = run({
      run_id: "q06-sft-dev-4",
      dev_accuracy: 0.5,
      date: "2026-11-02T10:00:00Z",
    });
    const best = run({ run_id: "q06-sft-dev-6", dev_accuracy: 0.55, date: "2026-11-07T10:00:00Z" });
    renderPage("/scores", { api: scoresApi([later, BL06, earlier, best]) });
    const table = await findTable();
    const ids = ["q06-base-dev-1", "q06-sft-dev-4", "q06-sft-dev-5", "q06-sft-dev-6"];

    expect(rowIds(table, ids)).toEqual([
      "q06-base-dev-1",
      "q06-sft-dev-6",
      "q06-sft-dev-4",
      "q06-sft-dev-5",
    ]);
  });

  it("AC4.3.1 lists only runs with a dev score", async () => {
    const running = run({
      run_id: "q17-sft-dev-3",
      model: Q17,
      dev_accuracy: null,
      status: "running",
      date: null,
    });
    renderPage("/scores", { api: scoresApi([...RUNS, running]) });
    const table = await findTable();
    const ids = rowIds(table, [...ALL_IDS, "q17-sft-dev-3"]);

    expect(ids).toHaveLength(6);
    expect(ids).not.toContain("q17-base-test-1");
    expect(ids).not.toContain("q17-sft-dev-3");
  });

  it("AC4.3.2 shows -- for a missing test score, never 0%", async () => {
    renderPage("/scores", { api: scoresApi(RUNS) });
    const table = await findTable();
    const row = rowFor(table, "q17-sft-dev-1");

    expect(within(row).getByText("--")).toBeInTheDocument();
    expect(row.textContent ?? "").not.toMatch(/(^|[^0-9.])0(\.0)?%/);
    // A run that has a test score shows it.
    expect(rowFor(table, "q17-base-dev-1").textContent).toContain("57.9%");
  });

  it("AC4.3.2 signs every gain with + or − (U+2212)", async () => {
    renderPage("/scores", { api: scoresApi(RUNS) });
    const table = await findTable();

    expect(within(rowFor(table, "q06-sft-dev-3")).getByText("+5.7 pts")).toBeInTheDocument();
    const negative = rowFor(table, "q06-sft-dev-2");
    expect(within(negative).getByText("−2.0 pts")).toBeInTheDocument();
    expect(negative.textContent ?? "").not.toContain("-2.0 pts");
  });

  it("AC4.3.3 filters by model and keeps that model's baseline row", async () => {
    const user = userEvent.setup();
    renderPage("/scores", { api: scoresApi(RUNS) });
    const table = await findTable();

    await choose(user, screen.getByRole("combobox", { name: /^Model/ }), /1\.7B/);

    await waitFor(() => expect(rowIds(table)).not.toContain("q06-sft-dev-3"));
    const ids = rowIds(table);
    expect(ids).not.toContain("q06-sft-dev-2");
    expect(ids).toContain("q17-sft-dev-2");
    expect(ids).toContain("q17-sft-dev-1");
    expect(ids[0] === "q17-base-dev-1" || ids[1] === "q17-base-dev-1").toBe(true);
  });

  it("AC4.3.3 filters by method and every baseline row stays", async () => {
    const user = userEvent.setup();
    const grpo = run({
      run_id: "q17-grpo-dev-1",
      model: Q17,
      method: "grpo",
      dev_accuracy: 0.7,
      gain: 0.113,
      date: "2026-11-06T12:00:00Z",
    });
    const ids = [...ALL_IDS, "q17-grpo-dev-1"];
    renderPage("/scores", { api: scoresApi([...RUNS, grpo]) });
    const table = await findTable();
    expect(rowIds(table, ids)).toContain("q17-grpo-dev-1");

    await choose(user, screen.getByRole("combobox", { name: /^Method/ }), /\bsft\b/i);

    await waitFor(() => expect(rowIds(table, ids)).not.toContain("q17-grpo-dev-1"));
    const shown = rowIds(table, ids);
    expect(shown.slice(0, 2).sort()).toEqual(["q06-base-dev-1", "q17-base-dev-1"]);
    expect(shown.slice(2)).toEqual([
      "q17-sft-dev-2",
      "q17-sft-dev-1",
      "q06-sft-dev-3",
      "q06-sft-dev-2",
    ]);
  });

  it("AC4.3.3 says when no run matches the filters and clears them", async () => {
    const user = userEvent.setup();
    const runs = [
      BL17,
      BL06,
      SFT17B,
      run({ run_id: "q06-grpo-dev-1", method: "grpo", gain: 0.01 }),
    ];
    const ids = runs.map((r) => r.run_id);
    renderPage("/scores", { api: scoresApi(runs) });
    await findTable();

    await choose(user, screen.getByRole("combobox", { name: /^Model/ }), /0\.6B/);
    await choose(user, screen.getByRole("combobox", { name: /^Method/ }), /\bsft\b/i);

    expect(await screen.findByText("No runs match these filters.")).toBeInTheDocument();
    expect(rowIds(screen.getByRole("table", { name: CAPTION }), ids)).toContain("q06-base-dev-1");

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() =>
      expect(rowIds(screen.getByRole("table", { name: CAPTION }), ids)).toContain("q06-grpo-dev-1"),
    );
    expect(screen.queryByText("No runs match these filters.")).not.toBeInTheDocument();
  });

  it("AC4.3.4 invites a baseline run when there are no scored runs", async () => {
    renderPage("/scores", { api: scoresApi([]) });

    await waitFor(() =>
      expect(main()).toHaveTextContent(
        "No scored runs yet. Run a baseline from the training page.",
      ),
    );
    const links = within(main()).getAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === "/training")).toBe(true);
    expect(screen.queryByRole("table", { name: CAPTION })).not.toBeInTheDocument();
  });

  it("AC4.3.4 treats runs without a dev score as no scored runs", async () => {
    renderPage("/scores", { api: scoresApi([TEST17]) });

    await waitFor(() => expect(main()).toHaveTextContent("No scored runs yet."));
    expect(main().textContent).not.toContain("q17-base-test-1");
  });

  it("AC4.3.4 names the unreadable run log and retries on Retry", async () => {
    const user = userEvent.setup();
    const listRuns = vi
      .fn<Api["listRuns"]>()
      .mockRejectedValueOnce(
        apiError("run_log_unreadable", "Run log could not be read", "results/runs.csv"),
      )
      .mockResolvedValue({ runs: RUNS, skipped_rows: 0 });
    const api = fakeApi({ listRuns });
    renderPage("/scores", { api });

    await waitFor(() => expect(main()).toHaveTextContent("Run log could not be read"));
    expect(main()).toHaveTextContent("results/runs.csv");
    const calls = listRuns.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Retry" }));

    const table = await findTable();
    expect(listRuns.mock.calls.length).toBeGreaterThan(calls);
    expect(rowIds(table)).toContain("q17-sft-dev-2");
    expect(main()).not.toHaveTextContent("Run log could not be read");
  });

  it("AC4.3.4 says what to do when the run service is unreachable, with Retry", async () => {
    const api = fakeApi({
      listRuns: vi
        .fn<Api["listRuns"]>()
        .mockRejectedValue(apiError("unreachable", UNREACHABLE_MESSAGE)),
    });
    renderPage("/scores", { api });

    await waitFor(() =>
      expect(main()).toHaveTextContent("The run service is not reachable at 127.0.0.1:8000"),
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(main().textContent).not.toMatch(/\b(500|undefined)\b/);
  });

  it("AC4.3.5 marks a run as finalist through the service and shows the mark", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS);
    renderPage("/scores", { api });
    const table = await findTable();
    expect(hasFinalistMark(rowFor(table, "q17-sft-dev-1"))).toBe(false);

    await user.click(await menuItem(user, "q17-sft-dev-1", /^Mark as finalist/));

    expect(api.markFinalist).toHaveBeenCalledWith("q17-sft-dev-1");
    await waitFor(() =>
      expect(
        hasFinalistMark(rowFor(screen.getByRole("table", { name: CAPTION }), "q17-sft-dev-1")),
      ).toBe(true),
    );
    expect(
      hasFinalistMark(rowFor(screen.getByRole("table", { name: CAPTION }), "q17-sft-dev-2")),
    ).toBe(false);
  });

  it("AC4.3.5 unmarks a finalist through the service and removes the mark", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS, ["q17-sft-dev-2"]);
    renderPage("/scores", { api });
    const table = await findTable();
    await waitFor(() => expect(hasFinalistMark(rowFor(table, "q17-sft-dev-2"))).toBe(true));

    await user.click(await menuItem(user, "q17-sft-dev-2", /^Unmark finalist/));

    expect(api.unmarkFinalist).toHaveBeenCalledWith("q17-sft-dev-2");
    await waitFor(() =>
      expect(
        hasFinalistMark(rowFor(screen.getByRole("table", { name: CAPTION }), "q17-sft-dev-2")),
      ).toBe(false),
    );
  });

  it("AC4.3.5 names the file when a finalist mark fails and leaves the row unmarked", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS, [], {
      markFinalist: vi
        .fn<Api["markFinalist"]>()
        .mockRejectedValue(
          apiError("finalists_unreadable", "Finalists could not be read", "results/finalists.json"),
        ),
    });
    renderPage("/scores", { api });
    await findTable();

    await user.click(await menuItem(user, "q17-sft-dev-1", /^Mark as finalist/));

    await waitFor(() => expect(main()).toHaveTextContent("results/finalists.json"));
    expect(
      hasFinalistMark(rowFor(screen.getByRole("table", { name: CAPTION }), "q17-sft-dev-1")),
    ).toBe(false);
  });

  it("AC3.6.2 offers Score on test only for finalists, with the reason", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS);
    renderPage("/scores", { api });
    await findTable();

    const item = await menuItem(user, "q17-sft-dev-1", /^Score on test/);

    const disabled =
      item.getAttribute("aria-disabled") === "true" || (item as HTMLButtonElement).disabled;
    expect(disabled).toBe(true);
    expect(screen.getByText(/Only finalists can be scored on the test split/)).toBeInTheDocument();
    await user.click(item);
    expect(api.checkRun).not.toHaveBeenCalled();
  });

  it("AC3.6.3 scores a finalist on test only after the second confirmation", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS, ["q17-sft-dev-2"], {
      checkRun: vi.fn<Api["checkRun"]>().mockResolvedValue(
        checkedRun({
          check_id: "check-test-1",
          attempt_id: "q17-best-test-1",
          model: Q17,
          method: "best",
          kind: "evaluate",
          estimate_s: 6720,
          estimate_text: "about 1 h 52 min",
          config: {
            model: Q17,
            method: "best",
            split: "test",
            adapter_path: "checkpoints/q17-sft-dev-2",
          },
        }),
      ),
    });
    renderPage("/scores", { api });
    await findTable();

    await user.click(await menuItem(user, "q17-sft-dev-2", /^Score on test/));

    const dialog = await screen.findByRole("dialog", {
      name: /Score q17-sft-dev-2 on the test split/,
    });
    expect(api.checkRun).toHaveBeenCalledWith(
      expect.objectContaining({
        model: Q17,
        method: "best",
        split: "test",
        adapter_path: "checkpoints/q17-sft-dev-2",
      }),
    );
    const score = within(dialog).getByRole("button", { name: /^Score on test$/ });
    expect(score).toBeDisabled();
    await user.click(score);
    expect(api.confirmRun).not.toHaveBeenCalled();

    await user.click(
      within(dialog).getByRole("checkbox", {
        name: /I understand this uses the held-out test split/,
      }),
    );
    expect(score).toBeEnabled();
    await user.click(score);

    await waitFor(() => expect(api.confirmRun).toHaveBeenCalledWith("check-test-1", true));
  });

  it("AC3.6.3 keeps the test-split dialog open with the reason when the service refuses", async () => {
    const user = userEvent.setup();
    const api = scoresApi(RUNS, ["q17-sft-dev-2"], {
      confirmRun: vi
        .fn<Api["confirmRun"]>()
        .mockRejectedValue(
          apiError("not_finalist", "Only finalists can be scored on the test split"),
        ),
    });
    renderPage("/scores", { api });
    await findTable();

    await user.click(await menuItem(user, "q17-sft-dev-2", /^Score on test/));
    const dialog = await screen.findByRole("dialog", {
      name: /Score q17-sft-dev-2 on the test split/,
    });
    await user.click(
      within(dialog).getByRole("checkbox", {
        name: /I understand this uses the held-out test split/,
      }),
    );
    await user.click(within(dialog).getByRole("button", { name: /^Score on test$/ }));

    await waitFor(() =>
      expect(dialog).toHaveTextContent("Only finalists can be scored on the test split"),
    );
    expect(
      screen.getByRole("dialog", { name: /Score q17-sft-dev-2 on the test split/ }),
    ).toBeVisible();
  });
});
