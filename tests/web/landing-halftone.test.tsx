/**
 * u5-website, batch-11 part L: the landing wordmark centred, fast and smooth (US4.2,
 * AC4.2.5, AC4.2.7, AC4.2.8).
 *
 * - AC4.2.5 through the app's router: class names and data-* hooks only. The hooks the page and
 *   the component provide: the landing root (the first element child of `main#main`) carries
 *   `min-h-[calc(100svh-3.5rem)]`, `flex` and `flex-col`; the headline section (`[data-motion]`)
 *   is its child, carries `flex-1` and `data-align="center"`; the halftone component's own root
 *   (the nearest `[data-align]` above its canvas) carries `data-align="center"` when given
 *   `align="center"` and `data-align="bottom"` by default.
 * - AC4.2.7 and AC4.2.8 on the halftone module itself: the pure helpers `hwfGap` and `hwfStep`,
 *   and the draw loop under a recording 2D context, stubbed animation frames, a stubbed clock and
 *   a stubbed element size (jsdom has no canvas and no layout).
 */
import { render } from "@testing-library/react";

import HalftoneWordmarkFooter, { hwfGap, hwfStep } from "@/components/ui/halftone-wordmark-footer";
import { fakeApi } from "@/test/fake-api";
import { fireEvent, renderPage, screen } from "@/test/utils";

const MAX_DOTS = 16000;
const FRAME_60 = 1000 / 60;
const FRAME_144 = 1000 / 144;

// ---------------------------------------------------------------------------------------------
// AC4.2.5: the landing page through the router
// ---------------------------------------------------------------------------------------------

const DESCRIPTION = "Teaching small open models grade-school math, one measured run at a time.";

function classesOf(el: Element): string[] {
  return (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
}

/** The landing page's root: the first element child of `<main id="main">`. */
function landingRoot(): Element {
  const main = document.querySelector("main#main");
  expect(main).not.toBeNull();
  const root = main?.firstElementChild ?? null;
  expect(root).not.toBeNull();
  return root as Element;
}

/** The halftone headline section (`data-motion="still" | "live"`). */
function headlineSection(): HTMLElement {
  const section = document.querySelector<HTMLElement>("main [data-motion]");
  expect(section, "the halftone headline section carries data-motion").not.toBeNull();
  return section as HTMLElement;
}

/** The halftone component's root: the nearest element above the canvas carrying data-align. */
function componentRootOf(scope: ParentNode): HTMLElement {
  const canvas = scope.querySelector("canvas");
  expect(canvas, "the halftone component renders a canvas").not.toBeNull();
  const root = canvas?.closest<HTMLElement>("[data-align]") ?? null;
  expect(root, "the halftone component's root carries data-align").not.toBeNull();
  return root as HTMLElement;
}

async function renderLanding() {
  renderPage("/", { api: fakeApi() });
  await screen.findByRole("heading", { level: 1, name: "gsm8k" });
  await screen.findByText(DESCRIPTION);
}

describe("AC4.2.5 the landing wordmark sits centred in the free height", () => {
  it("AC4.2.5 the landing root fills the window height below the top bar as a flex column", async () => {
    await renderLanding();
    const classes = classesOf(landingRoot());
    expect(classes).toContain("min-h-[calc(100svh-3.5rem)]");
    expect(classes).toContain("flex");
    expect(classes).toContain("flex-col");
  });

  it("AC4.2.5 the headline section grows into the free height (flex-1) and carries data-align=center", async () => {
    await renderLanding();
    const section = headlineSection();
    expect(section.parentElement).toBe(landingRoot());
    expect(section).toHaveAttribute("data-align", "center");
    expect(classesOf(section)).toContain("flex-1");
    // The description and buttons stay below the headline.
    const text = screen.getByText(DESCRIPTION);
    expect(section.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(section.contains(text)).toBe(false);
  });

  it("AC4.2.5 the landing page gives the halftone component align=center", async () => {
    await renderLanding();
    const section = headlineSection();
    const root = componentRootOf(section);
    expect(root).not.toBe(section);
    expect(root).toHaveAttribute("data-align", "center");
  });

  it("AC4.2.5 the halftone component defaults to align=bottom, the old placement", () => {
    const { container } = render(
      <HalftoneWordmarkFooter
        wordmark="gsm8k"
        label=""
        meta=""
        columns={[]}
        backToTop={false}
        crop={0}
      />,
    );
    expect(componentRootOf(container)).toHaveAttribute("data-align", "bottom");
  });
});

// ---------------------------------------------------------------------------------------------
// A recording 2D context, stubbed frames, clock and size for the draw loop
// ---------------------------------------------------------------------------------------------

interface TextCall {
  text: string;
  y: number;
  baseline: string;
  px: number;
}

interface Recorder {
  counts: Map<string, number>;
  texts: TextCall[];
}

const recorders = new WeakMap<HTMLCanvasElement, Recorder>();
const totals = new Map<string, number>();
let frames = new Map<number, FrameRequestCallback>();
let nextFrameId = 1;
let clock = 1000;
let size = { width: 2400, height: 520 };

const ORIGINAL_GET_CONTEXT = Object.getOwnPropertyDescriptor(
  HTMLCanvasElement.prototype,
  "getContext",
);
const ORIGINAL_RECT = Object.getOwnPropertyDescriptor(Element.prototype, "getBoundingClientRect");

function bump(map: Map<string, number>, name: string) {
  map.set(name, (map.get(name) ?? 0) + 1);
}

function fontPx(font: unknown): number {
  const m = /(\d+(?:\.\d+)?)px/.exec(String(font));
  return m ? Number(m[1]) : 10;
}

/** A 2D context that records every method call; the word mask is fully inked everywhere. */
function makeContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const rec: Recorder = { counts: new Map(), texts: [] };
  recorders.set(canvas, rec);
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
      const px = fontPx(state.font);
      const width = 0.6 * px * String(text).length;
      return {
        width,
        actualBoundingBoxAscent: 0.7 * px,
        actualBoundingBoxDescent: 0.02 * px,
        actualBoundingBoxLeft: 0,
        actualBoundingBoxRight: width,
        fontBoundingBoxAscent: 0.9 * px,
        fontBoundingBoxDescent: 0.25 * px,
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
    fillText: (text, _x, y) => {
      rec.texts.push({
        text: String(text),
        y: Number(y),
        baseline: String(state.textBaseline),
        px: fontPx(state.font),
      });
    },
  };
  return new Proxy(state, {
    get(target, prop) {
      if (typeof prop !== "string") return undefined;
      if (prop in methods) {
        return (...args: unknown[]) => {
          bump(rec.counts, prop);
          bump(totals, prop);
          return methods[prop](...args);
        };
      }
      if (prop in target) return target[prop];
      return () => {
        bump(rec.counts, prop);
        bump(totals, prop);
        return undefined;
      };
    },
    set(target, prop, value) {
      if (typeof prop === "string") target[prop] = value;
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
}

function installCanvasStubs(width: number, height: number) {
  size = { width, height };
  totals.clear();
  frames = new Map();
  nextFrameId = 1;
  clock = 1000;
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
      right: size.width,
      bottom: size.height,
      width: size.width,
      height: size.height,
      toJSON: () => ({}),
    }),
  });
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    const id = nextFrameId++;
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

/** Runs one animation frame `dt` ms after the last; returns the main canvas's calls in it. */
function runFrame(main: HTMLCanvasElement, dt = FRAME_60): Map<string, number> {
  clock += dt;
  const rec = recorders.get(main);
  expect(rec, "the halftone canvas asked for a 2D context").toBeDefined();
  rec!.counts = new Map();
  const due = [...frames.values()];
  frames = new Map();
  for (const cb of due) cb(clock);
  return rec!.counts;
}

function renderHalftone(extra: Record<string, unknown> = {}) {
  const { container } = render(
    <HalftoneWordmarkFooter
      wordmark="gsm8k"
      preset="night"
      label=""
      meta=""
      columns={[]}
      backToTop={false}
      crop={0}
      height="40vh"
      {...extra}
    />,
  );
  const main = container.querySelector("canvas");
  expect(main).not.toBeNull();
  const root = main!.parentElement as HTMLElement;
  return { main: main as HTMLCanvasElement, root };
}

/** Records every canvas the component creates (the word masks are never attached). */
function trackCanvases(): HTMLCanvasElement[] {
  const created: HTMLCanvasElement[] = [];
  const original = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation(((
    tag: string,
    options?: ElementCreationOptions,
  ) => {
    const el = original(tag, options);
    if (tag.toLowerCase() === "canvas") created.push(el as HTMLCanvasElement);
    return el;
  }) as typeof document.createElement);
  return created;
}

/** The word's vertical extent on its mask, from the last fillText of the word on any canvas. */
function wordBox(canvases: HTMLCanvasElement[]): { top: number; bottom: number } {
  const calls = canvases.flatMap((c) => recorders.get(c)?.texts ?? []);
  const last = [...calls].reverse().find((c) => c.text === "gsm8k");
  expect(last, "the word is set on a mask canvas with fillText").toBeDefined();
  const { y, baseline, px } = last!;
  const asc = 0.7 * px;
  const desc = 0.02 * px;
  switch (baseline) {
    case "top":
    case "hanging":
      return { top: y, bottom: y + asc + desc };
    case "bottom":
    case "ideographic":
      return { top: y - asc - desc, bottom: y };
    case "middle":
      return { top: y - (asc + desc) / 2, bottom: y + (asc + desc) / 2 };
    default:
      return { top: y - asc, bottom: y + desc };
  }
}

describe("AC4.2.7 the halftone holds at most 16,000 dots and batches its fills", () => {
  it("AC4.2.7 hwfGap keeps the 6 px gap when the canvas holds at most 16,000 dots", () => {
    expect(hwfGap(1200, 300, 6)).toBe(6);
    // Exactly at the limit: 100 columns x 160 rows.
    expect(hwfGap(600, 960, 6)).toBe(6);
    expect(hwfGap(10, 10, 6)).toBe(6);
  });

  it("AC4.2.7 hwfGap widens the gap only as far as needed to stay at or under 16,000 dots", () => {
    const g = hwfGap(2400, 520, 6);
    expect(g).toBeGreaterThan(6);
    const count = Math.ceil(2400 / g) * Math.ceil(520 / g);
    expect(count).toBeLessThanOrEqual(MAX_DOTS);
    // Not widened far past what is needed (the smallest such gap gives close to 16,000).
    expect(count).toBeGreaterThanOrEqual(0.75 * MAX_DOTS);

    const big = hwfGap(4000, 1200, 6);
    const bigCount = Math.ceil(4000 / big) * Math.ceil(1200 / big);
    expect(bigCount).toBeLessThanOrEqual(MAX_DOTS);
    expect(bigCount).toBeGreaterThanOrEqual(0.75 * MAX_DOTS);
  });

  it("AC4.2.7 hwfGap honours a custom maxDots", () => {
    const g = hwfGap(2400, 520, 6, 4000);
    const count = Math.ceil(2400 / g) * Math.ceil(520 / g);
    expect(count).toBeLessThanOrEqual(4000);
    expect(count).toBeGreaterThanOrEqual(3000);
    expect(hwfGap(120, 60, 6, 4000)).toBe(6);
  });

  describe("draw loop at 2400 x 520", () => {
    beforeEach(() => installCanvasStubs(2400, 520));
    afterEach(() => restoreCanvasStubs());

    it("AC4.2.7 each frame draws at most 16,000 dots in at most 4 dot fills plus one grain fill", () => {
      const { main } = renderHalftone();
      fireEvent.pointerMove(main, { clientX: 1200, clientY: 260 });
      for (let i = 0; i < 6; i++) {
        const calls = runFrame(main);
        const arcs = calls.get("arc") ?? 0;
        const images = calls.get("drawImage") ?? 0;
        expect(arcs + images, `frame ${i} draws dots`).toBeGreaterThan(0);
        expect(arcs, `frame ${i} dots`).toBeLessThanOrEqual(MAX_DOTS);
        expect(calls.get("fill") ?? 0, `frame ${i} fill() calls`).toBeLessThanOrEqual(5);
        expect(calls.get("fillRect") ?? 0, `frame ${i} fillRect() calls`).toBeLessThanOrEqual(2);
        // Keep the pointer moving across the word.
        fireEvent.pointerMove(main, { clientX: 1200 + 20 * (i + 1), clientY: 260 });
      }
    });

    it("AC4.2.7 the grain pattern is created once per layout, not once per frame", () => {
      const { main } = renderHalftone();
      fireEvent.pointerMove(main, { clientX: 1200, clientY: 260 });
      for (let i = 0; i < 10; i++) runFrame(main);
      // Every layout reads the word mask's pixels once.
      const layouts = Math.max(1, totals.get("getImageData") ?? 0);
      expect(layouts).toBeLessThanOrEqual(2);
      expect(totals.get("createPattern") ?? 0).toBeLessThanOrEqual(layouts);
    });

    it("AC4.2.7 with the pointer gone and the dots settled, no frame is requested", () => {
      const { main, root } = renderHalftone();
      fireEvent.pointerMove(main, { clientX: 1200, clientY: 260 });
      for (let i = 0; i < 5; i++) runFrame(main);
      fireEvent.pointerLeave(root);
      let n = 0;
      while (frames.size > 0 && n < 900) {
        runFrame(main);
        n++;
      }
      expect(frames.size, "the loop sleeps once the dots are home").toBe(0);
      expect(n).toBeLessThan(900);
    });
  });
});

describe("AC4.2.5 the halftone component draws the word in the middle when align=center", () => {
  beforeEach(() => installCanvasStubs(1200, 520));
  afterEach(() => restoreCanvasStubs());

  it("AC4.2.5 with align=center the word's vertical middle is near the canvas middle", () => {
    const created = trackCanvases();
    renderHalftone({ align: "center" });
    const box = wordBox(created);
    const middle = (box.top + box.bottom) / 2;
    expect(Math.abs(middle - 260)).toBeLessThanOrEqual(0.15 * 520);
  });

  it("AC4.2.5 by default the word still sits on the bottom edge (crop 0)", () => {
    const created = trackCanvases();
    renderHalftone();
    const box = wordBox(created);
    expect(box.bottom).toBeGreaterThanOrEqual(0.9 * 520);
  });
});

// ---------------------------------------------------------------------------------------------
// AC4.2.8: the spring steps by elapsed time
// ---------------------------------------------------------------------------------------------

/** The step as it was before batch-11 (one 60 Hz frame): push 2.6, spring 0.05, damping 0.84. */
function oldStep(
  x: number,
  y: number,
  vx: number,
  vy: number,
  hx: number,
  hy: number,
  px: number,
  py: number,
  r: number,
): number[] {
  const dx = x - px;
  const dy = y - py;
  const d2 = dx * dx + dy * dy;
  if (r > 0 && d2 < r * r) {
    const d = Math.sqrt(d2) + 0.001;
    const f = (1 - d / r) * 2.6;
    vx += (dx / d) * f;
    vy += (dy / d) * f;
  }
  vx = (vx + (hx - x) * 0.05) * 0.84;
  vy = (vy + (hy - y) * 0.05) * 0.84;
  return [x + vx, y + vy, vx, vy];
}

type StepArgs = [number, number, number, number, number, number, number, number, number];

const CASES: StepArgs[] = [
  // At home, pointer close: pushed away.
  [100, 50, 0, 0, 100, 50, 120, 60, 80],
  // Displaced and moving, pointer far: springs home.
  [130, 40, 1.5, -2, 100, 50, -1e5, -1e5, 80],
  // Inside the radius while moving.
  [90, 70, 3, 1, 100, 50, 60, 80, 80],
  // Radius 0: no push at all.
  [104, 47, 0.4, 0.2, 100, 50, 104, 47, 0],
];

/** x of a dot displaced 30 px from home (pointer away), stepped every `dt` ms for 1 s. */
function path(dt: number): Array<[number, number]> {
  let x = 130;
  let y = 50;
  let vx = 0;
  let vy = 0;
  let t = 0;
  const out: Array<[number, number]> = [[0, x - 100]];
  while (t < 1000) {
    const s = hwfStep(x, y, vx, vy, 100, 50, -1e5, -1e5, 80, dt);
    [x, y, vx, vy] = s;
    t += dt;
    out.push([t, x - 100]);
  }
  return out;
}

/** The displacement at time t, linearly between the steps around it. */
function at(points: Array<[number, number]>, t: number): number {
  for (let i = 1; i < points.length; i++) {
    const [t1, x1] = points[i];
    if (t1 >= t) {
      const [t0, x0] = points[i - 1];
      return x0 + ((x1 - x0) * (t - t0)) / (t1 - t0);
    }
  }
  return points[points.length - 1][1];
}

describe("AC4.2.8 the dots move by elapsed time", () => {
  it("AC4.2.8 hwfStep with the default elapsed time gives the old one-frame result", () => {
    for (const args of CASES) {
      const got = hwfStep(...args);
      const want = oldStep(...args);
      expect(got).toHaveLength(4);
      for (let i = 0; i < 4; i++) expect(got[i]).toBeCloseTo(want[i], 9);
    }
  });

  it("AC4.2.8 hwfStep with one 60 Hz frame passed explicitly gives the old result", () => {
    for (const args of CASES) {
      const got = hwfStep(...args, FRAME_60);
      const want = oldStep(...args);
      for (let i = 0; i < 4; i++) expect(got[i]).toBeCloseTo(want[i], 9);
    }
  });

  it("AC4.2.8 a dot's path over one second differs by under 5% between 60 and 144 frames per second", () => {
    const p60 = path(FRAME_60);
    const p144 = path(FRAME_144);
    const largest = Math.max(...p60.map((p) => Math.abs(p[1])), ...p144.map((p) => Math.abs(p[1])));
    expect(largest).toBeGreaterThanOrEqual(30);
    for (const t of [50, 100, 250, 500, 750, 1000]) {
      const diff = Math.abs(at(p60, t) - at(p144, t));
      expect(diff, `at ${t} ms`).toBeLessThan(0.05 * largest);
    }
    // At 144 Hz one step moves the dot less than one 60 Hz step does (it is scaled, not repeated).
    const one60 = Math.abs(p60[1][1] - p60[0][1]);
    const one144 = Math.abs(p144[1][1] - p144[0][1]);
    expect(one144).toBeLessThan(one60);
  });

  it("AC4.2.8 an elapsed time over 50 ms is treated as 50 ms", () => {
    for (const args of CASES) {
      const capped = hwfStep(...args, 50);
      for (const dt of [80, 200, 5000]) {
        const got = hwfStep(...args, dt);
        for (let i = 0; i < 4; i++) expect(got[i]).toBeCloseTo(capped[i], 9);
      }
    }
    // 50 ms is not the same as one frame: the cap is a real clamp, not a reset to the default.
    const fifty = hwfStep(130, 40, 1.5, -2, 100, 50, -1e5, -1e5, 80, 50);
    const frame = hwfStep(130, 40, 1.5, -2, 100, 50, -1e5, -1e5, 80);
    expect(Math.abs(fifty[0] - frame[0])).toBeGreaterThan(1e-6);
  });

  it("AC4.2.8 the 60 Hz and 144 Hz paths both settle home within the second", () => {
    const p60 = path(FRAME_60);
    const p144 = path(FRAME_144);
    expect(Math.abs(p60[p60.length - 1][1])).toBeLessThan(1);
    expect(Math.abs(p144[p144.length - 1][1])).toBeLessThan(1);
  });
});
