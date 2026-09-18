import { site } from "@/lib/site";

const STEPS = [
  {
    n: "1",
    title: "Install CodeLith",
    code: "pip install codelith",
  },
  {
    n: "2",
    title: "Configure your AI provider",
    code: "codelith setup",
    hint: "Groq and/or OpenRouter keys — stored in your OS credential store or a .env file.",
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

        <div className="start__terminal" role="img" aria-label="Install and run CodeLith">
          <div className="start__titlebar">
            <span className="demo__dot" aria-hidden="true" />
            <span className="demo__dot" aria-hidden="true" />
            <span className="demo__dot" aria-hidden="true" />
          </div>
          <div className="start__body">
            <p>
              <span className="start__prompt">$</span>
              <span className="start__cmd">{site.installCommand}</span>
            </p>
            <p>
              <span className="start__prompt">$</span>
              <span className="start__cmd">codelith</span>
            </p>
            <p className="start__out">
              ┌─────────────────────────────────────────────┐
            </p>
            <p className="start__out">
              │&nbsp;&nbsp;C O D E L I T H&nbsp;&nbsp;—&nbsp;&nbsp;local AI mentor session&nbsp;&nbsp;│
            </p>
            <p className="start__out">
              └─────────────────────────────────────────────┘
            </p>
          </div>
        </div>

        <ol className="start__steps">
          {STEPS.map((step) => (
            <li key={step.n} className="start__step">
              <span className="start__num">{step.n}</span>
              <div>
                <h3>{step.title}</h3>
                <code className="start__code">{step.code}</code>
                {step.hint && <p className="start__hint">{step.hint}</p>}
              </div>
            </li>
          ))}
        </ol>

        <p className="start__python">
          Requires Python {site.pythonRequires}. Works fully locally — session
          state stays in SQLite on your machine.
        </p>
      </div>
    </section>
  );
}
