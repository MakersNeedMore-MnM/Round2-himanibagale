"use client";

import { useCallback, useRef, useState } from "react";
import { site } from "@/lib/site";

function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function InstallCommand() {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(site.installCommand);
    } catch {
      // Clipboard API unavailable (insecure context) — still show feedback.
    }
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  }, []);

  return (
    <div className="install" role="group" aria-label="Installation command">
      <span className="install__prompt">$</span>
      <code className="install__cmd">{site.installCommand}</code>
      <span className="install__hint" title="Package name is planned; not yet published">
        (coming to PyPI)
      </span>
      <button
        type="button"
        className={`install__copy${copied ? " install__copy--done" : ""}`}
        onClick={onCopy}
        aria-label={copied ? "Copied" : "Copy install command"}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </div>
  );
}

export default function Hero() {
  return (
    <section className="hero" id="top">
      <div className="container">
        <span className="badge hero__eyebrow">
          <span className="hero__dot" aria-hidden="true" />
          Local AI coding agent + learning dashboard
        </span>

        <h1 className="hero__title">
          Build with AI.
          <br />
          <span className="text-gradient">Understand what you build.</span>
        </h1>

        <p className="hero__sub">
          CodeLith is an open-source AI coding agent that builds software with
          you — and while it works, it identifies the programming concepts
          appearing in the implementation and turns them into explanations,
          diagrams, and questions on your dashboard. Generate code
          <em> and </em> learn it.
        </p>

        <div className="hero__actions">
          <a href="#get-started" className="btn btn--primary">
            Get Started
          </a>
          <a
            href={site.githubUrl}
            className="btn btn--ghost"
            target="_blank"
            rel="noopener noreferrer"
          >
            <svg className="icon-star" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2l2.9 6.26L21.5 9.27l-4.75 4.4 1.15 6.83L12 17.27l-5.9 3.23 1.15-6.83L2.5 9.27l6.6-1.01L12 2z" />
            </svg>
            View on GitHub
          </a>
        </div>

        <InstallCommand />

        <p className="hero__providers">
          Runs locally against Groq and OpenRouter — your keys, your machine,
          your session state.
        </p>
      </div>
    </section>
  );
}
