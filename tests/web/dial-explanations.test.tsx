/**
 * Part W2 (u5-website, batch-6): the explanations in the dials panel. AC4.6.8 is the "Explain
 * <label>" button of the method choice and of each of the eleven dials, plus "Explain all
 * settings"; AC4.6.9 is the "How training uses your NVIDIA GPU" button. Tested through
 * `RunControls`, which renders the dials panel, under the fake run service; the expected text
 * comes from `DIAL_INFO` and `GPU_NOTES` (`@/lib/dial-info`). Only the DOM contract of
 * construction/batch-6.md is used: buttons by accessible name, `aria-expanded`, `aria-controls`.
 */
import { RunControls } from "@/components/run-controls";
import { DIAL_INFO, GPU_NOTES, type DialInfo } from "@/lib/dial-info";
import { DIALS, Q17, fakeApi, serviceStatus, type FakeApi } from "@/test/fake-api";
import { renderWithApi, screen, userEvent, waitFor } from "@/test/utils";

const IDLE = serviceStatus();

function renderControls(api: FakeApi = fakeApi()) {
  return renderWithApi(
    <RunControls status={IDLE} queue={[]} onChanged={vi.fn<() => void>()} />,
    api,
  );
}

/** Waits until the dials from `GET /dials` are on screen. */
async function dialsReady(): Promise<void> {
  await screen.findByLabelText("Learning rate");
}

function normalize(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

/** The method choice and the eleven dials of the fake `GET /dials`, in panel order. */
interface Setting {
  key: string;
  label: string;
}
const SETTINGS: Setting[] = [
  { key: "method", label: "Method" },
  ...DIALS.map((dial) => ({ key: dial.name, label: dial.label })),
];

function infoFor(key: string): DialInfo {
  const info = (DIAL_INFO as Record<string, DialInfo | undefined>)[key];
  if (!info) throw new Error(`DIAL_INFO has no entry for ${key}`);
  return info;
}

function explainButton(label: string): HTMLElement {
  return screen.getByRole("button", { name: `Explain ${label}` });
}

function allSettingsButtons(): Array<Setting & { button: HTMLElement }> {
  return SETTINGS.map((setting) => ({ ...setting, button: explainButton(setting.label) }));
}

/** The element `button` controls, when it exists and is not hidden; else null. */
function shownPanel(button: HTMLElement): HTMLElement | null {
  const id = button.getAttribute("aria-controls");
  if (!id) return null;
  const panel = document.getElementById(id);
  if (!panel || panel.closest("[hidden]")) return null;
  return panel;
}

function expanded(button: HTMLElement): string | null {
  expect(button.isConnected, "the button is still on the page").toBe(true);
  return button.getAttribute("aria-expanded");
}

/** What an explanation must show: what, one line per effect as "<label>: <text>", and the tip. */
function expectExplanation(panel: HTMLElement | null, info: DialInfo, what: string): void {
  expect(panel, `${what} explanation is shown`).not.toBeNull();
  const text = normalize(panel?.textContent);
  expect(text, `${what} what`).toContain(normalize(info.what));
  for (const effect of info.effects) {
    expect(text, `${what} effect ${effect.label}`).toContain(
      normalize(`${effect.label}: ${effect.text}`),
    );
  }
  expect(text, `${what} tip`).toContain(normalize(`Tip: ${info.tip}`));
}

function startButton(): HTMLElement {
  return screen.getByRole("button", { name: "Start run" });
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

/** Loops over twelve buttons with several queries each: more time than the 5 s default. */
const LOOP_TIMEOUT = 30_000;

describe("dials panel, Explain buttons (AC4.6.8)", () => {
  it(
    "AC4.6.8 gives the method choice and each of the eleven dials an Explain button that starts closed",
    async () => {
      renderControls();
      await dialsReady();

      expect(SETTINGS).toHaveLength(12);
      const controlled = new Set<string>();
      for (const { key, label } of SETTINGS) {
        const info = infoFor(key);
        expect(normalize(info.what), `${label} what`).not.toBe("");
        expect(info.effects.length, `${label} effects`).toBeGreaterThanOrEqual(2);
        for (const effect of info.effects) {
          expect(normalize(effect.label), `${label} effect label`).not.toBe("");
          expect(normalize(effect.text), `${label} effect text`).not.toBe("");
        }
        expect(normalize(info.tip), `${label} tip`).not.toBe("");

        const button = explainButton(label);
        expect(button, `${label} is a native button`).toHaveProperty("tagName", "BUTTON");
        expect(button).toHaveAttribute("type", "button");
        expect(button).toHaveTextContent("Explain");
        expect(button).toHaveAttribute("aria-expanded", "false");
        const id = button.getAttribute("aria-controls");
        expect(id, `${label} aria-controls`).toBeTruthy();
        controlled.add(String(id));
        expect(shownPanel(button), `${label} explanation starts hidden`).toBeNull();
      }
      expect(controlled.size, "each button controls its own element").toBe(SETTINGS.length);
    },
    LOOP_TIMEOUT,
  );

  it(
    "AC4.6.8 shows what a setting does, what higher and lower do and a tip when its Explain button is pressed, and hides them on a second press",
    async () => {
      const user = userEvent.setup();
      renderControls();
      await dialsReady();
      const settings = allSettingsButtons();

      for (const { key, label, button } of settings) {
        await user.click(button);
        expect(expanded(button), `${label} after the first press`).toBe("true");
        expectExplanation(shownPanel(button), infoFor(key), label);
        // Only this explanation is open.
        for (const other of settings) {
          if (other.key !== key)
            expect(expanded(other.button), `${other.label} stays closed`).toBe("false");
        }

        await user.click(button);
        expect(expanded(button), `${label} after the second press`).toBe("false");
        expect(shownPanel(button), `${label} explanation is gone`).toBeNull();
      }
    },
    LOOP_TIMEOUT,
  );

  it("AC4.6.8 lets several explanations stay open at once", async () => {
    const user = userEvent.setup();
    renderControls();
    await dialsReady();
    const epochs = explainButton("Epochs");
    const rank = explainButton("LoRA rank");
    const method = explainButton("Method");

    await user.click(epochs);
    await user.click(rank);
    await user.click(method);

    for (const [button, key] of [
      [epochs, "epochs"],
      [rank, "lora_rank"],
      [method, "method"],
    ] as const) {
      expect(button).toHaveAttribute("aria-expanded", "true");
      expectExplanation(shownPanel(button), infoFor(key), key);
    }
    await user.click(rank);
    expect(rank).toHaveAttribute("aria-expanded", "false");
    expect(epochs).toHaveAttribute("aria-expanded", "true");
    expect(method).toHaveAttribute("aria-expanded", "true");
  });

  it(
    "AC4.6.8 opens every explanation from Explain all settings, which then reads Hide all explanations, and closes them all again",
    async () => {
      const user = userEvent.setup();
      renderControls();
      await dialsReady();
      const settings = allSettingsButtons();

      const all = screen.getByRole("button", { name: "Explain all settings" });
      expect(all).toHaveAttribute("type", "button");
      // It sits above the fields.
      expect(
        all.compareDocumentPosition(screen.getByLabelText("Learning rate")) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();

      await user.click(all);

      expect(screen.getByRole("button", { name: "Hide all explanations" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Explain all settings" })).toBeNull();
      for (const { key, label, button } of settings) {
        expect(expanded(button), `${label} is open`).toBe("true");
        expectExplanation(shownPanel(button), infoFor(key), label);
      }

      await user.click(screen.getByRole("button", { name: "Hide all explanations" }));

      expect(screen.getByRole("button", { name: "Explain all settings" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Hide all explanations" })).toBeNull();
      for (const { label, button } of settings) {
        expect(expanded(button), `${label} is closed`).toBe("false");
        expect(shownPanel(button), `${label} explanation is gone`).toBeNull();
      }
    },
    LOOP_TIMEOUT,
  );

  it(
    "AC4.6.8 opens an explanation that was already open from Explain all settings and keeps single buttons working after it",
    async () => {
      const user = userEvent.setup();
      renderControls();
      await dialsReady();
      const settings = allSettingsButtons();
      const epochs = explainButton("Epochs");
      const model = explainButton("Model");

      // One open first: Explain all settings leaves it open and opens the rest.
      await user.click(epochs);
      await user.click(screen.getByRole("button", { name: "Explain all settings" }));
      for (const { label, button } of settings) {
        expect(expanded(button), `${label} is open`).toBe("true");
      }

      // A single button still closes just its own explanation, and opens it again.
      await user.click(epochs);
      expect(epochs).toHaveAttribute("aria-expanded", "false");
      expect(shownPanel(epochs)).toBeNull();
      for (const { label, button } of settings) {
        if (button !== epochs) expect(expanded(button), `${label} stays open`).toBe("true");
      }
      await user.click(epochs);
      expect(epochs).toHaveAttribute("aria-expanded", "true");
      expectExplanation(shownPanel(epochs), infoFor("epochs"), "Epochs");

      await user.click(model);
      expect(model).toHaveAttribute("aria-expanded", "false");
      expect(shownPanel(model)).toBeNull();
      expect(epochs).toHaveAttribute("aria-expanded", "true");
    },
    LOOP_TIMEOUT,
  );

  it("AC4.6.8 never changes a typed value or the Start button when explanations open or close", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    const rate = await setDial(user, "Learning rate", "0.0003");
    const model = screen.getByLabelText("Model") as HTMLSelectElement;
    await user.selectOptions(model, Q17);
    expect(startButton()).toBeEnabled();

    await user.click(explainButton("Learning rate"));
    await user.click(explainButton("Model"));
    await user.click(screen.getByRole("button", { name: "Explain all settings" }));
    expect(rate.value).toBe("0.0003");
    expect(model.value).toBe(Q17);
    expect(startButton()).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Hide all explanations" }));
    await user.click(explainButton("Learning rate"));
    expect(rate.value).toBe("0.0003");
    expect(model.value).toBe(Q17);
    expect(api.checkRun).not.toHaveBeenCalled();

    // Start still works with explanations open.
    await user.click(screen.getByRole("button", { name: "Explain all settings" }));
    await user.click(startButton());
    expect(await screen.findByRole("dialog", { name: "Confirm run" })).toBeInTheDocument();
    expect(api.checkRun).toHaveBeenCalledTimes(1);
  });

  it("AC4.6.8 never clears an error or enables Start when explanations open or close", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    const rate = await setDial(user, "Learning rate", "0.1");
    const message = "Learning rate must be between 1e-5 and 5e-4";
    expect(await screen.findByText(message)).toBeVisible();
    expect(startButton()).toBeDisabled();

    const expectUnchanged = () => {
      expect(screen.getByText(message)).toBeVisible();
      expect(rate).toHaveAttribute("aria-invalid", "true");
      expect(rate.value).toBe("0.1");
      expect(startButton()).toBeDisabled();
      expect(screen.getByText("Fix the highlighted dial to start")).toBeInTheDocument();
    };

    await user.click(explainButton("Learning rate"));
    expectUnchanged();
    await user.click(screen.getByRole("button", { name: "Explain all settings" }));
    expectUnchanged();
    await user.click(screen.getByRole("button", { name: "Hide all explanations" }));
    expectUnchanged();
    expect(api.checkRun).not.toHaveBeenCalled();
  });

  it("AC4.6.8 gives a dial without an explanation no Explain button", async () => {
    const saved = DIAL_INFO.seed;
    delete DIAL_INFO.seed;
    try {
      renderControls();
      await dialsReady();

      expect(screen.getByLabelText("Random seed")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Explain Random seed" })).toBeNull();
      expect(explainButton("Epochs")).toBeInTheDocument();
      expect(explainButton("Method")).toBeInTheDocument();
    } finally {
      DIAL_INFO.seed = saved;
    }
  });
});

describe("dials panel, NVIDIA GPU notes (AC4.6.9)", () => {
  const BUTTON = "How training uses your NVIDIA GPU";

  it("AC4.6.9 lists what every fine-tune already does on the GPU behind a How training uses your NVIDIA GPU button", async () => {
    const user = userEvent.setup();
    renderControls();
    await dialsReady();

    const button = screen.getByRole("button", { name: BUTTON });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button.getAttribute("aria-controls")).toBeTruthy();
    expect(shownPanel(button)).toBeNull();

    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    const panel = shownPanel(button);
    expect(panel, "the notes are shown").not.toBeNull();
    const list = panel?.matches("ul") ? panel : (panel?.querySelector("ul") ?? null);
    expect(list, "a <ul>").not.toBeNull();
    const items = Array.from(list?.querySelectorAll(":scope > li") ?? []);
    expect(GPU_NOTES).toHaveLength(5);
    expect(items).toHaveLength(5);
    for (const note of GPU_NOTES) {
      const match = items.find((item) => {
        const text = normalize(item.textContent);
        return text.includes(normalize(note.name)) && text.includes(normalize(note.why));
      });
      expect(match, `an item with "${note.name}" and its reason`).toBeDefined();
    }

    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(shownPanel(button)).toBeNull();
  });

  it("AC4.6.9 names bf16, the fused AdamW optimiser, gradient checkpointing, LoRA adapters and the linear learning-rate decay", async () => {
    const user = userEvent.setup();
    renderControls();
    await dialsReady();

    await user.click(screen.getByRole("button", { name: BUTTON }));

    const panel = shownPanel(screen.getByRole("button", { name: BUTTON }));
    const text = normalize(panel?.textContent);
    expect(text).toMatch(/bf16/i);
    expect(text).toMatch(/fused AdamW/i);
    expect(text).toMatch(/gradient checkpointing/i);
    expect(text).toMatch(/LoRA/);
    expect(text).toMatch(/linear learning-rate decay/i);
  });

  it("AC4.6.9 sits at the end of the dials panel, after the last dial", async () => {
    renderControls();
    await dialsReady();

    const button = screen.getByRole("button", { name: BUTTON });
    const last = screen.getByLabelText("Answer format");
    expect(last.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(
      explainButton("Answer format").compareDocumentPosition(button) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("AC4.6.9 never changes a typed value or the Start button when the notes open or close", async () => {
    const user = userEvent.setup();
    const api = fakeApi();
    renderControls(api);
    await dialsReady();

    const rate = await setDial(user, "Learning rate", "0.0003");
    expect(startButton()).toBeEnabled();

    const button = screen.getByRole("button", { name: BUTTON });
    await user.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-expanded", "true"));
    expect(rate.value).toBe("0.0003");
    expect(startButton()).toBeEnabled();

    await user.click(button);
    expect(rate.value).toBe("0.0003");
    expect(startButton()).toBeEnabled();
    expect(api.checkRun).not.toHaveBeenCalled();
  });
});
