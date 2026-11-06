# Design System Mapping

How the mockups (`mockups.md`) map onto the stack named in `inception/requirements-analysis/requirements.md` (Constraints: React, TypeScript, Vite, Tailwind, shadcn/ui with charts) and onto Nico's design inputs. The rough structure is from `ideation/rough-mockups/wireframes.md` and `ideation/rough-mockups/user-flow.md`; stories from `inception/user-stories/stories.md`; tooling rules (Node under `.tools/node/`, npm cache in `.cache/npm`, ESLint, Prettier, strict TypeScript) from `inception/practices-discovery/team-practices.md`.

## Sources of the Look

- **Halftone Wordmark Footer** (`inputs/halftone-wordmark-footer.tsx.txt`, cleared by Nico for personal use, requirements Q6): used as the landing hero with preset `night`. Its colours become the site tokens below.
- **Gateway Flow screenshot** (`inputs/design/training-live-gateway-flow.png`): only the look is taken (dotted lines converging to a waist on black, sparse bright dots). The HourglassBand is written from scratch; no 21st.dev code, registry or Magic MCP is used (STATE.md, DO NOT).

## Design Tokens

Defined once as CSS variables in `src/styles/tokens.css` and mapped into the Tailwind theme and shadcn/ui's variables (`--background`, `--foreground`, and so on). Contrast is measured against `bg` (`#0c0c0b`).

| Token | Value | Use | Contrast on bg |
|---|---|---|---|
| `bg` | `#0c0c0b` | Page background | — |
| `panel` | `#141413` | Panels, dialogs, log block | — |
| `ink` | `#e9e4da` | Text, dots, curves | 15.4:1 |
| `ink-muted` | `#8c8882` | Helper text, labels, axis ticks | 5.5:1 |
| `hairline` | `ink` at 16% | Borders, table rules | decorative |
| `grid` | `ink` at 12%, dotted | Chart gridlines | decorative |
| `accent` | `#e9762b` | Active run, current curve, focus ring, current-page underline | 5.9:1 |
| `danger` | `#ff6b5b` | Error text and icons (always with an icon and words) | 7.0:1 |
| `ok` | `#8fd19e` | Finished-run check icon (always with the word) | 11.0:1 |
| `scrim` | `bg` at 70% | Behind text over the hourglass dots | — |

| Type token | Value | Use |
|---|---|---|
| `font-sans` | `ui-sans-serif, system-ui, sans-serif` | Body and headings |
| `font-mono` | `ui-monospace, SFMono-Regular, Menlo, monospace` with `tabular-nums` | Numbers, run ids, dials, commands |
| `label` | mono, 10.5 px, uppercase, letter-spacing 0.18 em | Section labels ("BEST SO FAR", "DIALS") |
| `body` | sans, 15 px / 1.5 | Text |
| `h1` | sans, 28 px, weight 600 | Page titles (Scores, Training); landing h1 is visually hidden |
| `number-lg` | mono, 20 px | Step counter and percentage on the band |

| Space and shape | Value |
|---|---|
| Spacing scale | 4, 8, 16, 24, 32, 48 px |
| Radius | 6 px on panels and dialogs; 4 px on fields and buttons |
| Border | 0.5 px `hairline`; no shadows |
| Content width | max 1280 px, 24 px gutters |
| Motion | 150–300 ms, ease-out in, ease-in out; none under reduced motion |

## Component Mapping

| Mockup element | Built from | Notes |
|---|---|---|
| TopBar | Plain `<header>` + `<nav>` with shadcn `Button` (variant `link`) | Sticky; run tag uses `Badge` |
| HalftoneHeadline | `components/ui/halftone-wordmark-footer.tsx` (Nico's paste) | Props: `wordmark="gsm8k"`, `preset="night"`, `columns={[]}`, `backToTop={false}`, `crop={0}`; wrap in `<div className="w-full">` |
| BestSoFar | Text + shadcn `Skeleton` | — |
| ScoresTable | shadcn `Table`, `Checkbox`, `Select` (filters), `DropdownMenu` (row menu), `Skeleton` | Native table semantics kept |
| CompareView | shadcn `Table` + `Tabs` + chart (below) | Run B dashed |
| HourglassBand | Custom `components/hourglass-band.tsx` on a 2D canvas | No dependencies; draws from `step / totalSteps` |
| CurvesPanel | shadcn `Chart` (Recharts) `LineChart`, `Tabs` | 1.5 px lines, `strokeDasharray` for gridlines, `Tooltip` for the read-out |
| DialsPanel | shadcn `Form` (react-hook-form + zod), `Input`, `Select`, `Label`, `Button` | Zod schema mirrors the stories.md Training Dials table; the service checks again (US2.1) |
| ConfirmRunDialog, TestSplitDialog | shadcn `Dialog`, `Checkbox`, `Button` | Focus trap and Escape from Radix |
| StopRunDialog | shadcn `AlertDialog` | — |
| FailurePanel | shadcn `Sheet` + `<pre>` + `Button` (Copy) | — |
| PastRunsList | shadcn `Table` | — |
| Live paused banner | shadcn `Alert` | Icon plus text |
| Toasts | none | All feedback is inline near its cause |

## Component Library Gaps

- **HourglassBand** has no shadcn/ui equivalent; it is a project component with its own Vitest tests on the fraction it draws (state, not pixels).
- **HalftoneHeadline** is third-party source kept as pasted except for the hero props; its licence is cleared for this personal use only (requirements.md Constraints).

## Project Layout (website)

```
web/
  src/
    components/ui/          shadcn/ui parts + halftone-wordmark-footer.tsx
    components/             hourglass-band.tsx, curves-panel.tsx, dials-panel.tsx, ...
    pages/                  landing.tsx, scores.tsx, training.tsx
    styles/tokens.css       the tokens above
  tests/ -> project tests/web/   Vitest tests named "AC4.x.y ..."
```

<!-- Text fallback: the website lives in web/, with shadcn/ui parts and the pasted halftone component under src/components/ui, project components such as the hourglass band under src/components, one file per page under src/pages, and the tokens in src/styles/tokens.css. Its Vitest tests live under the project's tests/web/ folder, named by criterion ID. -->

The folder layout is a proposal for Functional Design and Code Generation to confirm; tests stay under the project's `tests/` (team-practices.md).
