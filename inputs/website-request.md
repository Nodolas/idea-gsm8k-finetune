# Input: results website with a halftone headline

Nico's request in a session on 2026-10-30, saved as data for the brief (`/build` 2.1). Not a spec until the brief and AI-DLC take it in.

## Request (verbatim)
> I want a headline like this on the main landing page. In the end the website should be a website with landing page, highest scores and the training page.

## What it implies for the spec
- Three pages: landing (halftone wordmark headline), highest scores (best runs from `results/runs.csv`), training (the learning path: SFT, GRPO, ablations, per-run detail).
- The component below is a footer. As a headline it needs a hero variant: no link columns and probably `crop` 0. Wordmark text to decide (for example `gsm8k`).
- Stack the component expects: React with TypeScript, Tailwind, shadcn layout (`components/ui/`, `@/` alias). The repo has no frontend yet, and Node is not installed on this PC.
- Learning project: no deploy (rule 9 off). The site runs locally (`npm run dev`) and reads the committed results; it is an add-on to `results.md`, not a replacement.
- Component has no npm dependencies beyond React; no images or icons needed (lucide-react only if the nav needs icons).

## Component source (21st.dev "Halftone Wordmark Footer", as pasted)
Target path once built: `components/ui/halftone-wordmark-footer.tsx`. Demo usage: wrap in `<div className="w-full">` (a flex item at width:auto shrinks the canvas to 0 px).

The full source Nico pasted is kept in `halftone-wordmark-footer.tsx.txt` next to this file.
