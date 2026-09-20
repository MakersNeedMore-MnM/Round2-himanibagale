import { site } from "@/lib/site";

function GithubIcon() {
  return (
    <svg className="icon-github" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .297a12 12 0 0 0-3.79 23.388c.6.113.82-.26.82-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.73.084-.73 1.205.085 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.108-.776.418-1.305.762-1.605-2.665-.303-5.466-1.332-5.466-5.931 0-1.31.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 0 1 3.003-.404c1.02.005 2.047.138 3.003.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.652.242 2.873.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.61-2.805 5.624-5.475 5.921.43.372.823 1.102.823 2.222v3.293c0 .32.216.694.825.576A12 12 0 0 0 12 .297" />
    </svg>
  );
}

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <div className="footer__brand">
          <span className="footer__name">{site.name}</span>
          <span className="footer__tagline">{site.tagline}</span>
        </div>

        <nav className="footer__links" aria-label="Footer">
          <a href={site.githubUrl} target="_blank" rel="noopener noreferrer">
            <GithubIcon />
            View on GitHub
          </a>
          <a href="#get-started">Get started</a>
        </nav>
      </div>
    </footer>
  );
}
