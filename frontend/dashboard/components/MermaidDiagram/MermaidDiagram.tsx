import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

// Mermaid bakes text/fill colors into the SVG at render time, so the palette
// must match the app theme BEFORE each render. Kept in sync with the CSS
// variables in base.css (:root = dark, [data-theme] = light).
//
// Two traps in mermaid's `base` theme make that harder than it looks:
//
//  1. Missing variables are DERIVED from the handful we do set, and the
//     derivation branches on `darkMode`. With `darkMode` unset mermaid derives
//     the *light* variants — e.g. erDiagram row fills become
//     `lighten(mainBkg, 75)` (94% lightness, i.e. near-white), which is what
//     paints white stripes on a dark panel.
//  2. Some variables are hard-coded literals in the base theme and are never
//     derived: `altSectionBkgColor: 'white'`, `noteBkgColor: '#fff5ad'`,
//     `noteTextColor: '#333'`, `gridColor`/`doneTaskBkgColor: 'lightgrey'`,
//     `excludeBkgColor: '#eeeeee'`, `attributeBackgroundColorOdd/Even:
//     '#ffffff'/'#f2f2f2'`. They have no dark counterpart at all, so each
//     theme must override them explicitly.
//
// Flowcharts (the only diagrams we used to emit) read `primaryColor`/
// `mainBkg` only, so trap 1 never showed up. Category routing now emits
// erDiagram/classDiagram/sequenceDiagram, whose renderers read `rowOdd`,
// `rowEven`, `actorBkg`, `signalColor`, … — hence the white patches.

/** Palette roles shared by both themes, mapped onto mermaid's variable names. */
interface Palette {
  darkMode: boolean
  surfaceDim: string
  surface: string
  surfaceElevated: string
  border: string
  borderStrong: string
  accent: string
  text: string
  line: string
}

const DARK_PALETTE: Palette = {
  darkMode: true,
  surfaceDim: '#181823', // --color-bg
  surface: '#1f2030', // --color-bg-card
  surfaceElevated: '#25273c', // --color-bg-elevated
  border: '#2e3248', // --color-border
  borderStrong: '#3e4c7a', // --color-border-strong
  accent: '#537fe7', // --color-accent
  text: '#e9f8f9',
  line: '#94a3b8',
}

const LIGHT_PALETTE: Palette = {
  darkMode: false,
  surfaceDim: '#f4f6fb',
  surface: '#e5e9f4',
  surfaceElevated: '#eef1f9',
  border: '#d5dbeb',
  borderStrong: '#b9c2da',
  accent: '#3b66c4',
  text: '#161a2b',
  line: '#5a6379',
}

const themeVariablesFor = (p: Palette) => ({
  darkMode: p.darkMode,
  background: 'transparent',
  fontSize: '14px',
  fontFamily: 'Geist, system-ui, sans-serif',

  // Core trio — the only variables flowcharts care about.
  primaryColor: p.surfaceElevated,
  primaryTextColor: p.text,
  primaryBorderColor: p.accent,
  secondaryColor: p.surface,
  secondaryTextColor: p.text,
  secondaryBorderColor: p.borderStrong,
  tertiaryColor: p.surfaceDim,
  textColor: p.text,
  lineColor: p.line,

  // Every variable below is one mermaid would otherwise leave at its light
  // base-theme default while rendering on a dark panel.
  mainBkg: p.surfaceElevated,
  nodeBkg: p.surfaceElevated,
  nodeBorder: p.accent,
  nodeTextColor: p.text,
  clusterBkg: p.surface,
  clusterBorder: p.borderStrong,
  titleColor: p.text,
  edgeLabelBackground: p.surface,

  // sequenceDiagram
  actorBkg: p.surfaceElevated,
  actorBorder: p.accent,
  actorTextColor: p.text,
  actorLineColor: p.borderStrong,
  signalColor: p.line,
  signalTextColor: p.text,
  labelBoxBkgColor: p.surfaceElevated,
  labelBoxBorderColor: p.accent,
  labelTextColor: p.text,
  loopTextColor: p.text,
  activationBkgColor: p.surface,
  activationBorderColor: p.borderStrong,
  sequenceNumberColor: p.surfaceDim,
  noteBkgColor: p.surfaceElevated,
  noteTextColor: p.text,
  noteBorderColor: p.borderStrong,
  altSectionBkgColor: p.surface,
  sectionBkgColor: p.surfaceDim,
  sectionBkgColor2: p.surfaceElevated,

  // erDiagram entity tables (rowOdd/rowEven paint the alternating rows)
  rowOdd: p.surface,
  rowEven: p.surfaceElevated,
  attributeBackgroundColorOdd: p.surface,
  attributeBackgroundColorEven: p.surfaceElevated,

  // gantt / state / misc
  gridColor: p.border,
  taskBkgColor: p.surfaceElevated,
  taskBorderColor: p.accent,
  taskTextColor: p.text,
  taskTextOutsideColor: p.text,
  taskTextDarkColor: p.text,
  activeTaskBkgColor: p.borderStrong,
  activeTaskBorderColor: p.accent,
  doneTaskBkgColor: p.surface,
  doneTaskBorderColor: p.borderStrong,
  excludeBkgColor: p.surfaceDim,
  personBkg: p.surfaceElevated,
  personBorder: p.accent,
  errorBkgColor: p.surface,
  errorTextColor: p.text,
})

const currentPalette = () =>
  document.documentElement.getAttribute('data-theme') === 'light'
    ? LIGHT_PALETTE
    : DARK_PALETTE

const applyMermaidTheme = () => {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    themeVariables: themeVariablesFor(currentPalette()),
  })
}

// Unique ids are required by mermaid.render(); a module-level counter is
// enough because diagrams render one at a time per expanded accordion.
let renderSeq = 0

interface MermaidDiagramProps {
  /** Mermaid diagram definition (flowchart, sequenceDiagram, ...). */
  definition: string
}

/**
 * Renders a Mermaid diagram definition as an SVG.
 *
 * If the definition is invalid (LLM output can be imperfect), the component
 * renders nothing — the text explanation next to it is always the fallback.
 *
 * Hardening against mermaid's error behavior: (1) the definition is parsed
 * with mermaid.parse() BEFORE render() — parse failures throw cleanly
 * without touching the DOM, whereas a render() failure injects a "Syntax
 * error in text" SVG into document.body BEFORE throwing, leaking an error
 * blob below the whole app; (2) on any render failure the orphaned error
 * element is removed explicitly, so nothing mermaid inserted survives
 * outside React.
 *
 * Theme-aware: re-initializes mermaid and re-renders the SVG whenever the
 * app's data-theme attribute flips (dark ⇄ light), since colors are baked
 * into the SVG markup at render time.
 */
export default function MermaidDiagram({ definition }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    const id = `concept-diagram-${++renderSeq}`

    const removeOrphanErrorArtifacts = () => {
      // mermaid appends a temp element `#<id>_svg_error` to document.body
      // on failure; nothing in React owns it, so clean up.
      document.getElementById(`${id}_svg_error`)?.remove()
    }

    async function draw() {
      if (!containerRef.current) return
      applyMermaidTheme()
      try {
        // Parse first: throws without DOM side effects on bad syntax.
        await mermaid.parse(definition)
        const { svg } = await mermaid.render(id, definition)
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
          setFailed(false)
        }
      } catch {
        // Broken diagram definition — hide the box, keep the text,
        // and strip anything mermaid leaked into document.body.
        removeOrphanErrorArtifacts()
        if (!cancelled) setFailed(true)
      }
    }

    void draw()

    // Re-render when the app theme flips (colors live in the SVG).
    const observer = new MutationObserver(() => {
      if (!cancelled) void draw()
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    return () => {
      cancelled = true
      observer.disconnect()
      removeOrphanErrorArtifacts()
    }
  }, [definition])

  if (failed) return null

  return (
    <div className="concept-diagram">
      <p className="card-label">Visual explanation</p>
      <div ref={containerRef} className="concept-diagram-svg" />
    </div>
  )
}
