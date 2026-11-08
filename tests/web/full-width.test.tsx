/**
 * Part W (u5-website, batch-10): full-width pages (AC4.1.4). Every page, rendered through the
 * app's router with its top bar, spans the window less the side gutter: no element sets the old
 * 1280 px cap (`max-w-[1280px]`, `max-w-[var(--content-width)]`), each page's outer container
 * and the top bar's row carry `px-[var(--gutter)]` and no max-width, and the design tokens no
 * longer define `--content-width`. Prose blocks may keep their line length (`max-w-[70ch]`,
 * `max-w-[75ch]`, `max-w-xl`); this file does not check them. Class names only, never pixels.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { Q06, Q17, fakeApi, run, type FakeApi } from "@/test/fake-api";
import { renderPage, screen, waitFor } from "@/test/utils";

const CAPS = ["max-w-[1280px]", "max-w-[var(--content-width)]"];
const GUTTER = "px-[var(--gutter)]";

/** Tests run from the project root (vitest `test.root`); the tokens file is read from disk. */
const TOKENS = resolve(process.cwd(), "web/src/styles/tokens.css");

const RUNS = [
  run({
    run_id: "q17-base-dev-1",
    model: Q17,
    method: "base",
    dev_accuracy: 0.587,
    gain: null,
    date: "2026-11-02T09:00:00Z",
  }),
  run({
    run_id: "q06-sft-dev-1",
    model: Q06,
    method: "sft",
    dev_accuracy: 0.47,
    gain: 0.057,
    date: "2026-11-03T09:00:00Z",
  }),
];

function apiWithRuns(): FakeApi {
  return fakeApi({ listRuns: async () => ({ runs: RUNS, skipped_rows: 0 }) });
}

/** The class tokens of an element (SVG elements included, via the attribute). */
function classesOf(el: Element): string[] {
  return (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
}

/** Every element in the document whose class list carries one of the old width caps. */
function cappedElements(): string[] {
  const found: string[] = [];
  for (const el of document.querySelectorAll("[class]")) {
    const classes = classesOf(el);
    if (CAPS.some((cap) => classes.some((c) => c.includes(cap)))) {
      found.push(`<${el.tagName.toLowerCase()} class="${el.getAttribute("class") ?? ""}">`);
    }
  }
  return found;
}

/** The page's outer container: the first element child of `<main id="main">`. */
function pageContainer(): Element {
  const main = document.querySelector("main#main");
  expect(main).not.toBeNull();
  const container = main?.firstElementChild ?? null;
  expect(container).not.toBeNull();
  return container as Element;
}

/** The top bar's inner row: the main navigation inside the header. */
function topBarRow(): Element {
  return screen.getByRole("navigation", { name: "Main" });
}

/** Spans the full width less the gutter: the gutter class and no max-width class at all. */
function expectFullWidth(el: Element) {
  const classes = classesOf(el);
  expect(classes).toContain(GUTTER);
  expect(classes.filter((c) => c.startsWith("max-w-"))).toEqual([]);
}

interface PageCase {
  name: string;
  path: string;
  api: () => FakeApi;
  /** Waits until the page shows its loaded content, not only a loading state. */
  ready: (api: FakeApi) => Promise<void>;
  /**
   * The element under the outer container that carries the gutter, when the outer container
   * itself stays full-bleed (landing: the halftone headline spans the window, lead 2026-11-08).
   */
  gutterBlock?: () => Element;
}

const LANDING_DESCRIPTION =
  "Teaching small open models grade-school math, one measured run at a time.";

/** Landing's text block under the headline: the element holding the description line. */
function landingTextBlock(): Element {
  const block = screen.getByText(LANDING_DESCRIPTION).parentElement;
  expect(block).not.toBeNull();
  return block as Element;
}

const PAGES: PageCase[] = [
  {
    name: "landing",
    path: "/",
    api: apiWithRuns,
    ready: async () => {
      expect(await screen.findByRole("link", { name: "See scores" })).toBeInTheDocument();
      await waitFor(() =>
        expect(document.querySelector('[data-state="populated"]')).not.toBeNull(),
      );
    },
    gutterBlock: landingTextBlock,
  },
  {
    name: "scores",
    path: "/scores",
    api: apiWithRuns,
    ready: async () => {
      expect(await screen.findByRole("table")).toBeInTheDocument();
    },
  },
  {
    name: "training",
    path: "/training",
    api: () => fakeApi(),
    ready: async (api) => {
      expect(await screen.findByRole("heading", { name: "Training" })).toBeInTheDocument();
      await waitFor(() => expect(api.getStatus).toHaveBeenCalled());
      await waitFor(() => expect(api.stream.isOpen).toBe(true));
    },
  },
  {
    name: "reasoning",
    path: "/reasoning",
    api: () => fakeApi(),
    ready: async () => {
      expect(
        await screen.findByText(/No self-taught chain-of-thought run yet/),
      ).toBeInTheDocument();
    },
  },
];

describe("AC4.1.4 full-width pages", () => {
  for (const page of PAGES) {
    it(`AC4.1.4 the ${page.name} page and the top bar set no 1280 px cap`, async () => {
      const api = page.api();
      renderPage(page.path, { api });
      await page.ready(api);
      expect(cappedElements()).toEqual([]);
    });

    it(`AC4.1.4 the ${page.name} page container spans the window less the gutter`, async () => {
      const api = page.api();
      renderPage(page.path, { api });
      await page.ready(api);
      const container = pageContainer();
      if (page.gutterBlock) {
        // Full-bleed outer container: no max-width cap at all (so no mx-auto + max-w centring),
        // no gutter needed; the text block under the headline carries the gutter instead.
        expect(classesOf(container).filter((c) => c.startsWith("max-w-"))).toEqual([]);
        const block = page.gutterBlock();
        expect(container.contains(block)).toBe(true);
        expectFullWidth(block);
      } else {
        expectFullWidth(container);
      }
    });

    it(`AC4.1.4 the top bar row on the ${page.name} page spans the window less the gutter`, async () => {
      const api = page.api();
      renderPage(page.path, { api });
      await page.ready(api);
      expectFullWidth(topBarRow());
    });
  }

  it("AC4.1.4 the design tokens drop --content-width and keep --gutter", () => {
    const css = readFileSync(TOKENS, "utf8");
    expect(css).not.toMatch(/--content-width\s*:/);
    expect(css).not.toMatch(/var\(\s*--content-width\s*\)/);
    expect(css).toMatch(/--gutter\s*:\s*24px\s*;/);
  });
});
