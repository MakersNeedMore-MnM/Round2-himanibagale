import { site } from "@/lib/site";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#demo", label: "Demo" },
  { href: "#dashboard", label: "Dashboard" },
  { href: "#modes", label: "Modes" },
  { href: "#get-started", label: "Get started" },
];

function LogoMark() {
  return (
    <span className="logo-mark" aria-hidden="true">
      <span className="logo-mark__chevron">&lt;</span>
      <span className="logo-mark__slash">/</span>
      <span className="logo-mark__chevron">&gt;</span>
    </span>
  );
}

export default function Navbar() {
  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <a href="#top" className="navbar__brand">
          <LogoMark />
          <span>{site.name}</span>
          <span className="navbar__beta">beta</span>
        </a>

        <nav className="navbar__links" aria-label="Sections">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>

        <a
          className="btn btn--ghost navbar__cta"
          href={site.githubUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg className="icon-star" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 2l2.9 6.26L21.5 9.27l-4.75 4.4 1.15 6.83L12 17.27l-5.9 3.23 1.15-6.83L2.5 9.27l6.6-1.01L12 2z" />
          </svg>
          GitHub
        </a>
      </div>
    </header>
  );
}
