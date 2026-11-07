/**
 * u5-website, part W1: the landing page (US4.2, AC4.2.1-AC4.2.4).
 * Text, roles and data-* state only; the halftone canvas draws nothing under jsdom.
 */
import type { Run } from "@/lib/api";
import { apiError, fakeApi, Q06, Q17, run } from "@/test/fake-api";
import { setReducedMotion } from "@/test/setup";
import { act, renderPage, screen, userEvent, waitFor } from "@/test/utils";

const DESCRIPTION = "Teaching small open models grade-school math, one measured run at a time.";

/** The mockup's scored runs: two baselines, three tuned runs, one running and one failed. */
const SCORED_RUNS: Run[] = [
  run({
    run_id: "q17-base-dev-1",
    model: Q17,
    method: "base",
    dev_accuracy: 0.587,
    test_accuracy: 0.579,
    gain: null,
    minutes: 24,
    date: "2026-11-02T10:00:00Z",
  }),
  run({
    run_id: "q06-base-dev-1",
    model: Q06,
    method: "base",
    dev_accuracy: 0.413,
    test_accuracy: 0.402,
    gain: null,
    minutes: 11,
    date: "2026-11-01T10:00:00Z",
  }),
  run({
    run_id: "q17-sft-dev-1",
    model: Q17,
    method: "sft",
    dev_accuracy: 0.659,
    gain: 0.072,
    minutes: 49,
    date: "2026-11-04T10:00:00Z",
  }),
  run({
    run_id: "q17-sft-dev-2",
    model: Q17,
    method: "sft",
    dev_accuracy: 0.681,
    test_accuracy: 0.67,
    gain: 0.094,
    minutes: 52,
    date: "2026-11-05T10:00:00Z",
    finalist: true,
  }),
  run({
    run_id: "q06-sft-dev-3",
    model: Q06,
    method: "sft",
    dev_accuracy: 0.47,
    gain: 0.057,
    minutes: 23,
    date: "2026-11-04T12:00:00Z",
  }),
  run({
    run_id: "q06-sft-dev-4",
    model: Q06,
    method: "sft",
    dev_accuracy: null,
    gain: null,
    minutes: null,
    date: null,
    status: "running",
  }),
  run({
    run_id: "q06-sft-dev-0",
    model: Q06,
    method: "sft",
    dev_accuracy: null,
    gain: null,
    minutes: 2,
    date: "2026-11-03T21:40:00Z",
    status: "failed",
  }),
];

function withRuns(runs: Run[]) {
  return fakeApi({ listRuns: async () => ({ runs, skipped_rows: 0 }) });
}

/** The main region's text with whitespace collapsed. */
function mainText(): string {
  return (screen.getByRole("main").textContent ?? "").replace(/\s+/g, " ");
}

/** The landing page's halftone headline root (`data-motion="still" | "live"`). */
function headline(): HTMLElement | null {
  return document.querySelector<HTMLElement>("main [data-motion]");
}

/** The one link or button with this exact accessible name. */
function control(name: string): HTMLElement {
  const found = [
    ...screen.queryAllByRole("link", { name }),
    ...screen.queryAllByRole("button", { name }),
  ];
  expect(found, `one link or button named "${name}"`).toHaveLength(1);
  return found[0];
}

describe("landing page", () => {
  it("AC4.2.1 shows the wordmark as a real h1 while the halftone canvas is aria-hidden", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS) });
    const h1s = await screen.findAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]).toHaveAccessibleName("gsm8k");

    const root = headline();
    expect(root, "the halftone headline root carries data-motion").not.toBeNull();
    const canvases = root!.querySelectorAll("canvas");
    expect(canvases.length).toBeGreaterThan(0);
    for (const canvas of canvases) {
      expect(canvas.closest('[aria-hidden="true"]')).not.toBeNull();
    }
  });

  it("AC4.2.1 shows the one-line description under its label", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS) });
    expect(await screen.findByText(DESCRIPTION)).toBeInTheDocument();
    expect(screen.getByText(/a personal fine-tuning lab on this pc/i)).toBeInTheDocument();
  });

  it("AC4.2.1 shows the best run's model, method, dev accuracy and gain over its baseline", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS) });
    await waitFor(() => expect(mainText()).toContain("+9.4 pts"));
    expect(screen.getByText(/best so far/i)).toBeInTheDocument();
    const text = mainText();
    expect(text).toContain("Qwen3-1.7B-Base");
    expect(text).toMatch(/sft/i);
    expect(text).toContain("68.1%");
    // Only the best run is on the line, not the runner-up or the baselines.
    expect(text).not.toContain("65.9%");
    expect(text).not.toContain("+7.2 pts");
    expect(text).not.toContain("58.7%");
  });

  it("AC4.2.1 has Go to training and See scores, each leading to its page", async () => {
    const user = userEvent.setup();
    const { router } = renderPage("/", { api: withRuns(SCORED_RUNS) });
    await waitFor(() => expect(mainText()).toContain("+9.4 pts"));

    await user.click(control("See scores"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/scores"));

    await act(() => router.navigate("/"));
    await waitFor(() => expect(mainText()).toContain("+9.4 pts"));
    await user.click(control("Go to training"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/training"));
  });

  it("AC4.2.1 leaves base runs out of best so far even when a baseline scores higher", async () => {
    renderPage("/", {
      api: withRuns([
        run({
          run_id: "q17-base-dev-1",
          model: Q17,
          method: "base",
          dev_accuracy: 0.7,
          gain: null,
          date: "2026-11-02T10:00:00Z",
        }),
        run({
          run_id: "q06-sft-dev-1",
          model: Q06,
          method: "sft",
          dev_accuracy: 0.47,
          gain: 0.057,
          date: "2026-11-04T10:00:00Z",
        }),
      ]),
    });
    await waitFor(() => expect(mainText()).toContain("+5.7 pts"));
    const text = mainText();
    expect(text).toContain("Qwen3-0.6B-Base");
    expect(text).toContain("47.0%");
    expect(text).not.toContain("70.0%");
  });

  it("AC4.2.1 breaks a dev accuracy tie toward the earlier run", async () => {
    renderPage("/", {
      api: withRuns([
        run({
          run_id: "q17-sft-dev-5",
          model: Q17,
          method: "sft",
          dev_accuracy: 0.6,
          gain: 0.013,
          date: "2026-11-06T10:00:00Z",
        }),
        run({
          run_id: "q06-sft-dev-5",
          model: Q06,
          method: "sft",
          dev_accuracy: 0.6,
          gain: 0.187,
          date: "2026-11-03T10:00:00Z",
        }),
      ]),
    });
    await waitFor(() => expect(mainText()).toContain("60.0%"));
    const text = mainText();
    expect(text).toContain("Qwen3-0.6B-Base");
    expect(text).toContain("+18.7 pts");
    expect(text).not.toContain("+1.3 pts");
  });

  it("AC4.2.1 shows a gain below the baseline with its minus sign", async () => {
    renderPage("/", {
      api: withRuns([
        run({
          run_id: "q06-base-dev-1",
          model: Q06,
          method: "base",
          dev_accuracy: 0.413,
          gain: null,
        }),
        run({
          run_id: "q06-sft-dev-1",
          model: Q06,
          method: "sft",
          dev_accuracy: 0.393,
          gain: -0.02,
        }),
      ]),
    });
    await waitFor(() => expect(mainText()).toContain("39.3%"));
    expect(mainText()).toContain("−2.0 pts");
  });

  it("AC4.2.1 with only baselines scored shows the best baseline and no tuned run yet", async () => {
    renderPage("/", {
      api: withRuns([
        run({
          run_id: "q06-base-dev-1",
          model: Q06,
          method: "base",
          dev_accuracy: 0.413,
          gain: null,
          date: "2026-11-01T10:00:00Z",
        }),
        run({
          run_id: "q17-base-dev-1",
          model: Q17,
          method: "base",
          dev_accuracy: 0.587,
          gain: null,
          date: "2026-11-02T10:00:00Z",
        }),
      ]),
    });
    await waitFor(() => expect(mainText()).toContain("no tuned run yet"));
    const text = mainText();
    expect(text).toContain("Qwen3-1.7B-Base");
    expect(text).toMatch(/baseline/i);
    expect(text).toContain("58.7%");
    expect(text).not.toContain("41.3%");
    expect(text).not.toContain("No runs yet");
  });

  it("AC4.2.1 shows none of the pasted component's demo text in the hero", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS) });
    await waitFor(() => expect(mainText()).toContain("+9.4 pts"));
    const text = mainText();
    expect(text).not.toContain("Halden");
    expect(text).not.toContain("Oslo / Lisbon");
    expect(text).not.toContain("Back to top");
  });

  it("AC4.2.1 renders the headline at once while the run list is still loading", async () => {
    renderPage("/", { api: fakeApi({ listRuns: () => new Promise(() => {}) }) });
    expect(await screen.findByRole("heading", { level: 1, name: "gsm8k" })).toBeInTheDocument();
    expect(headline()).not.toBeNull();
    const text = mainText();
    expect(text).not.toContain("No runs yet");
    expect(text).not.toContain("Run log could not be read");
  });

  it("AC4.2.2 with no runs reads No runs yet with the Go to training button", async () => {
    const user = userEvent.setup();
    const { router } = renderPage("/", { api: fakeApi() });
    await waitFor(() =>
      expect(mainText()).toContain("No runs yet: start with a baseline on the training page"),
    );
    await user.click(control("Go to training"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/training"));
  });

  it("AC4.2.3 reads Run log could not be read naming the file, and the headline still renders", async () => {
    renderPage("/", {
      api: fakeApi({
        listRuns: async () => {
          throw apiError("run_log_unreadable", "Run log could not be read", "results/runs.csv");
        },
      }),
    });
    await waitFor(() =>
      expect(mainText()).toMatch(/Run log could not be read: results\/runs\.csv/),
    );
    expect(screen.getByRole("heading", { level: 1, name: "gsm8k" })).toBeInTheDocument();
    expect(headline()).not.toBeNull();
    expect(mainText()).not.toContain("No runs yet");
  });

  it("AC4.2.3 names the file the service reports, not a fixed path", async () => {
    renderPage("/", {
      api: fakeApi({
        listRuns: async () => {
          throw apiError(
            "run_log_unreadable",
            "Run log could not be read",
            "outputs/elsewhere.csv",
          );
        },
      }),
    });
    await waitFor(() =>
      expect(mainText()).toMatch(/Run log could not be read: outputs\/elsewhere\.csv/),
    );
    expect(mainText()).not.toContain("results/runs.csv");
  });

  it("AC4.2.4 with reduce motion on keeps the halftone dots still", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS), reducedMotion: true });
    await screen.findByRole("heading", { level: 1, name: "gsm8k" });
    await waitFor(() => expect(headline()).not.toBeNull());
    expect(headline()).toHaveAttribute("data-motion", "still");
  });

  it("AC4.2.4 with reduce motion off lets the halftone dots move", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS), reducedMotion: false });
    await waitFor(() => expect(headline()).not.toBeNull());
    expect(headline()).toHaveAttribute("data-motion", "live");
  });

  it("AC4.2.4 stops the dots when reduce motion is turned on while the page is open", async () => {
    renderPage("/", { api: withRuns(SCORED_RUNS), reducedMotion: false });
    await waitFor(() => expect(headline()).toHaveAttribute("data-motion", "live"));
    act(() => setReducedMotion(true));
    await waitFor(() => expect(headline()).toHaveAttribute("data-motion", "still"));
  });
});
