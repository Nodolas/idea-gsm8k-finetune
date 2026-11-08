"use client"

// Halftone Wordmark Footer — a site footer whose wordmark is set enormous and
// cropped by the bottom edge, printed as a field of halftone dots. Each dot is
// sized by how much of the letter covers its cell, so the type keeps its edges
// at any scale. Move across it and the dots part around the pointer on springs,
// warming in colour as they are pushed off their place; click and a shock ring
// runs through the word. Above it sit the studio line, tracked link columns and
// a back-to-top, separated by a hairline, all over a fine print grain.
//
// One file, React only. A 2D canvas for the dots and the grain, real anchors
// for the links. Every rule in the scoped <style> is .hwf- prefixed and nothing
// is fetched: the faces come from the host page or the fallback stacks.

import * as React from "react"

export interface HalftonePalette {
  /** The footer background. */
  background: string
  /** The dots at rest, and the text. */
  ink: string
  /** The colour a dot warms toward as it is pushed off its place. */
  warm: string
}

export type HalftonePreset = "night" | "paper" | "ember" | "cobalt"

export interface FooterLink {
  label: string
  href?: string
}

export interface FooterColumn {
  title: string
  links: FooterLink[]
}

export interface HalftoneWordmarkFooterProps {
  /** The giant word printed in dots. Lowercase reads best. */
  wordmark?: string
  /** Top-left studio line. */
  label?: string
  /** The muted line under it. */
  meta?: string
  /** Link columns along the top. */
  columns?: FooterColumn[]
  /** Show the back-to-top link. It scrolls the window to 0. Defaults to true. */
  backToTop?: boolean
  /** Starting colours. Defaults to "night". */
  preset?: HalftonePreset
  /** Colour overrides, merged over the preset. */
  palette?: { background?: string; ink?: string; warm?: string }
  /** Distance between dot centres, in CSS px. Defaults to 6. */
  dotGap?: number
  /** How far the pointer pushes, in CSS px. Defaults to 80. */
  radius?: number
  /** How much of the word's cap height hangs below the bottom edge, 0–0.6. Defaults to 0.2. */
  crop?: number
  /**
   * Where the word sits: "bottom" (the default) stands it on the bottom edge, cropped by
   * `crop`; "center" draws it whole with its vertical middle at the canvas middle.
   */
  align?: "bottom" | "center"
  /** The most dots the field may hold; the gap widens past `dotGap` to stay under. Defaults to 16,000. */
  maxDots?: number
  /** Print grain over everything, 0–1. Defaults to 0.5. */
  grain?: number
  /** Pointer and click response. Defaults to true. */
  interactive?: boolean
  /** Face for the wordmark. Heavy grotesks print best. */
  fontFamily?: string
  /** Weight of the wordmark. Defaults to 800. */
  fontWeight?: number
  /** Face for the small type. */
  monoFamily?: string
  /** Root height. A definite length, never a percentage. */
  height?: string
  /** Extra root class names. */
  className?: string
}

const PRESETS: { [K in HalftonePreset]: HalftonePalette } = {
  night: { background: "#0c0c0b", ink: "#e9e4da", warm: "#e9762b" },
  paper: { background: "#efebe3", ink: "#17150f", warm: "#c2361c" },
  ember: { background: "#160a06", ink: "#f2c48c", warm: "#ff5a1f" },
  cobalt: { background: "#0d1b4d", ink: "#dfe7ff", warm: "#ffcd3c" },
}

const DEFAULT_COLUMNS: FooterColumn[] = [
  { title: "Work", links: [{ label: "Index" }, { label: "Archive" }, { label: "Journal" }] },
  { title: "Studio", links: [{ label: "About" }, { label: "Process" }, { label: "Careers" }] },
  { title: "Contact", links: [{ label: "hello@halden.co" }, { label: "+47 22 00 41 00" }] },
]

const SANS_STACK = '"Inter Tight", "Inter Variable", "Inter", "Helvetica Neue", Arial, system-ui, sans-serif'
const MONO_STACK = '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace'

// #region halftone
// Pure helpers, lifted out and executed by tests/halftone-wordmark-footer.test.mjs.

/** Hex → [r, g, b] in 0–255, or null for anything that isn't #rgb / #rrggbb. */
export function hwfHex(hex: string) {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec((hex || "").trim())
  if (!m) return null
  const h = m[1].length === 3 ? m[1].split("").map((c) => c + c).join("") : m[1]
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

/** Dot radius for a cell coverage in [0, 1]: area-true, so tone stays even. */
export function hwfRadius(coverage: number, gap: number) {
  const c = coverage < 0 ? 0 : coverage > 1 ? 1 : coverage
  return Math.sqrt(c) * gap * 0.56
}

/** One 60 Hz frame, in ms: the time step the spring constants were tuned for. */
export const HWF_FRAME_MS = 1000 / 60

/** The longest time one step may cover, in ms (a stalled tab never flings the dots). */
export const HWF_MAX_STEP_MS = 50

/**
 * One step of a dot's spring back to home, plus the push from a pointer at
 * (px, py) within radius r, over `dtMs` of elapsed time (default one 60 Hz
 * frame, clamped to 50 ms). Returns [x, y, vx, vy]. Push, spring and damping
 * scale with the elapsed time, so the motion is the same at any frame rate;
 * at the default it is exactly the original per-frame step. Away from the
 * pointer a displaced dot always heads home and comes to rest.
 */
export function hwfStep(
  x: number, y: number, vx: number, vy: number,
  hx: number, hy: number, px: number, py: number, r: number,
  dtMs: number = HWF_FRAME_MS,
) {
  const dt = Number.isFinite(dtMs) ? Math.max(0, Math.min(dtMs, HWF_MAX_STEP_MS)) : HWF_FRAME_MS
  const s = dt / HWF_FRAME_MS
  const damp = Math.pow(0.84, s)
  const dx = x - px
  const dy = y - py
  const d2 = dx * dx + dy * dy
  if (r > 0 && d2 < r * r) {
    const d = Math.sqrt(d2) + 0.001
    const f = (1 - d / r) * 2.6
    vx += (dx / d) * f * s
    vy += (dy / d) * f * s
  }
  vx = (vx + (hx - x) * 0.05 * s) * damp
  vy = (vy + (hy - y) * 0.05 * s) * damp
  return [x + vx * s, y + vy * s, vx, vy]
}

/**
 * The dot gap used for layout: `dotGap`, unless a `width` × `height` field at
 * that gap would hold more than `maxDots` dots; then the smallest gap that
 * keeps the count (ceil(width / gap) × ceil(height / gap)) at or under it.
 */
export function hwfGap(width: number, height: number, dotGap: number, maxDots = 16000) {
  const count = (g: number) => Math.ceil(width / g) * Math.ceil(height / g)
  if (!(width > 0) || !(height > 0) || !(dotGap > 0) || !(maxDots >= 1)) return dotGap
  if (count(dotGap) <= maxDots) return dotGap
  // The count only falls as the gap grows: search for the smallest gap that fits.
  let lo = dotGap
  let hi = Math.max(dotGap, width, height)
  while (count(hi) > maxDots) hi *= 2
  for (let i = 0; i < 60 && hi - lo > 1e-9; i++) {
    const mid = (lo + hi) / 2
    if (count(mid) <= maxDots) hi = mid
    else lo = mid
  }
  return hi
}

/** How warm a dot is drawn: 0 at home, 1 once it is `span` px or more away. */
export function hwfWarmth(x: number, y: number, hx: number, hy: number, span: number) {
  const d = Math.hypot(x - hx, y - hy)
  return span > 0 ? Math.min(1, d / span) : 0
}

/** Font size that sets `measured` (width at 100px) to fill `width` exactly. */
export function hwfFitSize(measured: number, width: number) {
  return measured > 0 ? (width / measured) * 100 : 0
}

/** The number of warm colour steps a displaced dot is drawn in (one path each). */
export const HWF_WARM_STEPS = 3

/** Which warm step a warmth k in (0, 1] falls in: 0 … HWF_WARM_STEPS - 1. */
export function hwfWarmStep(k: number) {
  return Math.max(0, Math.min(HWF_WARM_STEPS - 1, Math.ceil(k * HWF_WARM_STEPS) - 1))
}
// #endregion

const HWF_CSS = `
.hwf-root {
  position: relative; width: 100%; overflow: hidden; isolation: isolate;
  background: var(--hwf-bg); color: var(--hwf-ink); -webkit-font-smoothing: antialiased;
}
.hwf-root canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; max-width: none; }
.hwf-top {
  position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1.25fr) repeat(3, minmax(0, 1fr));
  gap: 24px; padding: clamp(22px, 3.4vw, 40px) clamp(20px, 3.4vw, 44px) 0;
  font-family: var(--hwf-mono); font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; line-height: 1.75;
}
.hwf-brand strong { display: block; font-weight: 500; }
.hwf-brand span { opacity: .45; }
.hwf-col h3 { margin: 0; font: inherit; opacity: .4; font-weight: 500; }
.hwf-col ul { list-style: none; margin: 0; padding: 0; }
.hwf-col a, .hwf-up {
  color: inherit; text-decoration: none; opacity: .78; background: none; border: 0; padding: 0;
  font: inherit; letter-spacing: inherit; text-transform: inherit; cursor: pointer;
  background-image: linear-gradient(currentColor, currentColor); background-size: 0% 1px;
  background-repeat: no-repeat; background-position: 0 100%; transition: opacity .25s ease, background-size .35s cubic-bezier(.2,.7,.1,1);
}
.hwf-col a:hover, .hwf-up:hover { opacity: 1; background-size: 100% 1px; }
.hwf-col a:focus-visible, .hwf-up:focus-visible { outline: 1px solid currentColor; outline-offset: 3px; opacity: 1; }
.hwf-rule {
  position: relative; z-index: 1; display: flex; justify-content: flex-end; align-items: center; gap: 16px;
  margin: clamp(18px, 2.6vw, 30px) clamp(20px, 3.4vw, 44px) 0; padding-top: 12px;
  border-top: 0.5px solid color-mix(in srgb, var(--hwf-ink) 16%, transparent);
  font-family: var(--hwf-mono); font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase;
}
.hwf-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@media (max-width: 720px) {
  .hwf-top { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); row-gap: 18px; }
  .hwf-brand { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: reduce) {
  .hwf-col a, .hwf-up { transition: none; }
}
`

export default function HalftoneWordmarkFooter({
  wordmark = "halden",
  label = "Halden Studio",
  meta = "©2026 · Oslo / Lisbon",
  columns = DEFAULT_COLUMNS,
  backToTop = true,
  preset = "night",
  palette,
  dotGap = 6,
  radius = 80,
  crop = 0.2,
  align = "bottom",
  maxDots = 16000,
  grain = 0.5,
  interactive = true,
  fontFamily = SANS_STACK,
  fontWeight = 800,
  monoFamily = MONO_STACK,
  height = "560px",
  className = "",
}: HalftoneWordmarkFooterProps) {
  const colors = { ...(PRESETS[preset] || PRESETS.night), ...(palette || {}) }
  const rootRef = React.useRef(null as HTMLElement | null)
  const canvasRef = React.useRef(null as HTMLCanvasElement | null)
  const opts = React.useRef({ colors, dotGap, radius, crop, align, maxDots, grain, interactive, fontFamily, fontWeight, wordmark })
  opts.current = { colors, dotGap, radius, crop, align, maxDots, grain, interactive, fontFamily, fontWeight, wordmark }
  const key = [wordmark, dotGap, crop, align, maxDots, grain, fontFamily, fontWeight, colors.background, colors.ink, colors.warm].join("|")

  React.useEffect(() => {
    const root = rootRef.current
    const canvas = canvasRef.current
    if (!root || !canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    let w = 0
    let h = 0
    let dpr = 1
    let px = -1e5
    let py = -1e5
    let raf = 0
    let last = 0
    let visible = true
    let awake = true
    let ring = { x: 0, y: 0, t: -1 }
    // Flat arrays: x, y, vx, vy, hx, hy, r per dot.
    let dots = new Float32Array(0)
    let count = 0
    // Per-frame scratch, sized per layout: the displaced dots of each warm step.
    let warmIdx: Int32Array[] = []
    const warmLen = new Int32Array(HWF_WARM_STEPS)
    let grainTile = null as HTMLCanvasElement | null
    let grainPattern = null as CanvasPattern | null
    const ink = hwfHex(opts.current.colors.ink) || [233, 228, 218]
    const warm = hwfHex(opts.current.colors.warm) || [233, 118, 43]
    // The colour of each warm step, worked out once: step b is drawn at warmth (b + 1) / steps.
    const warmColors: string[] = []
    for (let b = 0; b < HWF_WARM_STEPS; b++) {
      const k = (b + 1) / HWF_WARM_STEPS
      warmColors.push(
        "rgb(" +
          Math.round(ink[0] + (warm[0] - ink[0]) * k) + "," +
          Math.round(ink[1] + (warm[1] - ink[1]) * k) + "," +
          Math.round(ink[2] + (warm[2] - ink[2]) * k) + ")",
      )
    }

    const layout = () => {
      const o = opts.current
      const rect = root.getBoundingClientRect()
      w = Math.max(1, Math.round(rect.width))
      h = Math.max(1, Math.round(rect.height))
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)

      // Set the word once on a 1x mask, at a size that fills the width but never
      // overflows the height: the smaller of the two fits.
      const mask = document.createElement("canvas")
      mask.width = w
      mask.height = h
      const m = mask.getContext("2d", { willReadFrequently: true })
      if (!m) return
      const centred = o.align === "center"
      const c = centred ? 0 : Math.max(0, Math.min(0.6, o.crop))
      m.font = o.fontWeight + " 100px " + o.fontFamily
      const word = o.wordmark || " "
      const probe = m.measureText(word)
      const asc100 = probe.actualBoundingBoxAscent || 72
      const desc100 = probe.actualBoundingBoxDescent || 0
      const fitW = hwfFitSize(probe.width, w * (centred ? 0.94 : 1.02))
      // Centred: the whole ink box fits in 86% of the height. Bottom: the visible
      // part of the cap height (above the crop) fits in 96% of it.
      const fitH = centred
        ? (h * 0.86 * 100) / Math.max(1, asc100 + desc100)
        : (h * 0.96 * 100) / Math.max(1, asc100 * (1 - c))
      const fit = Math.max(1, Math.min(fitW, fitH))
      m.font = o.fontWeight + " " + fit + "px " + o.fontFamily
      const box = m.measureText(word)
      const cap = box.actualBoundingBoxAscent || fit * 0.72
      const desc = box.actualBoundingBoxDescent || 0
      m.fillStyle = "#000"
      m.textBaseline = "alphabetic"
      // Centred: the ink box's vertical middle on the canvas middle.
      const baseline = centred ? h / 2 + (cap - desc) / 2 : h + cap * c
      m.fillText(word, (w - box.width) / 2, baseline)
      const img = m.getImageData(0, 0, w, h).data

      const gap = hwfGap(w, h, Math.max(3, o.dotGap), Math.max(1, o.maxDots))
      const cols = Math.ceil(w / gap)
      const rows = Math.ceil(h / gap)
      const tmp = []
      for (let gy = 0; gy < rows; gy++) {
        for (let gx = 0; gx < cols; gx++) {
          // Coverage: average alpha over a 3×3 sample of the cell.
          let sum = 0
          for (let sy = 0; sy < 3; sy++) {
            for (let sx = 0; sx < 3; sx++) {
              const x = Math.min(w - 1, Math.floor(gx * gap + ((sx + 0.5) * gap) / 3))
              const y = Math.min(h - 1, Math.floor(gy * gap + ((sy + 0.5) * gap) / 3))
              sum += img[(y * w + x) * 4 + 3]
            }
          }
          const cov = sum / (9 * 255)
          if (cov < 0.06) continue
          const hx = gx * gap + gap / 2
          const hy = gy * gap + gap / 2
          tmp.push(hx, hy, 0, 0, hx, hy, hwfRadius(cov, gap))
        }
      }
      dots = new Float32Array(tmp)
      count = tmp.length / 7
      warmIdx = []
      for (let b = 0; b < HWF_WARM_STEPS; b++) warmIdx.push(new Int32Array(count))

      // A fixed tile of print grain, drawn once per layout, and its pattern made
      // once too, then laid over every frame.
      grainTile = document.createElement("canvas")
      grainTile.width = 256
      grainTile.height = 256
      const g = grainTile.getContext("2d")
      if (g) {
        const id = g.createImageData(256, 256)
        for (let i = 0; i < id.data.length; i += 4) {
          const v = Math.random() * 255
          id.data[i] = id.data[i + 1] = id.data[i + 2] = v
          id.data[i + 3] = Math.random() < 0.5 ? 0 : 255
        }
        g.putImageData(id, 0, 0)
      }
      grainPattern = o.grain > 0 ? ctx.createPattern(grainTile, "repeat") : null
      awake = true
    }

    const draw = (now: number, dt: number) => {
      const o = opts.current
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = o.colors.background
      ctx.fillRect(0, 0, w, h)

      const r = o.interactive && !reduced ? Math.max(0, o.radius) : 0
      const s = Math.max(0, Math.min(dt, HWF_MAX_STEP_MS)) / HWF_FRAME_MS
      const ringAge = ring.t < 0 ? 1e9 : now - ring.t
      const ringR = ringAge * 0.9
      let moving = false
      warmLen.fill(0)
      // At-rest dots go straight into one path; displaced ones are set aside by warm step.
      ctx.beginPath()
      for (let i = 0; i < count; i++) {
        const j = i * 7
        let x = dots[j]
        let y = dots[j + 1]
        let vx = dots[j + 2]
        let vy = dots[j + 3]
        const hx = dots[j + 4]
        const hy = dots[j + 5]
        if (!reduced) {
          if (ringAge < 900) {
            const dx = hx - ring.x
            const dy = hy - ring.y
            const d = Math.sqrt(dx * dx + dy * dy) + 0.001
            const band = 1 - Math.min(1, Math.abs(d - ringR) / 26)
            if (band > 0) {
              const f = band * 3.2 * (1 - ringAge / 900) * s
              vx += (dx / d) * f
              vy += (dy / d) * f
            }
          }
          const st = hwfStep(x, y, vx, vy, hx, hy, px, py, r, dt)
          x = st[0]
          y = st[1]
          vx = st[2]
          vy = st[3]
          if (Math.abs(vx) + Math.abs(vy) > 0.02 || Math.abs(x - hx) + Math.abs(y - hy) > 0.05) moving = true
          else {
            x = hx
            y = hy
            vx = 0
            vy = 0
          }
          dots[j] = x
          dots[j + 1] = y
          dots[j + 2] = vx
          dots[j + 3] = vy
        }
        const k = x === hx && y === hy ? 0 : hwfWarmth(x, y, hx, hy, 28)
        if (k > 0.02) {
          const b = hwfWarmStep(k)
          warmIdx[b][warmLen[b]++] = i
        } else {
          const rad = dots[j + 6]
          ctx.moveTo(x + rad, y)
          ctx.arc(x, y, rad, 0, 6.2832)
        }
      }
      ctx.fillStyle = o.colors.ink
      ctx.fill()
      for (let b = 0; b < HWF_WARM_STEPS; b++) {
        const n = warmLen[b]
        if (n === 0) continue
        const list = warmIdx[b]
        ctx.beginPath()
        for (let q = 0; q < n; q++) {
          const j = list[q] * 7
          const x = dots[j]
          const y = dots[j + 1]
          const rad = dots[j + 6]
          ctx.moveTo(x + rad, y)
          ctx.arc(x, y, rad, 0, 6.2832)
        }
        ctx.fillStyle = warmColors[b]
        ctx.fill()
      }

      if (grainPattern && o.grain > 0) {
        ctx.globalAlpha = Math.min(1, o.grain) * 0.09
        ctx.globalCompositeOperation = "overlay"
        ctx.fillStyle = grainPattern
        ctx.fillRect(0, 0, w, h)
        ctx.globalAlpha = 1
        ctx.globalCompositeOperation = "source-over"
      }
      // Sleep once everything is home and nothing is pushing.
      awake = moving || ringAge < 900 || px > -1e4
    }

    const loop = (now: number) => {
      raf = 0
      if (!visible) {
        last = 0
        return
      }
      // The real time since the last frame (one 60 Hz frame after a sleep), clamped.
      const dt = last > 0 ? Math.min(Math.max(0, now - last), HWF_MAX_STEP_MS) : HWF_FRAME_MS
      last = now
      draw(now, dt)
      if (awake) raf = requestAnimationFrame(loop)
      else last = 0
    }
    const wake = () => {
      awake = true
      if (!raf && visible) raf = requestAnimationFrame(loop)
    }

    const toLocal = (e: PointerEv) => {
      const b = canvas.getBoundingClientRect()
      return [e.clientX - b.left, e.clientY - b.top]
    }
    const onMove = (e: PointerEv) => {
      if (!opts.current.interactive) return
      const p = toLocal(e)
      px = p[0]
      py = p[1]
      wake()
    }
    const onLeave = () => {
      px = -1e5
      py = -1e5
      wake()
    }
    const onDown = (e: PointerEv) => {
      if (!opts.current.interactive || reduced) return
      if ((e.target as HTMLElement).closest("a,button")) return
      const p = toLocal(e)
      ring = { x: p[0], y: p[1], t: performance.now() }
      wake()
    }

    layout()
    draw(performance.now(), HWF_FRAME_MS)
    wake()

    root.addEventListener("pointermove", onMove)
    root.addEventListener("pointerleave", onLeave)
    root.addEventListener("pointerdown", onDown)
    const ro = new ResizeObserver(() => {
      layout()
      wake()
    })
    ro.observe(root)
    const io = new IntersectionObserver((entries) => {
      visible = entries[0] ? entries[0].isIntersecting : true
      if (visible) wake()
    })
    io.observe(root)
    // A web font that lands late re-sets the word in its real face.
    let alive = true
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => {
        if (!alive) return
        layout()
        wake()
      })
    }

    return () => {
      alive = false
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
      root.removeEventListener("pointermove", onMove)
      root.removeEventListener("pointerleave", onLeave)
      root.removeEventListener("pointerdown", onDown)
    }
  }, [key])

  const toTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <footer
      ref={rootRef}
      className={"hwf-root " + className}
      data-align={align}
      style={
        {
          height,
          "--hwf-bg": colors.background,
          "--hwf-ink": colors.ink,
          "--hwf-mono": monoFamily,
        } as React.CSSProperties
      }
    >
      <style>{HWF_CSS}</style>
      <canvas ref={canvasRef} aria-hidden="true" />
      <span className="hwf-sr">{wordmark}</span>
      <div className="hwf-top">
        <div className="hwf-brand">
          <strong>{label}</strong>
          <span>{meta}</span>
        </div>
        {columns.map((col) => (
          <nav className="hwf-col" key={col.title} aria-label={col.title}>
            <h3>{col.title}</h3>
            <ul>
              {col.links.map((l) => (
                <li key={l.label}>
                  <a href={l.href || "#"}>{l.label}</a>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="hwf-rule">
        {backToTop ? (
          <button type="button" className="hwf-up" onClick={toTop}>
            Back to top ↑
          </button>
        ) : null}
      </div>
    </footer>
  )
}

type PointerEv = PointerEvent
