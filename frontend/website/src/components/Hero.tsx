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
        <h1 className="hero__title">
          A coding agent
          <br />
          <span className="text-gradient">that teaches you what it builds.</span>
        </h1>

        <p className="hero__sub">
          CodeLith is an open-source AI coding agent that builds software with
          you — and while it works, it identifies the programming concepts
          appearing in the implementation and turns them into explanations,
          diagrams, and questions on your dashboard.
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
            View on GitHub
          </a>
        </div>

        <InstallCommand />
      </div>
    </section>
  );
}
