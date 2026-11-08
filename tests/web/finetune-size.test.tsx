/**
 * Batch-11 (u5-website), part F: the size of the fine-tuning drawing, AC4.7.10. The main drawing
 * (`svg.ft-drawing`, a 1000-unit viewBox) is at most two-thirds of the window wide (`max-w-[66vw]`) and centred
 * in its column (`mx-auto`); it keeps `min-w-[860px]`, so narrow windows still scroll sideways.
 * The "One layer up close" figure stays at most 280 px wide (`max-w-[280px]`). jsdom does no
 * layout, so the tests read the Tailwind classes that set these sizes.
 */
import { FinetuneView } from "@/components/finetune-view";
import type { Run, RunConfig, Status } from "@/lib/api";
import { fakeApi, Q17, run, serviceStatus, type FakeApi } from "@/test/fake-api";
import { renderPage, renderWithApi, screen, waitFor, within } from "@/test/utils";

const LIVE = "q17-sft-dev-1";

/** The settings of a 1.7B supervised fine-tune at rank 16 and batch size 4. */
function config(): RunConfig {
  return {
    model: Q17,
    method: "sft",
    learning_rate: 2e-4,
    epochs: 1,
    lora_rank: 16,
    lora_alpha: 32,
    batch_size: 4,
  };
}

function running(): Status {
  return serviceStatus({ status: "RUNNING", run_id: LIVE, started_at: "2026-11-08T16:50:00Z" });
}

function activeRun(): Run {
  return run({
    run_id: LIVE,
    model: Q17,
    method: "sft",
    dev_accuracy: null,
    minutes: null,
    date: null,
    started_at: "2026-11-08T16:50:00Z",
    status: "running",
  });
}

/** A fake Api whose service reports the active sft run on Qwen3-1.7B. */
function liveApi(): FakeApi {
  return fakeApi({
    getStatus: async () => running(),
    listRuns: async () => ({ runs: [activeRun()], skipped_rows: 0 }),
    getRun: async (id: string) => ({ run_id: id, config: config(), status: {}, timings: {} }),
  });
}

/** The panel's main drawing: the `svg.ft-drawing` whose viewBox is 1000 units wide. */
function mainDrawing(scope: ParentNode = document): SVGSVGElement {
  const drawings = Array.from(scope.querySelectorAll<SVGSVGElement>("svg.ft-drawing"));
  const main = drawings.filter((svg) => {
    const box = (svg.getAttribute("viewBox") ?? "").trim().split(/\s+/);
    return box.length === 4 && Number(box[2]) === 1000;
  });
  expect(main).toHaveLength(1);
  return main[0];
}

/** The svg of the "One layer up close" figure. */
async function closeUpDrawing(): Promise<SVGSVGElement> {
  const figure = await screen.findByRole("figure", { name: "One layer up close" });
  const svg = figure.querySelector<SVGSVGElement>("svg.ft-drawing");
  if (!svg) throw new Error("the close-up figure has no drawing");
  return svg;
}

/** Renders the panel alone for the live sft run on Qwen3-1.7B and waits for its drawing. */
async function renderPanel(): Promise<void> {
  renderWithApi(
    <FinetuneView runId={LIVE} method="sft" model={Q17} liveLines={[]} live={true} />,
    liveApi(),
  );
  await waitFor(() => expect(document.querySelector("svg.ft-drawing")).not.toBeNull());
}

describe("fine-tuning drawing at its designed size (AC4.7.10)", () => {
  it("AC4.7.10 the main drawing of a 1.7B fine-tune is at most two-thirds of the window wide and centred", async () => {
    await renderPanel();
    const drawing = mainDrawing();
    expect(drawing).toHaveClass("max-w-[66vw]");
    expect(drawing).toHaveClass("mx-auto");
  });

  it("AC4.7.10 the main drawing keeps its 860 px minimum width for sideways scrolling", async () => {
    await renderPanel();
    expect(mainDrawing()).toHaveClass("min-w-[860px]");
  });

  it("AC4.7.10 the One layer up close figure stays at most 280 px wide", async () => {
    await renderPanel();
    const svg = await closeUpDrawing();
    expect(svg).toHaveClass("max-w-[280px]");
    expect(svg).not.toHaveClass("max-w-[66vw]");
  });

  it("AC4.7.10 on the training page the panel's main drawing is capped at two-thirds of the window, centred, and keeps its minimum width", async () => {
    const api = liveApi();
    renderPage("/training", { api });
    await waitFor(() => expect(api.stream.isOpen).toBe(true));
    api.stream.status(running());
    const region = await screen.findByRole("region", { name: "How the model is fine-tuned" });
    await waitFor(() => expect(region.querySelector("svg.ft-drawing")).not.toBeNull());
    const drawing = mainDrawing(region);
    expect(drawing).toHaveClass("max-w-[66vw]");
    expect(drawing).toHaveClass("mx-auto");
    expect(drawing).toHaveClass("min-w-[860px]");
    const closeUp = within(region).getByRole("figure", { name: "One layer up close" });
    expect(closeUp.querySelector("svg.ft-drawing")).toHaveClass("max-w-[280px]");
  });
});
