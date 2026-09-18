"use client";

import { useEffect, useState } from "react";

/**
 * Polished placeholder, not a fake screenshot: a stylized replay of the
 * real CodeLith flow (terminal prompt → agent tool activity → concept
 * detected → dashboard) that types itself out on a loop. When a real
 * demo GIF/recording exists, replace <TerminalMock /> with an
 * <Image>/<video> — the section around it stays as-is.
 */

const AGENT_LINES = [
  { text: "λ build a small REST API with user auth", kind: "user" as const },
  { text: "· Coding agent…", kind: "status" as const },
  { text: "  ▸ Read main.py ✓", kind: "tool" as const },
  { text: "  ▸ Wrote auth/routes.py ✓", kind: "tool" as const },
  { text: "  ▸ Ran pytest -q ✓ 4 passed", kind: "tool" as const },
  { text: "Done — auth service wired into the app.", kind: "reply" as const },
];

const CONCEPT_LINE = "New concept detected — Dependency Injection";

const DASH_LINES = [
  { text: "Dependency Injection", kind: "title" as const },
  {
    text: "Receives its dependencies instead of creating them — that's why",
    kind: "body" as const,
  },
  { text: "testing the service took one line.", kind: "body" as const },
  { text: "Assessment ready — 1 question queued", kind: "meta" as const },
];

type Phase = "terminal" | "concept" | "dashboard";

export default function Demo() {
  const [visibleLines, setVisibleLines] = useState(0);
  const [phase, setPhase] = useState<Phase>("terminal");
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) {
      // Show the finished state; no animation loop.
      setVisibleLines(AGENT_LINES.length);
      setPhase("dashboard");
      return;
    }

    let timer: ReturnType<typeof setTimeout>;

    if (phase === "terminal") {
      if (visibleLines < AGENT_LINES.length) {
        timer = setTimeout(() => setVisibleLines((v) => v + 1), 520);
      } else {
        timer = setTimeout(() => setPhase("concept"), 900);
      }
    } else if (phase === "concept") {
      timer = setTimeout(() => {
        setPhase("dashboard");
      }, 1600);
    } else {
      // Hold the dashboard, then restart the loop.
      timer = setTimeout(() => {
        setVisibleLines(0);
        setPhase("terminal");
      }, 3200);
    }

    return () => clearTimeout(timer);
  }, [phase, visibleLines, prefersReducedMotion]);

  return (
    <section className="section demo" id="demo">
      <div className="container">
        <div className="section-head">
          <span className="kicker">From building to understanding</span>
          <h2 className="section-title">Watch a build turn into a lesson.</h2>
          <p>
            The terminal is where the work happens. The dashboard is where the
            understanding happens. CodeLith connects them automatically —
            same session, same source of truth.
          </p>
        </div>

        <div className="demo__stage">
          {/* ---------------- Terminal ---------------- */}
          <div className="demo__panel demo__panel--terminal">
            <div className="demo__titlebar">
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__title">terminal — codelith</span>
            </div>
            <div className="demo__body demo__body--mono" aria-hidden="true">
              {AGENT_LINES.slice(0, visibleLines).map((line, i) => (
                <p
                  key={i}
                  className={`demo__line demo__line--${line.kind}${
                    i === visibleLines - 1 ? " demo__line--latest" : ""
                  }`}
                >
                  {line.text}
                </p>
              ))}
              {phase === "terminal" && (
                <span className="demo__caret" aria-hidden="true" />
              )}
            </div>
          </div>

          {/* ---------------- Bridge arrow ---------------- */}
          <div className={`demo__bridge${phase === "concept" ? " demo__bridge--active" : ""}`}>
            <span className="demo__bridge-label">
              {phase === "concept" ? CONCEPT_LINE : "concept detected"}
            </span>
            <span className="demo__bridge-arrow" aria-hidden="true">
              ──────▶
            </span>
          </div>

          {/* ---------------- Dashboard ---------------- */}
          <div className="demo__panel demo__panel--dash">
            <div className="demo__titlebar">
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__dot" aria-hidden="true" />
              <span className="demo__title">CodeLith dashboard</span>
            </div>
            <div className="demo__body" aria-hidden="true">
              {phase === "dashboard" ? (
                DASH_LINES.map((line, i) => (
                  <div key={i} className={`demo__dash-line demo__dash-line--${line.kind}`}>
                    {line.text}
                  </div>
                ))
              ) : (
                <div className="demo__dash-empty">
                  {phase === "terminal" ? "waiting for agent activity…" : "detecting concepts…"}
                </div>
              )}
            </div>
          </div>
        </div>

        <p className="demo__note">
          Stylized replay of a real CodeLith session — the flow, verbatim; the
          pacing, dramatized.
        </p>
      </div>
    </section>
  );
}
