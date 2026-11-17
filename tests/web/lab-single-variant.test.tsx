/**
 * Gap-1 part W2 (u11-finetune-lab): AC11.4.6 for a finished lesson with a single variant
 * (`l01`, variant `baseline`). The "What happened" list names that variant as having the lowest
 * dev loss after training, with its value to 3 decimals. The closing sentence that differences of
 * a few hundredths between variants are noise compares variants, so one variant has none.
 *
 * Text, roles and data-* only, as in `lab.test.tsx` (its fixtures and helpers, trimmed).
 */
import { type LabLesson, type LabList, type LabMetricsLine, type LabSummary } from "@/lib/api";
import { fakeApi, labLesson, labList, labSummary, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, within } from "@/test/utils";

const TOTAL = 20;

function norm(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

function follows(first: Node, second: Node): boolean {
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

/** Whether `text` holds `token` as a whole number (not part of a longer number). */
function hasToken(text: string, token: string): boolean {
  const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![\\d.,])${escaped}(?![\\d,]|\\.\\d)`).test(text);
}

function line(step: number, loss: number | null, devLoss: number | null): LabMetricsLine {
  return {
    v: 1,
    step,
    total_steps: TOTAL,
    loss,
    learning_rate: devLoss === null ? 1e-3 : null,
    grad_norm: devLoss === null ? 0.5 : null,
    elapsed_s: step * 1.5,
    dev_loss: devLoss,
  };
}

/** Lines that match a summary: step lines 1..TOTAL, dev lines at 0, 2, ..., TOTAL. */
function linesFor(s: LabSummary): LabMetricsLine[] {
  const lines: LabMetricsLine[] = [];
  const before = s.dev_loss_before ?? 2.8;
  const after = s.dev_loss_after ?? before;
  for (let k = 0; k <= 10; k += 1) {
    const step = (k * TOTAL) / 10;
    lines.push(line(step, null, before + ((after - before) * step) / TOTAL));
  }
  const first = s.train_loss_first ?? 2.9;
  const last = s.train_loss_last ?? first;
  for (let step = 1; step <= TOTAL; step += 1) {
    lines.push(line(step, first + ((last - first) * (step - 1)) / (TOTAL - 1), null));
  }
  return lines.sort((a, b) => a.step - b.step || (a.dev_loss === null ? 1 : -1));
}

/** Lesson l01 finished: its single variant "Baseline", a normal run (no overfit, no divergence). */
function l01Done(): LabLesson {
  const base = labLesson("l01");
  return {
    ...base,
    lesson: { ...base.lesson, state: "finished" },
    status: {
      state: "finished",
      variant: null,
      done: base.results.map((r) => r.name),
      started_at: "2026-11-08T10:00:00Z",
      ended_at: "2026-11-08T10:12:00Z",
      message: null,
    },
    results: base.results.map((r) => {
      const summary = labSummary({
        lesson: "l01",
        variant: r.name,
        label: r.label,
        steps: TOTAL,
        train_loss_first: 2.9,
        train_loss_last: 1.4,
        dev_loss_before: 2.8,
        dev_loss_after: 1.2347,
        dev_loss_best: 1.2347,
        dev_loss_best_step: TOTAL,
      });
      return { ...r, summary, lines: linesFor(summary) };
    }),
  };
}

function labApi(list: LabList, lessons: Record<string, LabLesson>): FakeApi {
  return fakeApi({
    getLab: async () => list,
    getLabLesson: async (lessonId: string) => lessons[lessonId] ?? labLesson(lessonId),
  });
}

/** The first list after the "What happened" heading: its items' texts. */
function whatHappened(): string[] {
  const heading = screen.getByRole("heading", { name: "What happened" });
  const list = [...document.querySelectorAll<HTMLElement>("ul, ol")].find((l) =>
    follows(heading, l),
  );
  if (!list) throw new Error('No list after the "What happened" heading');
  return within(list)
    .getAllByRole("listitem")
    .map((li) => norm(li.textContent));
}

async function openL01(): Promise<string[]> {
  const list = labList();
  const finished = {
    ...list,
    lessons: list.lessons.map((l) => (l.id === "l01" ? { ...l, state: "finished" as const } : l)),
  };
  renderPage("/lab?lesson=l01", { api: labApi(finished, { l01: l01Done() }) });
  await screen.findByRole("heading", { name: "Lesson 1: What a fine-tune does" });
  await screen.findByRole("heading", { name: "What happened" });
  return whatHappened();
}

describe("AC11.4.6 what happened for a lesson with a single variant", () => {
  it("AC11.4.6 names the one variant as having the lowest dev loss after training, to 3 decimals", async () => {
    const items = await openL01();
    expect(
      items.some((t) => t.includes("Baseline") && /lowest/i.test(t) && hasToken(t, "1.235")),
      items.join("\n"),
    ).toBe(true);
  });

  it("AC11.4.6 for one variant it does not say that differences between variants are noise", async () => {
    const items = await openL01();
    const text = items.join(" ");
    expect(text).not.toMatch(/few hundredths/i);
    expect(text).not.toMatch(/noise/i);
  });
});
