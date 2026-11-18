/**
 * Gap-2 part W (u11-finetune-lab): AC11.4.6 for the lessons the first Lab tests left loose.
 *
 * - `l12` lists the variant with the lowest dev loss after training and its value (3 decimals) in
 *   addition to its timing and padding sentences.
 * - `l11` states the spread of the last dev loss across seeds and that smaller differences in the
 *   other lessons are noise.
 * - Regression: `l09` still states the higher accuracy and the format rates (no lowest dev loss
 *   sentence); an ordinary lesson (`l02`) still states the lowest dev loss.
 *
 * Text, roles and data-* only, as in `lab.test.tsx` (its fixtures and helpers, trimmed).
 */
import {
  type LabLesson,
  type LabList,
  type LabMetricsLine,
  type LabSummary,
  type LabState,
} from "@/lib/api";
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

/** A finished lesson: every variant has a summary (a normal run plus `specs`) and lines. */
function finishedLesson(lessonId: string, specs: Record<string, Partial<LabSummary>>): LabLesson {
  const base = labLesson(lessonId);
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
        lesson: lessonId,
        variant: r.name,
        label: r.label,
        steps: TOTAL,
        train_loss_first: 2.9,
        train_loss_last: 1.4,
        dev_loss_before: 2.8,
        dev_loss_best_step: TOTAL,
        ...specs[r.name],
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

async function open(
  lessonId: string,
  number: number,
  title: string,
  lesson: LabLesson,
): Promise<string[]> {
  const list = labList();
  const finished = {
    ...list,
    lessons: list.lessons.map((l) =>
      l.id === lessonId ? { ...l, state: "finished" as LabState } : l,
    ),
  };
  renderPage(`/lab?lesson=${lessonId}`, { api: labApi(finished, { [lessonId]: lesson }) });
  await screen.findByRole("heading", { name: `Lesson ${number}: ${title}` });
  await screen.findByRole("heading", { name: "What happened" });
  return whatHappened();
}

/** Lesson l12 finished: "Length-grouped batches" has the lowest dev loss (1.457). */
const L12_DONE = finishedLesson("l12", {
  "tokenize-once": {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: null,
    padding_fraction: 0.31,
    seconds_per_step: 1.26,
    dev_loss_after: 1.612,
    dev_loss_best: 1.612,
  },
  "by-length": {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: null,
    padding_fraction: 0.04,
    seconds_per_step: 1.05,
    dev_loss_after: 1.457,
    dev_loss_best: 1.457,
  },
  retokenize: {
    tokenize_seconds: 2.5,
    retokenize_seconds_per_step: 0.42,
    padding_fraction: 0.31,
    seconds_per_step: 1.68,
    dev_loss_after: 1.589,
    dev_loss_best: 1.589,
  },
});

/** Lesson l11 finished: seeds end at 1.512, 1.534 and 1.498 (spread 0.036). */
const L11_DONE = finishedLesson("l11", {
  "seed-1": { dev_loss_after: 1.512, dev_loss_best: 1.512 },
  "seed-2": { dev_loss_after: 1.534, dev_loss_best: 1.534 },
  "seed-3": { dev_loss_after: 1.498, dev_loss_best: 1.498 },
});

/** Lesson l09 finished: "Final number only" has the lower dev loss, "Step by step" the higher accuracy. */
const L09_DONE = finishedLesson("l09", {
  "step-by-step": {
    dev_loss_after: 1.612,
    dev_loss_best: 1.612,
    accuracy_after: 0.0469,
    format_rate_after: 0.9375,
  },
  terse: {
    dev_loss_after: 0.412,
    dev_loss_best: 0.412,
    accuracy_after: 0.0156,
    format_rate_after: 0.6875,
  },
});

/** Lesson l02 finished: "Learning rate 1e-3" has the lowest dev loss (1.523). */
const L02_DONE = finishedLesson("l02", {
  "lr-1e-5": { dev_loss_after: 1.801, dev_loss_best: 1.801 },
  "lr-1e-4": { dev_loss_after: 1.642, dev_loss_best: 1.642 },
  "lr-1e-3": { dev_loss_after: 1.523, dev_loss_best: 1.523 },
  "lr-1e-2": { dev_loss_after: 1.71, dev_loss_best: 1.71 },
});

describe("AC11.4.6 what happened for lessons l12 and l11, and the lessons around them", () => {
  it("AC11.4.6 for l12 names the variant with the lowest dev loss after training, to 3 decimals", async () => {
    const items = await open("l12", 12, "Where the time goes", L12_DONE);
    const lowest = items.filter((t) => /lowest/i.test(t));
    expect(
      lowest.some((t) => t.includes("Length-grouped batches") && hasToken(t, "1.457")),
      items.join("\n"),
    ).toBe(true);
    for (const other of ["1.612", "1.589"]) {
      expect(
        lowest.some((t) => hasToken(t, other)),
        `${other} is not the lowest`,
      ).toBe(false);
    }
  });

  it("AC11.4.6 for l12 the lowest dev loss comes in addition to the timing and padding sentences", async () => {
    const items = await open("l12", 12, "Where the time goes", L12_DONE);
    const text = items.join(" ");
    expect(text).toMatch(/(?<![\d.])2\.50?(?![\d])/);
    expect(hasToken(text, "0.42")).toBe(true);
    expect(hasToken(text, "31%")).toBe(true);
    expect(hasToken(text, "4%")).toBe(true);
    expect(
      items.some((t) => /lowest/i.test(t) && hasToken(t, "1.457")),
      items.join("\n"),
    ).toBe(true);
  });

  it("AC11.4.6 for l11 states the spread across seeds and that smaller differences in the other lessons are noise", async () => {
    const items = await open("l11", 11, "Seed noise", L11_DONE);
    const sentence = items.find(
      (t) => hasToken(t, "0.036") && /other\s+lessons?/i.test(t) && /noise/i.test(t),
    );
    expect(sentence, items.join("\n")).toBeDefined();
  });

  it("AC11.4.6 for l09 still states the higher accuracy and the format rates, not a lowest dev loss", async () => {
    const items = await open("l09", 9, "Answer format", L09_DONE);
    const text = items.join(" ");
    expect(items.some((t) => t.includes("Step by step") && /accuracy/i.test(t))).toBe(true);
    expect(hasToken(text, "94%")).toBe(true);
    expect(hasToken(text, "69%")).toBe(true);
    expect(
      items.some((t) => /lowest dev loss/i.test(t)),
      text,
    ).toBe(false);
    expect(hasToken(text, "0.412"), text).toBe(false);
  });

  it("AC11.4.6 for l02 still names the variant with the lowest dev loss and its value", async () => {
    const items = await open("l02", 2, "Learning rate", L02_DONE);
    expect(
      items.some(
        (t) => t.includes("Learning rate 1e-3") && /lowest/i.test(t) && hasToken(t, "1.523"),
      ),
      items.join("\n"),
    ).toBe(true);
  });
});
