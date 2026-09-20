const STEPS = [
  {
    n: "1",
    title: "Install CodeLith",
    code: "pip install codelith",
    packageLink: true,
  },
  {
    n: "2",
    title: "Configure your AI provider",
    code: "codelith setup",
    hint: "Click the links below to get the keys or Configure your own LLM provider",
    providers: true,
  },
  {
    n: "3",
    title: "Start building",
    code: "codelith",
    hint: "The CLI starts a local daemon and opens an interactive session.",
  },
  {
    n: "4",
    title: "Learn what you build",
    code: "open the dashboard",
    hint: "Concepts, diagrams, and assessments appear as the agent works.",
  },
];

export default function GetStarted() {
  return (
    <section className="section start" id="get-started">
      <div className="container">
        <div className="section-head">
          <span className="kicker">Get started</span>
          <h2 className="section-title">Four steps from install to insight.</h2>
        </div>

        <ol className="start__steps">
          {STEPS.map((step) => (
            <li key={step.n} className="start__step">
              <span className="start__num">{step.n}</span>
              <div>
                <h3>{step.title}</h3>
                <code className="start__code">{step.code}</code>
                {step.packageLink && (
                  <a
                    className="start__package-link"
                    href="https://pypi.org/project/codelith/0.1.0/"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View my PyPI package
                  </a>
                )}
                {step.hint && <p className="start__hint">{step.hint}</p>}
                {step.providers && (
                  <ul className="start__providers">
                    <li>
                      <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer">
                        Groq
                      </a>
                    </li>
                    <li>
                      <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">
                        OpenRouter
                      </a>
                    </li>
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ol>

      </div>
    </section>
  );
}
