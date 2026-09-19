"""Tests for the model-role config resolver (backend.llm.config).

The critical invariant is the "only when the user wants it" contract:
resolution must fall back to built-in defaults with NO config file on
disk, and ``config.toml`` must never be created as a side effect of
reading.  Writes happen only through :func:`set_model`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import backend.llm.config as config
from backend.llm.config import MODEL_ROLES, get_model, set_model, unset_model


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path: Path):
    """Point the config dir at a per-test temp home and clear the cache."""
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.toml")
    _cache = getattr(config, "_cache")
    _cache["mtime"] = None
    _cache["models"] = {}
    # Belt and braces: no role env var from the outer environment may
    # leak into these tests.
    for role in MODEL_ROLES.values():
        monkeypatch.delenv(role["env"], raising=False)
    yield tmp_path


# ---------------------------------------------------------------------------
# No config file: pure defaults, zero side effects
# ---------------------------------------------------------------------------


def test_no_config_file_resolves_to_defaults():
    for role, entry in MODEL_ROLES.items():
        assert get_model(role) == entry["default"]


def test_reading_never_creates_config_file():
    for role in MODEL_ROLES:
        get_model(role)
    assert not config.config_path().exists()


def test_unknown_role_raises():
    with pytest.raises(KeyError):
        get_model("does-not-exist")


# ---------------------------------------------------------------------------
# config.toml layer
# ---------------------------------------------------------------------------


def test_file_override_wins_over_default(isolated_config: Path):
    set_model("grading", "test/some-model")
    assert get_model("grading") == "test/some-model"
    # Untouched roles keep their defaults.
    assert get_model("coding") == MODEL_ROLES["coding"]["default"]


def test_set_creates_file_with_models_table():
    set_model("coding", "x/y")
    text = config.config_path().read_text(encoding="utf-8")
    assert "[models]" in text
    assert 'coding = "x/y"' in text


def test_set_preserves_other_roles_and_sections():
    set_model("coding", "x/y")
    config.config_path().write_text(
        config.config_path().read_text(encoding="utf-8") + '\n[other]\nkey = "keep"\n',
        encoding="utf-8",
    )
    set_model("grading", "a/b")
    text = config.config_path().read_text(encoding="utf-8")
    assert 'coding = "x/y"' in text
    assert 'grading = "a/b"' in text
    assert "[other]" in text and 'key = "keep"' in text


def test_unset_removes_override_but_keeps_file():
    set_model("coding", "x/y")
    assert unset_model("coding") is True
    assert get_model("coding") == MODEL_ROLES["coding"]["default"]
    assert config.config_path().exists()  # file kept, role gone
    assert unset_model("coding") is False


def test_unset_role_never_set_returns_false():
    assert unset_model("teaching") is False


def test_set_rejects_unknown_role_and_empty_slug():
    with pytest.raises(KeyError):
        set_model("nope", "x/y")
    with pytest.raises(ValueError):
        set_model("coding", "   ")


def test_corrupt_toml_degrades_to_defaults():
    config.config_path().write_text("[models\nbroken ===", encoding="utf-8")
    for role, entry in MODEL_ROLES.items():
        assert get_model(role) == entry["default"]


def test_set_refuses_to_overwrite_corrupt_file():
    config.config_path().write_text("not [valid toml", encoding="utf-8")
    with pytest.raises(ValueError):
        set_model("coding", "x/y")
    # The user's broken file is untouched.
    assert config.config_path().read_text(encoding="utf-8") == "not [valid toml"


def test_file_table_missing_or_malformed_entries_ignored():
    config.config_path().write_text(
        '[models]\ncoding = ""\nteaching = 42\n[not_models]\ngrading = "x/z"\n',
        encoding="utf-8",
    )
    assert get_model("coding") == MODEL_ROLES["coding"]["default"]  # empty ignored
    assert get_model("teaching") == "42"  # non-string coerced to string
    assert get_model("grading") == MODEL_ROLES["grading"]["default"]  # wrong table


# ---------------------------------------------------------------------------
# mtime cache: file edits picked up without restart
# ---------------------------------------------------------------------------


def test_file_edits_are_picked_up_after_first_read():
    assert get_model("coding") == MODEL_ROLES["coding"]["default"]
    set_model("coding", "x/y")  # write invalidates the cache explicitly...
    assert get_model("coding") == "x/y"
    # ...but a hand-edit must work too (no daemon restart expected).
    # NTFS lazily updates timestamps (~10ms granularity), so space the
    # writes out to guarantee a fresh mtime — real hand-edits always do.
    import time

    time.sleep(0.05)
    config.config_path().write_text('[models]\ncoding = "hand/edited"\n', encoding="utf-8")
    assert get_model("coding") == "hand/edited"


# ---------------------------------------------------------------------------
# Env var layer (highest precedence)
# ---------------------------------------------------------------------------


def test_env_var_beats_config_file_and_default(monkeypatch, isolated_config: Path):
    set_model("coding", "from/config")
    monkeypatch.setenv(MODEL_ROLES["coding"]["env"], "from/env")
    assert get_model("coding") == "from/env"


def test_env_var_whitespace_only_is_ignored(monkeypatch, isolated_config: Path):
    monkeypatch.setenv(MODEL_ROLES["coding"]["env"], "   ")
    assert get_model("coding") == MODEL_ROLES["coding"]["default"]


# ---------------------------------------------------------------------------
# Same model for multiple roles / full customization
# ---------------------------------------------------------------------------


def test_multiple_roles_can_share_one_model(isolated_config: Path):
    for role in ("teaching", "grading", "assessment", "detection"):
        set_model(role, "shared/model")
    for role in ("teaching", "grading", "assessment", "detection"):
        assert get_model(role) == "shared/model"


# ---------------------------------------------------------------------------
# TOML serialization helpers
# ---------------------------------------------------------------------------


def test_toml_string_escaping():
    assert config._toml_string('a"b\\c') == '"a\\"b\\\\c"'
