const FEATURES = [
  {
    number: "01",
    title: "Contextual Code Generation",
    text: "Works inside your CLI or IDE. Whether you ask for an optimized LRU cache, a GraphQL schema, or a custom OAuth provider, CodeLith writes idiomatic, tested code tailored to your existing codebase.",
  },
  {
    number: "02",
    title: "Real-time Concept Extraction",
    text: "As code streams, the background AST interpreter isolates computer science paradigms, performance tradeoffs, and architectural patterns such as Idempotency Keys, Circuit Breakers, and Mutex Locks.",
  },
  {
    number: "03",
    title: "Live Companion Dashboard",
    text: "Your local web dashboard populates concurrently with interactive visual sequence diagrams, mental models, and retention check-ins to make sure you truly own what gets committed.",
  },
];

const MODES = [
  {
    number: "Mode 01",
    title: "Learn Mode",
    depth: "High Pedagogical Depth",
    text: "Paces the implementation with deliberate checkpoints. Asks conceptual questions before critical architectural decisions and explains every third-party library utilized.",
    calloutLabel: "Interactive Prompt",
    callout: "Explain why we selected a Trie over a Hash Map for this autocomplete feature?",
    icon: "⚡",
  },
  {
    number: "Mode 02",
    title: "Pair Programming",
    depth: "Balanced Workflow",
    text: "Your empathetic senior engineer co-pilot. Writes clean modular functions, annotates tricky edge conditions, and continuously logs concepts to your dashboard silently in the background.",
    calloutLabel: "Ambient Stream",
    callout: "Generated unit tests (98% coverage) + 2 concept cards dispatched to web GUI.",
    icon: "✦",
    featured: true,
  },
  {
    number: "Mode 03",
    title: "Autonomous Mode",
    depth: "Maximum Velocity",
    text: "Rapid full-project scaffolding, multi-file edits, and automated terminal command execution. Concept summaries are batched into an executive digest post-generation.",
    calloutLabel: "Post-run Artifact",
    callout: "14 files updated. Generated architecture recap with 4 visual mermaid diagrams.",
    icon: "⌖",
  },
];

function FeatureCard({ feature }: { feature: (typeof FEATURES)[number] }) {
  return (
    <article className="mastery-feature-card">
      <div>
        <span className="mastery-index">{feature.number}</span>
        <h3>{feature.title}</h3>
        <p>{feature.text}</p>
      </div>
    </article>
  );
}

function ModeCard({ mode }: { mode: (typeof MODES)[number] }) {
  return (
    <article className={`mastery-mode-card${mode.featured ? " mastery-mode-card--featured" : ""}`}>
      <div className="mastery-mode-card__header">
        <span className="mastery-mode-badge">{mode.number}{mode.featured ? " · Default" : ""}</span>
        <span className="mastery-mode-depth">{mode.depth}</span>
      </div>
      <h3>{mode.title}</h3>
      <p>{mode.text}</p>
      <div className={`mastery-callout${mode.featured ? " mastery-callout--featured" : ""}`}>
        <span className="mastery-callout__icon" aria-hidden="true">{mode.icon}</span>
        <span><strong>{mode.calloutLabel}:</strong> {mode.callout}</span>
      </div>
    </article>
  );
}

function KnowledgeGraphPreview() {
  return (
    <div className="knowledge-window" aria-label="Knowledge graph dashboard preview">
      <div className="knowledge-window__chrome">
        <span className="knowledge-window__traffic" aria-hidden="true"><i /><i /><i /></span>
        <code>localhost:3000/#knowledge-graph</code>
        <span className="knowledge-window__sync"><i /> Sync: Live</span>
      </div>
      <div className="knowledge-window__body">
        <div className="knowledge-window__project">Project: distributed-raft-node</div>
        <div className="knowledge-window__title">EXTRACTED ARCHITECTURE TREE</div>
        <div className="knowledge-flow">
          <span>Client Event<br /><small>gRPC Protobuf</small></span>
          <b>→</b>
          <span>Consensus Log<br /><small>WAL &amp; Async</small></span>
          <b>→</b>
          <span>State Machine<br /><small>Deterministic Apply</small></span>
        </div>
        <div className="knowledge-reviews">
          <div className="knowledge-review">
            <span className="knowledge-review__icon knowledge-review__icon--red">◆</span>
            <div><strong>Write-Ahead Logging (WAL) Pattern</strong><p>Why disk durability relies on sequential block append</p></div>
            <em className="knowledge-status knowledge-status--mastered">Mastered</em>
          </div>
          <div className="knowledge-review">
            <span className="knowledge-review__icon knowledge-review__icon--amber">▲</span>
            <div><strong>Heartbeat Election Timers</strong><p>Randomized jitter prevents split-vote deadlock</p></div>
            <em className="knowledge-status knowledge-status--review">Review Due</em>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MasterySection() {
  return (
    <section className="section mastery" id="mastery">
      <div className="container">
        <div className="mastery-heading">
          <span className="kicker">Engineering for mastery</span>
          <h2 className="section-title">How CodeLith Bridges Generation &amp; Understanding</h2>
        </div>

        <div className="mastery-feature-grid">
          {FEATURES.map((feature) => <FeatureCard key={feature.number} feature={feature} />)}
        </div>

        <div className="mastery-modes-heading">
          <div>
            <span className="kicker">Tailored workflow</span>
            <h2 className="section-title">Three Distinct Agent Modes</h2>
          </div>
          <p>Switch on-the-fly based on whether you want deep pedagogical immersion, fluid collaboration, or hyper-speed delivery.</p>
        </div>

        <div className="mastery-mode-grid">
          {MODES.map((mode) => <ModeCard key={mode.number} mode={mode} />)}
        </div>

        <div className="knowledge-grid">
          <div className="knowledge-copy">
            <span className="kicker">The CodeLith companion</span>
            <h2 className="section-title">A Knowledge Graph That Evolves With Every Line You Ship.</h2>
            <p>When you use generic AI assistants, you ship code fast—but your own technical depth stagnates. CodeLith&apos;s companion app gives you continuous intellectual leverage.</p>
            <ul>
              <li><strong>Automatic Interactive Flashcards</strong><span>Spaced-repetition prompts scheduled at 1, 3, and 7 days after code generation.</span></li>
              <li><strong>Auto-Rendered Architecture Flows</strong><span>Turn messy distributed logic into clear diagrams showing data contracts.</span></li>
              <li><strong>100% Offline &amp; Air-Gapped Capable</strong><span>Zero sensitive company IP sent to remote servers. Works with Ollama and vLLM.</span></li>
            </ul>
            <a className="knowledge-link" href="#demo">Explore live interactive web demo <span aria-hidden="true">→</span></a>
          </div>
          <KnowledgeGraphPreview />
        </div>
      </div>
    </section>
  );
}
