/**
 * Vitest setup for the website tests (tests/web): jest-dom matchers and the browser parts jsdom
 * lacks. Canvas has no context here (getContext -> null), so canvas components draw nothing and
 * tests assert text, roles, labels and data-* state instead.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

type MediaListener = (event: MediaQueryListEvent) => void;

interface MediaEntry {
  list: MediaQueryList;
  listeners: Set<MediaListener>;
}

interface MediaStore {
  reduced: boolean;
  lists: Map<string, MediaEntry>;
}

// Kept on globalThis so every import of this module shares one store.
const globalStore = globalThis as typeof globalThis & { __gsm8kMediaStore?: MediaStore };
const store: MediaStore = (globalStore.__gsm8kMediaStore ??= { reduced: false, lists: new Map() });

function matches(media: string): boolean {
  return media.replace(/\s+/g, " ").includes("prefers-reduced-motion: reduce") && store.reduced;
}

/** Turns the operating system's reduce-motion setting on or off for the current test. */
export function setReducedMotion(on: boolean): void {
  const changed = store.reduced !== on;
  store.reduced = on;
  if (!changed) return;
  for (const [media, entry] of store.lists) {
    const event = { matches: matches(media), media } as MediaQueryListEvent;
    for (const listener of [...entry.listeners]) listener(event);
  }
}

/** One MediaQueryList per query string, like a browser's live lists. */
function matchMediaStub(media: string): MediaQueryList {
  const known = store.lists.get(media);
  if (known) return known.list;
  const listeners = new Set<MediaListener>();
  const list = {
    media,
    get matches() {
      return matches(media);
    },
    onchange: null,
    addEventListener: (_type: string, listener: MediaListener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: MediaListener) => listeners.delete(listener),
    addListener: (listener: MediaListener) => listeners.add(listener),
    removeListener: (listener: MediaListener) => listeners.delete(listener),
    dispatchEvent: () => true,
  } as unknown as MediaQueryList;
  store.lists.set(media, { list, listeners });
  return list;
}

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  writable: true,
  value: matchMediaStub,
});

class ResizeObserverStub implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

class IntersectionObserverStub implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "0px";
  readonly scrollMargin = "0px";
  readonly thresholds: ReadonlyArray<number> = [0];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  writable: true,
  value: ResizeObserverStub,
});
Object.defineProperty(globalThis, "IntersectionObserver", {
  configurable: true,
  writable: true,
  value: IntersectionObserverStub,
});

// jsdom has no canvas: every context is null, so canvas components draw nothing.
Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  writable: true,
  value: () => null,
});

// Radix UI calls these; jsdom does not have them.
Object.defineProperty(Element.prototype, "scrollIntoView", {
  configurable: true,
  writable: true,
  value: () => {},
});
Object.defineProperty(Element.prototype, "hasPointerCapture", {
  configurable: true,
  writable: true,
  value: () => false,
});
Object.defineProperty(Element.prototype, "setPointerCapture", {
  configurable: true,
  writable: true,
  value: () => {},
});
Object.defineProperty(Element.prototype, "releasePointerCapture", {
  configurable: true,
  writable: true,
  value: () => {},
});

export { REDUCED_QUERY };

afterEach(() => {
  cleanup();
  setReducedMotion(false);
  store.lists.clear();
});
