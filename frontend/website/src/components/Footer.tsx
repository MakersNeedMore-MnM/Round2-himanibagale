import { site } from "@/lib/site";

export default function Footer() {
  const pypi = site.pypiPublished ? site.pypiUrl : null;

  return (
    <footer className="footer">
      <div className="container footer__inner">
        <div className="footer__brand">
          <span className="footer__name">{site.name}</span>
          <span className="footer__tagline">{site.tagline}</span>
        </div>

        <nav className="footer__links" aria-label="Footer">
          <a href={site.githubUrl} target="_blank" rel="noopener noreferrer">
            View on GitHub
          </a>
          {pypi ? (
            <a href={pypi} target="_blank" rel="noopener noreferrer">
              PyPI
            </a>
          ) : (
            <span className="footer__soon" title="Package name planned; link added on publication">
              PyPI (soon)
            </span>
          )}
          <a href="#how-it-works">How it works</a>
          <a href="#get-started">Get started</a>
        </nav>
      </div>
    </footer>
  );
}
