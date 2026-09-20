import { site } from "@/lib/site";

/**
 * Condensed four-step version of the repo's CONTRIBUTING.md — the full
 * guide stays the source of truth and is linked below the cards.
 */
const STEPS = [
  {
    n: "1",
    title: "Get the code",
    text: "Fork the repository on GitHub, clone your fork, and create a branch for your change.",
  },
  {
    n: "2",
    title: "Set up the project",
    text: "Create a virtual environment and install CodeLith in editable mode with a single command.",
  },
  {
    n: "3",
    title: "Check your change",
    text: "Keep changes focused and follow the existing code style. Add or update tests when behavior changes — and build the frontend for dashboard work.",
  },
  {
    n: "4",
    title: "Open a pull request",
    text: "Push your branch and open a PR from your fork. Describe what changed, why it helps, and how you tested it — screenshots welcome for visible dashboard changes.",
  },
];

export default function Contribute() {
  return (
    <section className="section contrib" id="contribute">
      <div className="container">
        <div className="section-head">
          <span className="kicker">Open source</span>
          <h2 className="section-title">Want to contribute?</h2>
          <p>
            Small fixes, documentation updates, tests, and new ideas are all
            welcome.
          </p>
        </div>

        <ol className="contrib__grid">
          {STEPS.map((step) => (
            <li key={step.n} className="contrib__card">
              <span className="contrib__num">{step.n}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="contrib__more">
          Full setup walkthrough in{" "}
          <a
            href={site.contributingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            CONTRIBUTING.md
          </a>{" "}
          on GitHub.
        </p>
      </div>
    </section>
  );
}
