export default function Problem() {
  return (
    <section className="section problem">
      <div className="container problem__grid">
        <div className="section-head problem__head">
          <span className="kicker">The problem</span>
          <h2 className="section-title">
            AI can accelerate building faster than understanding.
          </h2>
          <p>
            Modern AI tools make it easy to generate working software in
            minutes. For anyone still learning, that speed has a cost: the
            code compiles, the tests pass — and the reasoning behind it stays
            a black box.
          </p>
        </div>

        <ul className="problem__list">
          <li className="problem__item">
            <span className="problem__marker" aria-hidden="true">
              ?
            </span>
            <div>
              <h3>Code you can&apos;t explain</h3>
              <p>
                You shipped it, but asked <em>why</em> it&apos;s written that
                way, the answer is &ldquo;the AI wrote it.&rdquo;
              </p>
            </div>
          </li>
          <li className="problem__item">
            <span className="problem__marker" aria-hidden="true">
              ?
            </span>
            <div>
              <h3>Concepts you never met</h3>
              <p>
                The implementation introduced patterns, libraries, and
                trade-offs that never got a moment of your attention.
              </p>
            </div>
          </li>
          <li className="problem__item">
            <span className="problem__marker" aria-hidden="true">
              ?
            </span>
            <div>
              <h3>Progress you can&apos;t see</h3>
              <p>
                Nothing tracks what you actually understood across sessions —
                so the same gaps follow you into the next project.
              </p>
            </div>
          </li>
        </ul>
      </div>
    </section>
  );
}
