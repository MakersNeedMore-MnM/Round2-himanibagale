"""Tests for coding-agent path resolution (backend.agents.coding_agent).

Covers the sandbox contract: every path a model might invent — POSIX
home paths, guessed usernames, home-relative ``~/`` paths, quoted paths —
either resolves inside the workspace or is rejected with an error that
names the workspace root so the model can self-correct.
"""

from __future__ import annotations

from pathlib import Path

import backend.agents.coding_agent as ca


ROOT = str(Path(__file__).resolve().parents[2])


def test_relative_path_resolves_into_workspace():
    target, error = ca._resolve_in_workspace("index.html", ROOT)
    assert error is None
    assert target == (Path(ROOT) / "index.html").resolve()


def test_posix_absolute_path_is_rebased_into_workspace():
    # The classic hallucination from the failed himani-website run.
    target, error = ca._resolve_in_workspace("/home/user/himani-website/index.html", ROOT)
    assert error is None
    assert target == (Path(ROOT) / "home/user/himani-website/index.html").resolve()


def test_windows_absolute_path_inside_workspace_is_kept():
    target, error = ca._resolve_in_workspace(f"{ROOT}\\index.html", ROOT)
    assert error is None
    assert target == (Path(ROOT) / "index.html").resolve()


def test_windows_absolute_path_outside_workspace_is_rejected():
    _, error = ca._resolve_in_workspace("C:/Windows/system32/config", ROOT)
    assert error is not None
    assert "outside the workspace" in error
    # Actionable: names the root so the model can self-correct.
    assert ROOT in error
    assert "RELATIVE" in error


def test_tilde_path_is_workspace_relative():
    target, error = ca._resolve_in_workspace("~/index.html", ROOT)
    assert error is None
    assert target == (Path(ROOT) / "index.html").resolve()


def test_quoted_path_is_unquoted():
    target, error = ca._resolve_in_workspace('"index.html"', ROOT)
    assert error is None
    assert target == (Path(ROOT) / "index.html").resolve()


def test_parent_escape_is_rejected():
    _, error = ca._resolve_in_workspace("../outside.txt", ROOT)
    assert error is not None
    assert "outside the workspace" in error


def test_empty_path_is_rejected():
    _, error = ca._resolve_in_workspace("   ", ROOT)
    assert error is not None
    assert "must not be empty" in error


def test_write_file_rebases_hallucinated_posix_path(tmp_path, monkeypatch):
    """Regression: the himani-website run lost index.html to path rejection."""
    monkeypatch.setattr(ca, "MAX_WRITE_SIZE", 1_000_000)
    result = ca._write_file(
        "/home/user/himani-website/index.html",
        "<h1>himani</h1>",
        str(tmp_path),
    )
    assert result.startswith("Successfully wrote")
    written = tmp_path / "home/user/himani-website/index.html"
    assert written.read_text(encoding="utf-8") == "<h1>himani</h1>"


def test_workspace_context_names_root_and_shell():
    ctx = ca.workspace_context(str(tmp_path := Path(ROOT) / "does-not-matter"))
    assert "Workspace root" in ctx
    assert "RELATIVE" in ctx
    assert "Shell:" in ctx
