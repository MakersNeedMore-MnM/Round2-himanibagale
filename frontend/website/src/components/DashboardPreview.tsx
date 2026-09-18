const AREAS = [
  {
    title: "Coding Concepts",
    text: "Every concept the agent introduced, with a plain-language explanation and a Mermaid diagram grounded in your actual code.",
  },
  {
    title: "Learning Progress",
    text: "Concepts tracked per session — what you've seen, what you've mastered, and what's still open.",
  },
  {
    title: "Assessment Questions",
    text: "Socratic questions about the code you just built, answered one at a time with instant grading feedback.",
  },
  {
    title: "Ask AI",
    text: "A chat grounded in your session's concepts, so follow-up questions stay in context.",
  },
  {
    title: "Session & Mode",
    text: "Current mode, daemon status, and a live telemetry stream of what the agent is doing.",
  },
];

export default function DashboardPreview() {
  return (
    <section className="section dash" id="dashboard">
      <div className="container">
        <div className="section-head">
          <span className="kicker">The dashboard</span>
          <h2 className="section-title">
            Your session, laid out for learning.
          </h2>
          <p>
            The dashboard mirrors the terminal in real time — both talk to the
            same local daemon, so what the agent just did is what you see.
          </p>
        </div>

        <div className="dash__grid">
          {AREAS.map((area) => (
            <div key={area.title} className="dash__card">
              <h3>{area.title}</h3>
              <p>{area.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
