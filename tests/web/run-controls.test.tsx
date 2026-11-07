/**
 * Part W4, run controls (u5-website, US4.6): the dials panel, Start and Stop, the confirm and stop
 * dialogs, the "Queued runs" list and the page's polite status line, tested through
 * `RunControls({status, queue, onChanged})` under a fake run service.
 */
import { useState } from "react";
import { MemoryRouter } from "react-router";

import { RunControls } from "@/components/run-controls";
import { UNREACHABLE_MESSAGE, type QueueEntry, type Status } from "@/lib/api";
import { ApiProvider } from "@/lib/api-context";
import {
  DIALS,
  Q06,
  Q17,
  apiError,
  checkedRun,
  fakeApi,
  queueEntry,
  serviceStatus,
  withQueue,
  type FakeApi,
} from "@/test/fake-api";
import { act, renderWithApi, screen, userEvent, waitFor, within } from "@/test/utils";

const IDLE = serviceStatus();

function running(runId = "q06-sft-dev-3"): Status {
  return serviceStatus({ status: "RUNNING", run_id: runId, started_at: "2026-11-04T20:10:00Z" });
}

interface ControlsProps {
  status?: Status | null;
  queue?: QueueEntry[];
}

/** Renders RunControls under `api`; `rerender` keeps the same tree, so component state stays. */
function renderControls(api: FakeApi, props: ControlsProps = {}) {
  const onChanged = vi.fn<() => void>();
  const element = (next: ControlsProps) => (
    <RunControls
      status={next.status === undefined ? IDLE : next.status}
      queue={next.queue ?? []}
      onChanged={onChanged}
    />
  );
  const result = renderWithApi(element(props), api);
  const rerender = (next: ControlsProps) =>
    result.rerender(
      <ApiProvider api={api}>
        <MemoryRouter>{element(next)}</MemoryRouter>
      </ApiProvider>,
    );
  return { onChanged, rerender };
}

/** Waits until the dials from `GET /dials` are on screen. */
async function dialsReady(): Promise<void> {
  await screen.findByLabelText("Learning rate");
}

function startButton(name: "Start run" | "Add to queue" = "Start run"): HTMLElement {
  return screen.getByRole("button", { name });
}

async function setDial(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  value: string,
): Promise<HTMLInputElement> {
  const field = screen.getByLabelText(label) as HTMLInputElement;
  await user.clear(field);
  await user.type(field, value);
  await user.tab();
  return field;
}

async function openConfirm(
  user: ReturnType<typeof userEvent.setup>,
  name: "Start run" | "Add to queue" = "Start run",
): Promise<HTMLElement> {
  await dialsReady();
  await user.click(startButton(name));
  return screen.findByRole("dialog", { name: "Confirm run" });
}

/** The table cells of the queued-runs row that holds `button`. */
function rowCells(button: HTMLElement): string[] {
  const row = button.closest("tr");
  expect(row).not.toBeNull();
  return Array.from(row!.querySelectorAll("td, th"), (cell) => (cell.textContent ?? "").trim());
}

function queued(): QueueEntry[] {
  return [
    queueEntry({
      position: 1,
      attempt_id: "q06-sft-dev-4",
      config: { model: Q06, method: "sft", split: "dev" },
      added_at: "2026-11-04T20:41:00Z",
    }),
    queueEntry({
      position: 2,
      attempt_id: "q17-sft-dev-3",
      config: { model: Q17, method: "sft", split: "dev" },
      added_at: "2026-11-04T20:43:00Z",
    }),
  ];
}

describe("RunControls: dials (AC4.6.1)", () => {
  it("AC4.6.1 shows all eleven dials with a visible label and their defaults", async () => {
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    expect(screen.getByRole("heading", { name: "Dials" })).toBeInTheDocument();
    expect(api.getDials).toHaveBeenCalled();
    expect(DIALS).toHaveLength(11);
    for (const dial of DIALS) {
      const control = screen.getByLabelText(dial.label) as HTMLInputElement | HTMLSelectElement;
      const label = control.labels?.[0];
      expect(label, `${dial.name} has a native label`).toBeDefined();
      expect(label).toBeVisible();
      expect(label).toHaveTextContent(dial.label);
      if (dial.kind === "select") {
        expect(control.tagName, `${dial.name} is a native select`).toBe("SELECT");
        expect(control.value).toBe(String(dial.default));
      } else if (dial.default === "all") {
        expect(control.value).toBe("all");
      } else {
        expect(Number(control.value), `${dial.name} default`).toBe(dial.default);
      }
    }
  });

  it("AC4.6.1 links each number dial's allowed range as helper text", async () => {
    renderControls(fakeApi());
    await dialsReady();

    for (const dial of DIALS.filter((d) => d.kind !== "select")) {
      expect(screen.getByLabelText(dial.label)).toHaveAccessibleDescription(
        expect.stringContaining(dial.help),
      );
    }
  });

  it("AC4.6.1 names the allowed range for an invalid value and keeps Start disabled", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();
    expect(startButton()).toBeEnabled();

    const field = await setDial(user, "Learning rate", "0.1");
    const message = "Learning rate must be between 1e-5 and 5e-4";
    expect(await screen.findByText(message)).toBeVisible();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(expect.stringContaining(message));
    expect(field.value).toBe("0.1");
    expect(startButton()).toBeDisabled();
    expect(screen.getByText("Fix the highlighted dial to start")).toBeInTheDocument();
    expect(api.checkRun).not.toHaveBeenCalled();

    await setDial(user, "Learning rate", "0.0001");
    await waitFor(() => expect(screen.queryByText(message)).not.toBeInTheDocument());
    expect(field).not.toHaveAttribute("aria-invalid", "true");
    expect(startButton()).toBeEnabled();
  });

  it("AC4.6.1 refuses a fraction for a whole-number dial and a count below the range", async () => {
    const user = userEvent.setup();
    renderControls(fakeApi());
    await dialsReady();

    await setDial(user, "Epochs", "1.5");
    expect(await screen.findByText("Epochs must be a whole number")).toBeVisible();
    expect(startButton()).toBeDisabled();

    await setDial(user, "Epochs", "2");
    await setDial(user, "Training examples", "10");
    expect(await screen.findByText("Training examples must be between 50 and 6973")).toBeVisible();
    expect(screen.queryByText("Epochs must be a whole number")).not.toBeInTheDocument();
    expect(startButton()).toBeDisabled();
  });

  it("AC4.6.1 disables Start with the service message when the dials cannot be loaded", async () => {
    const api = fakeApi({
      getDials: async () => {
        throw apiError("unreachable", UNREACHABLE_MESSAGE);
      },
    });
    renderControls(api);

    expect(await screen.findByText(UNREACHABLE_MESSAGE)).toBeInTheDocument();
    expect(startButton()).toBeDisabled();
  });
});

describe("RunControls: confirm dialog (AC4.6.2-AC4.6.6)", () => {
  it("AC4.6.2 checks the dials and shows the attempt id, model, method, changes, estimate and command", async () => {
    const user = userEvent.setup();
    const check = checkedRun({
      attempt_id: "q06-sft-dev-3",
      model: Q06,
      method: "sft",
      changes: ["learning_rate: 0.0001 -> 0.0002"],
      estimate_s: 2460,
      estimate_text: "about 41 minutes",
    });
    const api = fakeApi({ checkRun: async () => check });
    renderControls(api);

    const dialog = await openConfirm(user);

    expect(api.checkRun).toHaveBeenCalledTimes(1);
    expect(api.checkRun.mock.calls[0]?.[0]).toEqual({
      model: Q06,
      method: "sft",
      split: "dev",
      learning_rate: 2e-4,
      epochs: 1,
      lora_rank: 16,
      lora_alpha: 32,
      max_seq_len: 512,
      train_examples: "all",
      batch_size: 4,
      warmup_ratio: 0.03,
      seed: 42,
      answer_format: "step-by-step",
    });
    expect(dialog).toHaveTextContent(/Run id:?\s*q06-sft-dev-3/);
    expect(dialog).toHaveTextContent(/Model:?\s*(Qwen\/)?Qwen3-0\.6B-Base/);
    expect(dialog).toHaveTextContent(/Method:?\s*SFT/i);
    expect(dialog).toHaveTextContent(/learning[_ ]rate: 0\.0001 -> 0\.0002/i);
    expect(dialog).toHaveTextContent(/Estimated?:?\s*~41 min/);
    expect(dialog).toHaveTextContent(check.command_text);
    expect(dialog).not.toHaveTextContent(/queued behind/i);
    expect(within(dialog).getByRole("button", { name: "Start run" })).toBeInTheDocument();
    expect(api.confirmRun).not.toHaveBeenCalled();
  });

  it("AC4.6.2 says the run waits in the queue and at which position while a run is active", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      checkRun: async () => checkedRun({ attempt_id: "q06-sft-dev-4", queue_position: 2 }),
    });
    renderControls(api, { status: running("q17-sft-dev-1") });

    const dialog = await openConfirm(user, "Add to queue");

    expect(dialog).toHaveTextContent(/queued behind q17-sft-dev-1/i);
    expect(dialog).toHaveTextContent(/position 2/);
    expect(within(dialog).getByRole("button", { name: "Add to queue" })).toBeInTheDocument();
  });

  it("AC4.6.2 Cancel closes the dialog and launches or queues nothing", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    const { onChanged } = renderControls(api);

    const dialog = await openConfirm(user);
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.confirmRun).not.toHaveBeenCalled();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("AC4.6.2 confirming launches the checked run once and closes the dialog", async () => {
    const user = userEvent.setup();
    const api = fakeApi({ checkRun: async () => checkedRun({ check_id: "check-7" }) });
    const { onChanged } = renderControls(api);

    const dialog = await openConfirm(user);
    await user.click(within(dialog).getByRole("button", { name: "Start run" }));

    await waitFor(() => expect(api.confirmRun).toHaveBeenCalledTimes(1));
    expect(api.confirmRun.mock.calls[0]?.[0]).toBe("check-7");
    expect(api.confirmRun.mock.calls[0]?.[1]).toBeFalsy();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(onChanged).toHaveBeenCalled();
  });

  it("AC4.6.2 says First run of this kind when nothing changed and No estimate yet without one", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      checkRun: async () =>
        checkedRun({ changes: [], estimate_s: null, estimate_text: "No estimate yet" }),
    });
    renderControls(api);

    const dialog = await openConfirm(user);

    expect(dialog).toHaveTextContent("First run of this kind");
    expect(dialog).toHaveTextContent("No estimate yet");
  });

  it("AC4.6.2 Evaluate on dev checks only the model, method, split and seed", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    const method = screen.getByLabelText("Method") as HTMLSelectElement;
    expect(within(method).getByRole("option", { name: "SFT" })).toBeInTheDocument();
    await user.selectOptions(method, "Evaluate on dev");
    await user.click(startButton());

    await screen.findByRole("dialog", { name: "Confirm run" });
    expect(api.checkRun.mock.calls[0]?.[0]).toEqual({
      model: Q06,
      method: "base",
      split: "dev",
      seed: 42,
    });
  });

  it("AC4.6.2 shows a check error and opens no dialog", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      checkRun: async () => {
        throw apiError("queue_full", "The queue is full (10 waiting)");
      },
    });
    renderControls(api);
    await dialsReady();

    await user.click(startButton());

    expect(await screen.findByText("The queue is full (10 waiting)")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.confirmRun).not.toHaveBeenCalled();
  });

  it("AC4.6.3 warns above the 3-hour cap and needs a second confirmation before starting", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      checkRun: async () =>
        checkedRun({ estimate_s: 13200, estimate_text: "about 3 h 40 min", over_cap: true }),
    });
    renderControls(api);

    const dialog = await openConfirm(user);
    expect(dialog).toHaveTextContent("Estimated time is above the 3-hour cap.");

    await user.click(within(dialog).getByRole("button", { name: "Start anyway" }));
    const ask = await screen.findByText(/Start a run estimated at 3 h 40 min\?/);
    expect(api.confirmRun).not.toHaveBeenCalled();

    const askDialog = ask.closest<HTMLElement>('[role="dialog"], [role="alertdialog"]');
    expect(askDialog).not.toBeNull();
    expect(within(askDialog!).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    await user.click(within(askDialog!).getByRole("button", { name: "Start anyway" }));

    await waitFor(() => expect(api.confirmRun).toHaveBeenCalledTimes(1));
    expect(api.confirmRun.mock.calls[0]?.[0]).toBe("check-1");
  });

  it("AC4.6.3 Cancel at the second confirmation starts nothing", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      checkRun: async () => checkedRun({ estimate_s: 13200, over_cap: true }),
    });
    renderControls(api);

    const dialog = await openConfirm(user);
    await user.click(within(dialog).getByRole("button", { name: "Start anyway" }));
    const ask = await screen.findByText(/Start a run estimated at 3 h 40 min\?/);
    const askDialog = ask.closest<HTMLElement>('[role="dialog"], [role="alertdialog"]');
    await user.click(within(askDialog!).getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByText(/Start a run estimated at/)).not.toBeInTheDocument(),
    );
    expect(api.confirmRun).not.toHaveBeenCalled();
  });

  it("AC4.6.3 a run within the cap shows no warning", async () => {
    const user = userEvent.setup();
    renderControls(fakeApi());

    const dialog = await openConfirm(user);

    expect(dialog).not.toHaveTextContent(/above the 3-hour cap/);
    expect(within(dialog).queryByRole("button", { name: "Start anyway" })).not.toBeInTheDocument();
  });

  it("AC4.6.5 keeps the dialog open and shows why the launch failed", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      confirmRun: async () => {
        throw apiError("queue_full", "The queue is full (10 waiting)");
      },
    });
    const { onChanged } = renderControls(api);

    const dialog = await openConfirm(user);
    await user.click(within(dialog).getByRole("button", { name: "Start run" }));

    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("The queue is full (10 waiting)");
    expect(screen.getByRole("dialog", { name: "Confirm run" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeEnabled();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("AC4.6.6 keeps focus inside the dialog, Escape cancels and focus returns to Start", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    const start = startButton();
    act(() => start.focus());
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Confirm run" });

    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus(),
    );
    for (let i = 0; i < 8; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement), `focus after Tab ${i + 1}`).toBe(true);
    }
    for (let i = 0; i < 4; i += 1) {
      await user.tab({ shift: true });
      expect(dialog.contains(document.activeElement), `focus after Shift+Tab ${i + 1}`).toBe(true);
    }

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.confirmRun).not.toHaveBeenCalled();
    await waitFor(() => expect(start).toHaveFocus());
  });

  it("AC4.6.6 focus returns to Start after Cancel", async () => {
    const user = userEvent.setup();
    renderControls(fakeApi());
    await dialsReady();
    const start = startButton();

    await user.click(start);
    const dialog = await screen.findByRole("dialog", { name: "Confirm run" });
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(start).toHaveFocus());
  });
});

describe("RunControls: active run, status and stop (AC4.6.4)", () => {
  it("AC4.6.4 idle: Start run enabled and Stop disabled", async () => {
    renderControls(fakeApi());
    await dialsReady();

    expect(startButton()).toBeEnabled();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Add to queue" })).not.toBeInTheDocument();
  });

  it("AC4.6.4 an active run turns Start into Add to queue, enables Stop and announces politely", async () => {
    const api = fakeApi();
    const { rerender } = renderControls(api, { status: IDLE });
    await dialsReady();
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");

    rerender({ status: running("q06-sft-dev-3") });

    expect(await screen.findByRole("button", { name: "Add to queue" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Start run" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
    expect(screen.getByRole("status")).toBe(region);
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent(/q06-sft-dev-3/);
    expect(region).toHaveTextContent(/running/i);
    expect(screen.getByLabelText("Learning rate")).toBeEnabled();
  });

  it("AC4.6.4 disables Add to queue when 10 runs wait", async () => {
    const full = Array.from({ length: 10 }, (_, i) =>
      queueEntry({ position: i + 1, attempt_id: `q06-sft-dev-${i + 10}` }),
    );
    renderControls(fakeApi(), { status: running("q06-sft-dev-3"), queue: full });
    await dialsReady();

    expect(startButton("Add to queue")).toBeDisabled();
    expect(screen.getByText("The queue is full (10 waiting)")).toBeInTheDocument();
  });

  it("AC4.6.4 Stop asks first: Keep running stops nothing, Stop run calls the service", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    const { onChanged } = renderControls(api, { status: running("q06-sft-dev-3") });
    await dialsReady();
    const stop = screen.getByRole("button", { name: "Stop" });

    await user.click(stop);
    let dialog = await screen.findByRole("alertdialog", { name: "Stop q06-sft-dev-3?" });
    expect(dialog).toHaveTextContent(/no score is recorded/);
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "Keep running" })).toHaveFocus(),
    );
    await user.click(within(dialog).getByRole("button", { name: "Keep running" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(api.stop).not.toHaveBeenCalled();
    await waitFor(() => expect(stop).toHaveFocus());

    await user.click(stop);
    dialog = await screen.findByRole("alertdialog", { name: "Stop q06-sft-dev-3?" });
    await user.click(within(dialog).getByRole("button", { name: "Stop run" }));

    await waitFor(() => expect(api.stop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(onChanged).toHaveBeenCalled();
  });

  it("AC4.6.4 Stop on a run that already ended says so with a Close button", async () => {
    const user = userEvent.setup();
    const api = fakeApi({
      stop: async () => {
        throw apiError("no_active_run", "No run is active");
      },
    });
    renderControls(api, { status: running("q06-sft-dev-3") });
    await dialsReady();

    await user.click(screen.getByRole("button", { name: "Stop" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Stop q06-sft-dev-3?" });
    await user.click(within(dialog).getByRole("button", { name: "Stop run" }));

    expect(await screen.findByText("This run has already ended.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });
});

describe("RunControls: queued runs (AC4.6.7)", () => {
  it("AC4.6.7 lists each waiting run's position, attempt id, model and method with Remove", async () => {
    const user = userEvent.setup();
    const api = withQueue(fakeApi(), queued());
    const { onChanged } = renderControls(api, {
      status: running("q06-sft-dev-3"),
      queue: queued(),
    });
    await dialsReady();

    expect(screen.getByRole("heading", { name: "Queued runs" })).toBeInTheDocument();
    const removes = screen.getAllByRole("button", { name: /Remove/ });
    expect(removes).toHaveLength(2);

    const first = rowCells(removes[0]!);
    expect(first).toContain("1");
    expect(first).toContain("q06-sft-dev-4");
    expect(first.some((cell) => /0\.6B/.test(cell))).toBe(true);
    expect(first.some((cell) => /^sft$/i.test(cell))).toBe(true);

    const second = rowCells(removes[1]!);
    expect(second).toContain("2");
    expect(second).toContain("q17-sft-dev-3");
    expect(second.some((cell) => /1\.7B/.test(cell))).toBe(true);
    expect(second.some((cell) => /^sft$/i.test(cell))).toBe(true);

    await user.click(removes[0]!);
    await waitFor(() => expect(api.removeQueued).toHaveBeenCalledWith("q06-sft-dev-4"));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("AC4.6.7 hides the list when no run is waiting", async () => {
    renderControls(fakeApi(), { status: running("q06-sft-dev-3"), queue: [] });
    await dialsReady();

    expect(screen.queryByRole("heading", { name: "Queued runs" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
  });

  it("AC4.6.7 after Remove focus moves to the next Remove button, then to Start", async () => {
    const user = userEvent.setup();
    const api = withQueue(fakeApi(), queued());

    function Page() {
      const [queue, setQueue] = useState<QueueEntry[]>(queued());
      return (
        <RunControls
          status={IDLE}
          queue={queue}
          onChanged={() => {
            void api.getQueue().then(setQueue);
          }}
        />
      );
    }
    renderWithApi(<Page />, api);
    await dialsReady();

    await user.click(screen.getAllByRole("button", { name: /Remove/ })[0]!);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /Remove/ })).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole("button", { name: /Remove/ })).toHaveFocus());

    await user.click(screen.getByRole("button", { name: /Remove/ }));
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Queued runs" })).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(startButton()).toHaveFocus());
  });
});
