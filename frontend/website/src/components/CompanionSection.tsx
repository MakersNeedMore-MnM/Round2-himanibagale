export default function CompanionSection() {
  return (
    <section className="section companion" id="companion">
      <div className="container">
        <div className="knowledge-copy">
          <span className="kicker">The CodeLith companion</span>
          <h2 className="section-title">
            A Knowledge Graph That Evolves With Every Line You Ship.
          </h2>
          <p>
            When you use AI assistants, you ship code fast - but your own
            technical depth stagnates. CodeLith&apos;s companion app gives you
            continuous intellectual leverage.
          </p>
          <ul>
            <li>
              <strong>Automatic Interactive Flashcards</strong>
              <span>
                Spaced-repetition prompts scheduled at 1, 3, and 7 days after
                code generation.
              </span>
            </li>
            <li>
              <strong>Auto-Rendered Architecture Flows</strong>
              <span>
                Turn messy distributed logic into clear diagrams showing data
                contracts.
              </span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
