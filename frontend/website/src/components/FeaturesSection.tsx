const FEATURES = [
  {
    title: "Multi-agent AI architecture",
    text: "using specialized coding, debugging, teaching, assessment, grading, and concept-detection agents.",
  },
  {
    title: "Interactive CLI",
    text: "with chat, mode switching, session reset, and daemon controls.",
  },
  {
    title: "Three working modes",
    text: "learn, pair-programming, and autonomous.",
  },
  {
    title: "Local FastAPI daemon",
    text: "that serves the API and coordinates agent activity.",
  },
  {
    title: "Dashboard",
    text: "for conversations, concepts, teachings, assessments, and progress.",
  },
  {
    title: "Secure API-key handling",
    text: "through environment variables, .env files, and the operating system credential store.",
  },
  {
    title: "Visual Mermaid diagrams",
    text: "generated for programming concepts and rendered in the dashboard.",
  },
  {
    title: "Socratic assessments",
    text: "that test whether users understand concepts rather than merely recognize them.",
  },
  {
    title: "Automatic debugging flow",
    text: "when coding commands fail.",
  },
];

export default function FeaturesSection() {
  return (
    <section className="section features" id="features">
      <div className="container">
        <div className="section-head">
          <span className="kicker">Technical features</span>
          <h2 className="section-title">Everything CodeLith brings to the build.</h2>
        </div>

        <ul className="features__list">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="features__item">
              <strong>{feature.title}</strong>
              <span>{feature.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
