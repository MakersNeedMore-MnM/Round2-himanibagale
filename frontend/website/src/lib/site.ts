/**
 * Site-wide configuration. Update these values in one place — e.g. when
 * the PyPI package goes live, set `pypiUrl` and flip `pypiPublished`.
 */

export const site = {
  name: "CodeLith",
  tagline: "Build with AI. Understand what you build.",

  githubUrl: "https://github.com/MakersNeedMore-MnM/Round2-himanibagale",

  /**
   * PyPI is not live yet — the UI renders the command without a link
   * while `pypiPublished` is false, and links pypi.org/project/codelith
   * once flipped. No other component needs to change.
   */
  pypiPublished: false,
  pypiUrl: "https://pypi.org/project/codelith/",

  installCommand: "pip install codelith",

  /** Minimum Python version, mirrored from pyproject.toml. */
  pythonRequires: "3.10+",
} as const;
