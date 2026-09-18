const MODES = [
  {
    name: "Learn",
    slug: "learn",
    text: "Every new concept gets explained and assessed. Best when you're building to understand.",
  },
  {
    name: "Pair Programming",
    slug: "pair-programming",
    text: "Focus on shipping while CodeLith quietly tracks concepts and asks the occasional question.",
  },
  {
    name: "Autonomous",
    slug: "autonomous",
    text: "Minimal interruptions — the agent implements and debugs; learning stays available on the dashboard.",
  },
];

export default function Modes() {
  return (
    <section className="section modes" id="modes">
      <div className="container">
        <div className="section-head">
          <span className="kicker">Modes</span>
          <h2 className="section-title">Three ways to work.</h2>
          <p>
            Switch from the terminal or the dashboard at any time — the daemon
            keeps both sides in sync.
          </p>
        </div>

        <div className="modes__grid">
          {MODES.map((mode) => (
            <div
              key={mode.slug}
              className={`modes__card${
                mode.slug === "pair-programming" ? " modes__card--pair" : ""
              }`}
            >
              <span className="badge">{mode.slug}</span>
              <h3>{mode.name}</h3>
              <p>{mode.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
