/**
 * AC4.5.7 for a run that has ended: the Live numbers never promise a finish time for a run that
 * is no longer running, and a run with no time left reads "Done", not "~1 min". Found in the
 * batch-6 review; the cases of live-data.test.tsx are unchanged.
 */
import type { MetricsLine, Status } from "@/lib/api";
import { fakeApi, metricsLine, run, serviceStatus, Q06, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, waitFor, within } from "@/test/utils";

const LIVE = "q06-sft-dev-3";
const DASH = "—";

function status(word: "RUNNING" | "STOPPED" | "FAILED"): Status {
  return serviceStatus({ status: word, run_id: LIVE, started_at: "2026-11-04T20:10:00Z" });
}

function liveApi(): FakeApi {
  return fakeApi({
    getStatus: async () => status("RUNNING"),
    listRuns: async () => ({
      runs: [
        run({
          run_id: LIVE,
          model: Q06,
          method: "sft",
          dev_accuracy: null,
          minutes: null,
          date: null,
          started_at: "2026-11-04T20:10:00Z",
          status: "running",
        }),
      ],
      skipped_rows: 0,
    }),
  });
}

async function open(api: FakeApi, lines: MetricsLine[]): Promise<void> {
  renderPage("/training", { api });
  await waitFor(() => expect(api.stream.isOpen).toBe(true));
  api.stream.status(status("RUNNING"));
  lines.forEach((line, i) => api.stream.metric({ ...line, run_id: LIVE }, i + 1));
}

async function stat(key: string): Promise<string> {
  const panel = await screen.findByRole("region", { name: "Live numbers" });
  const value = within(panel)
    .getByText((_, el) => el?.getAttribute("data-stat") === key)
    .querySelector("[data-part=value]");
  return (value?.textContent ?? "").trim();
}

describe("training page, Live numbers of an ended run (AC4.5.7)", () => {
  it("AC4.5.7 shows no finish time once the run has stopped", async () => {
    const api = liveApi();
    await open(api, [
      metricsLine({ step: 10, total_steps: 100, elapsed_s: 30, eta_s: 270 }),
      metricsLine({ step: 20, total_steps: 100, elapsed_s: 60, eta_s: 240 }),
    ]);
    expect(await stat("finish")).not.toBe(DASH);

    api.stream.status(status("STOPPED"));

    await waitFor(async () => expect(await stat("finish")).toBe(DASH));
  });

  it("AC4.5.7 shows no finish time once the run has failed", async () => {
    const api = liveApi();
    await open(api, [metricsLine({ step: 10, total_steps: 100, elapsed_s: 30, eta_s: 270 })]);

    api.stream.status(status("FAILED"));

    await waitFor(async () => expect(await stat("finish")).toBe(DASH));
  });

  it("AC4.5.7 reads Done for the time remaining when the last line has no time left", async () => {
    const api = liveApi();
    await open(api, [
      metricsLine({ step: 99, total_steps: 100, elapsed_s: 297, eta_s: 3 }),
      metricsLine({ step: 100, total_steps: 100, elapsed_s: 300, eta_s: 0 }),
    ]);

    expect(await stat("remaining")).toBe("Done");
    expect(await stat("finish")).toBe(DASH);
  });
});
