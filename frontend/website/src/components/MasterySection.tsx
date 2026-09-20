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
      </div>
    </section>
  );
}
