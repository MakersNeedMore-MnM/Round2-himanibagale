const STEPS = [
  {
    n: "01",
    title: "Prompt",
    text: "Ask CodeLith to build something — in the terminal, in plain language.",
  },
  {
    n: "02",
    title: "AI builds",
    text: "The coding agent reads, writes, and runs code in your project, using your chosen models.",
  },
  {
    n: "03",
    title: "Concepts detected",
    text: "As the implementation takes shape, CodeLith identifies the real programming concepts inside the changes.",
  },
  {
    n: "04",
    title: "Learn on the dashboard",
    text: "Each concept gets an explanation and a diagram on your dashboard — plus questions that check understanding.",
  },
];

function ConceptCard() {
  return (
    <div className="concept-card" aria-label="Example concept detection">
      <div className="concept-card__head">
        <span className="concept-card__label">New concept detected</span>
        <span className="concept-card__time">just now</span>
      </div>
      <p className="concept-card__name">Pydantic Models</p>
      <p className="concept-card__desc">
        Data validation using type hints — models declare the shape of your
        data, and pydantic enforces it at runtime.
      </p>
      <div className="concept-card__foot">
        <span className="concept-card__tag">Libraries / Validation</span>
        <span className="concept-card__open">Open concept →</span>
      </div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <section className="section hiw" id="how-it-works">
      <div className="container">
        <div className="section-head">
          <span className="kicker">How it works</span>
          <h2 className="section-title">
            The work the agent does becomes the curriculum.
          </h2>
          <p>
            CodeLith doesn&apos;t attach a generic lesson to your session. It
            follows the actual changes the agent made and finds the important
            ideas inside them.
          </p>
        </div>

        <div className="hiw__grid">
          <ol className="hiw__steps">
            {STEPS.map((step) => (
              <li key={step.n} className="hiw__step">
                <span className="hiw__num">{step.n}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="hiw__example">
            <ConceptCard />
          </div>
        </div>
      </div>
    </section>
  );
}
