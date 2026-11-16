/** Helpers of the Course page (US12.5): words for states, text blocks and number formats. */
import type { CourseKind, CourseRunState, CourseStepState } from "@/lib/api";

export const STEP_STATE_WORDS: Record<CourseStepState, string> = {
  "not-started": "Not started",
  "in-progress": "In progress",
  done: "Done",
};

export const KIND_WORDS: Record<CourseKind, string> = {
  gpu: "GPU run",
  inspect: "CPU inspection",
  lab: "Lab lesson",
  read: "Reading",
};

export const RUN_STATE_WORDS: Record<CourseRunState, string> = {
  "not-run": "Not run",
  queued: "Queued",
  running: "Running",
  finished: "Finished",
  failed: "Failed",
  stopped: "Stopped",
};

/** Lab lesson states as the lab's own list words them. */
export const LESSON_STATE_WORDS: Record<string, string> = {
  "not-run": "Not run",
  running: "Running",
  finished: "Finished",
  failed: "Failed",
  stopped: "Stopped",
};

/** How often a shown step is read again while one of its runs is queued or running. */
export const COURSE_POLL_MS = 3000;

/** A block of a Markdown text: a paragraph, or a list of `- ` lines. */
export type TextBlock = { kind: "p"; text: string } | { kind: "ul"; items: string[] };

/** Splits Markdown text on blank lines into paragraphs and bullet lists (nothing else). */
export function textBlocks(text: string): TextBlock[] {
  const blocks: TextBlock[] = [];
  for (const raw of text.split(/\n\s*\n/)) {
    const lines = raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length === 0) continue;
    if (lines.every((line) => /^[-*] /.test(line))) {
      blocks.push({ kind: "ul", items: lines.map((line) => line.slice(2).trim()) });
    } else {
      blocks.push({ kind: "p", text: lines.join(" ") });
    }
  }
  return blocks;
}

/** A piece of a line: plain text, **bold** or `code`. */
export type Inline = { kind: "text" | "strong" | "code"; text: string };

/** Splits a line into plain, bold and code pieces. */
export function inlinePieces(line: string): Inline[] {
  const pieces: Inline[] = [];
  for (const part of line.split(/(\*\*[^*]+\*\*|`[^`]+`)/)) {
    if (part === "") continue;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      pieces.push({ kind: "strong", text: part.slice(2, -2) });
    } else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      pieces.push({ kind: "code", text: part.slice(1, -1) });
    } else {
      pieces.push({ kind: "text", text: part });
    }
  }
  return pieces;
}

/** 155582464 -> "155.6 M". */
export function formatMillions(value: number): string {
  return `${(value / 1_000_000).toFixed(1)} M`;
}

/** 12 -> "12", 9.64 -> "9.6"; null -> "--". */
export function formatGb(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return value.toFixed(1);
}

/** 6 -> "+6 pts", -2 -> "−2 pts", 0 -> "±0 pts"; null -> "--". */
export function formatPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "±0 pts";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} pts`;
}

/** The first seven characters of a revision hash. */
export function shortRevision(revision: string): string {
  return revision.slice(0, 7);
}
