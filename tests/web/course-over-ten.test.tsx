/**
 * Gap-1 part W1 (u12-learning-course): AC12.1.2 on the Course page. A gpu step's run estimated
 * above 10 minutes is shown with "over 10 minutes" next to its estimate and is never refused:
 * "Run this step" stays enabled. A run estimated at 10 minutes or less shows no such words.
 *
 * Text, roles and data-* hooks only. The fake API and fixtures are the ones `course.test.tsx`
 * uses: the shown step is one `<article data-step="<id>">` and each run an element
 * `[data-run="<run>"]` holding its model, changes, estimate and state word.
 */
import { type CourseStep } from "@/lib/api";
import { courseOverview, courseRun, courseStep, fakeApi, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, waitFor } from "@/test/utils";

const OVER_TEN = "over 10 minutes";

function norm(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

function courseApi(steps: Record<string, CourseStep>): FakeApi {
  return fakeApi({
    getCourse: async () => courseOverview(),
    getCourseStep: async (id: string) => steps[id] ?? courseStep(id),
  });
}

/** Renders `/course?step=<id>` and waits for the shown step. */
async function showStep(api: FakeApi, stepId: string): Promise<void> {
  renderPage(`/course?step=${stepId}`, { api });
  await waitFor(() => {
    if (!document.querySelector(`[data-step="${stepId}"]`)) {
      throw new Error(`no [data-step="${stepId}"]`);
    }
  });
}

async function runText(runName: string): Promise<string> {
  const el = await waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[data-run="${runName}"]`);
    if (!found) throw new Error(`no [data-run="${runName}"]`);
    return found;
  });
  return norm(el.textContent);
}

describe("AC12.1.2 a course run estimated over 10 minutes", () => {
  it("AC12.1.2 shows 'over 10 minutes' with the estimate of a run above 10 minutes", async () => {
    const api = courseApi({
      c05: courseStep("c05", {
        runs: [
          courseRun({ run: "pythia", estimate_minutes: 3 }),
          courseRun({ run: "smollm2", estimate_minutes: 21 }),
        ],
      }),
    });
    await showStep(api, "c05");
    const long = await runText("smollm2");
    expect(long).toContain("about 21 min on the GPU");
    expect(long).toContain(OVER_TEN);
  });

  it("AC12.1.2 shows 'over 10 minutes' for a measured run above 10 minutes too", async () => {
    const api = courseApi({
      c05: courseStep("c05", {
        runs: [courseRun({ run: "pythia", estimate_minutes: 14, estimate_measured: true })],
      }),
    });
    await showStep(api, "c05");
    const text = await runText("pythia");
    expect(text).toContain("about 14 min on the GPU");
    expect(text).not.toContain("estimate, not measured yet");
    expect(text).toContain(OVER_TEN);
  });

  it("AC12.1.2 never refuses it: 'Run this step' stays enabled with a run above 10 minutes", async () => {
    const api = courseApi({
      c05: courseStep("c05", {
        runs: [
          courseRun({ run: "pythia", estimate_minutes: 3 }),
          courseRun({ run: "smollm2", estimate_minutes: 21 }),
        ],
      }),
    });
    await showStep(api, "c05");
    expect(await runText("smollm2")).toContain(OVER_TEN);
    const button = await screen.findByRole("button", { name: "Run this step" });
    expect(button).toBeEnabled();
  });

  it("AC12.1.2 shows no 'over 10 minutes' for runs of 10 minutes or less", async () => {
    const api = courseApi({
      c05: courseStep("c05", {
        runs: [
          courseRun({ run: "pythia", estimate_minutes: 1, estimate_measured: true }),
          courseRun({ run: "smollm2", estimate_minutes: 10 }),
          courseRun({ run: "qwen25", estimate_minutes: 11 }),
        ],
      }),
    });
    await showStep(api, "c05");
    const small = await runText("pythia");
    const ten = await runText("smollm2");
    const eleven = await runText("qwen25");
    expect(small).toContain("about 1 min on the GPU");
    expect(small).not.toContain(OVER_TEN);
    expect(ten).toContain("about 10 min on the GPU");
    expect(ten).not.toContain(OVER_TEN);
    expect(eleven).toContain("about 11 min on the GPU");
    expect(eleven).toContain(OVER_TEN);
  });
});
