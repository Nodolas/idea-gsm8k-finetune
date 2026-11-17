/**
 * Gap-1 part W3 (u5-website): AC4.2.4 with the operating system's reduce-motion setting on, the
 * halftone dots stay still and no pointer or click animation runs.
 *
 * Through the app's router (the landing page), under a recording 2D context, stubbed animation
 * frames and a stubbed element size (jsdom has no canvas and no layout; the harness follows the
 * AC4.2.7 one in `landing-halftone.test.tsx`). Moving the pointer over the wordmark and pressing
 * on it must request no animation frame and draw nothing, while the same events with motion
 * allowed (the live case) do request a frame, so the check cannot pass by the events doing
 * nothing in this harness.
 */
import { fakeApi } from "@/test/fake-api";
import { fireEvent, renderPage, screen, waitFor } from "@/test/utils";

const FRAME_60 = 1000 / 60;
const MAX_SETTLE_FRAMES = 900;

const counts = new Map<string, number>();
let frames = new Map<number, FrameRequestCallback>();
let nextFrameId = 1;
let clock = 1000;
let requested = 0;

const ORIGINAL_GET_CONTEXT = Object.getOwnPropertyDescriptor(
  HTMLCanvasElement.prototype,
  "getContext",
);
const ORIGINAL_RECT = Object.getOwnPropertyDescriptor(Element.prototype, "getBoundingClientRect");

function bump(name: string) {
  counts.set(name, (counts.get(name) ?? 0) + 1);
}

/** A 2D context that counts every method call; the word mask is fully inked everywhere. */
function makeContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const state: Record<string, unknown> = {
    canvas,
    font: "10px sans-serif",
    textBaseline: "alphabetic",
    textAlign: "start",
    fillStyle: "#000",
    strokeStyle: "#000",
    globalAlpha: 1,
    globalCompositeOperation: "source-over",
  };
  const methods: Record<string, (...args: unknown[]) => unknown> = {
    measureText: (text) => {
      const width = 6 * String(text).length;
      return {
        width,
        actualBoundingBoxAscent: 7,
        actualBoundingBoxDescent: 0.2,
        actualBoundingBoxLeft: 0,
        actualBoundingBoxRight: width,
        fontBoundingBoxAscent: 9,
        fontBoundingBoxDescent: 2.5,
      };
    },
    getImageData: (_x, _y, w, h) => {
      const width = Number(w);
      const height = Number(h);
      return { width, height, data: new Uint8ClampedArray(width * height * 4).fill(255) };
    },
    createImageData: (w, h) => {
      const width = Number(w);
      const height = Number(h);
      return { width, height, data: new Uint8ClampedArray(width * height * 4) };
    },
    createPattern: () => ({ setTransform: () => {} }),
  };
  return new Proxy(state, {
    get(target, prop) {
      if (typeof prop !== "string") return undefined;
      if (prop in methods) {
        return (...args: unknown[]) => {
          bump(prop);
          return methods[prop](...args);
        };
      }
      if (prop in target) return target[prop];
      return () => {
        bump(prop);
        return undefined;
      };
    },
    set(target, prop, value) {
      if (typeof prop === "string") target[prop] = value;
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
}

function installCanvasStubs() {
  counts.clear();
  frames = new Map();
  nextFrameId = 1;
  clock = 1000;
  requested = 0;
  const contexts = new WeakMap<HTMLCanvasElement, CanvasRenderingContext2D>();
  Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
    configurable: true,
    writable: true,
    value: function getContext(this: HTMLCanvasElement) {
      let ctx = contexts.get(this);
      if (!ctx) {
        ctx = makeContext(this);
        contexts.set(this, ctx);
      }
      return ctx;
    },
  });
  Object.defineProperty(Element.prototype, "getBoundingClientRect", {
    configurable: true,
    writable: true,
    value: () => ({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 1200,
      bottom: 520,
      width: 1200,
      height: 520,
      toJSON: () => ({}),
    }),
  });
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    const id = nextFrameId++;
    requested += 1;
    frames.set(id, cb);
    return id;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => {
    frames.delete(id);
  });
  vi.spyOn(performance, "now").mockImplementation(() => clock);
}

function restoreCanvasStubs() {
  if (ORIGINAL_GET_CONTEXT) {
    Object.defineProperty(HTMLCanvasElement.prototype, "getContext", ORIGINAL_GET_CONTEXT);
  }
  if (ORIGINAL_RECT) {
    Object.defineProperty(Element.prototype, "getBoundingClientRect", ORIGINAL_RECT);
  }
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
}

/** Runs the pending animation frames, one 60 Hz step at a time, until the loop sleeps. */
function settle(maxFrames = MAX_SETTLE_FRAMES): number {
  let n = 0;
  while (frames.size > 0 && n < maxFrames) {
    clock += FRAME_60;
    const due = [...frames.values()];
    frames = new Map();
    for (const cb of due) cb(clock);
    n += 1;
  }
  return n;
}

/** Renders the landing page and returns the halftone canvas once the loop has gone to sleep. */
async function landingCanvas(reducedMotion: boolean): Promise<HTMLCanvasElement> {
  renderPage("/", { api: fakeApi(), reducedMotion });
  await screen.findByRole("heading", { level: 1, name: "gsm8k" });
  const canvas = await waitFor(() => {
    const el = document.querySelector<HTMLCanvasElement>("main canvas");
    if (!el) throw new Error("no halftone canvas on the landing page");
    return el;
  });
  expect(settle(), "the dots come to rest").toBeLessThan(MAX_SETTLE_FRAMES);
  expect(frames.size).toBe(0);
  return canvas;
}

describe("AC4.2.4 reduce motion keeps the landing dots still", () => {
  beforeEach(() => installCanvasStubs());
  afterEach(() => restoreCanvasStubs());

  it("AC4.2.4 with reduce motion on, pointer move over the wordmark requests no frame and draws nothing", async () => {
    const canvas = await landingCanvas(true);
    const before = requested;
    counts.clear();
    fireEvent.pointerMove(canvas, { clientX: 600, clientY: 260 });
    fireEvent.pointerMove(canvas, { clientX: 640, clientY: 270 });
    expect(requested, "no animation frame is requested by a pointer move").toBe(before);
    expect(frames.size).toBe(0);
    expect(settle()).toBe(0);
    expect([...counts.keys()], "nothing is drawn after a pointer move").toEqual([]);
  });

  it("AC4.2.4 with reduce motion on, pointer down (click) on the wordmark requests no frame and draws nothing", async () => {
    const canvas = await landingCanvas(true);
    const before = requested;
    counts.clear();
    fireEvent.pointerDown(canvas, { clientX: 600, clientY: 260 });
    expect(requested, "no animation frame is requested by a click").toBe(before);
    expect(frames.size).toBe(0);
    expect(settle()).toBe(0);
    expect([...counts.keys()], "no ring or dot is drawn after a click").toEqual([]);
  });

  it("AC4.2.4 with reduce motion on, a move followed by a press and another move still runs no animation", async () => {
    const canvas = await landingCanvas(true);
    const before = requested;
    counts.clear();
    fireEvent.pointerMove(canvas, { clientX: 300, clientY: 200 });
    fireEvent.pointerDown(canvas, { clientX: 300, clientY: 200 });
    fireEvent.pointerMove(canvas, { clientX: 900, clientY: 300 });
    expect(frames.size).toBe(0);
    expect(settle()).toBe(0);
    expect(requested).toBe(before);
    expect([...counts.keys()]).toEqual([]);
  });

  it("AC4.2.4 the same events with motion allowed do request a frame and move the dots", async () => {
    const canvas = await landingCanvas(false);
    const before = requested;
    counts.clear();
    fireEvent.pointerMove(canvas, { clientX: 600, clientY: 260 });
    expect(requested, "the live page asks for a frame on pointer move").toBeGreaterThan(before);
    expect(frames.size).toBeGreaterThan(0);
    // The pointer stays over the word, so the dots keep moving: a few frames are enough.
    expect(settle(5), "the live loop keeps running frames").toBe(5);
    expect(counts.get("arc") ?? 0, "the live page redraws its dots").toBeGreaterThan(0);

    // Let the pointer go and the dots come home, so the loop sleeps before the click.
    fireEvent.pointerLeave(canvas.parentElement as HTMLElement);
    expect(settle(), "the dots come home").toBeLessThan(MAX_SETTLE_FRAMES);
    expect(frames.size).toBe(0);
    const afterMove = requested;
    fireEvent.pointerDown(canvas, { clientX: 600, clientY: 260 });
    expect(requested, "the live page asks for a frame on click").toBeGreaterThan(afterMove);
    expect(frames.size).toBeGreaterThan(0);
  });
});
