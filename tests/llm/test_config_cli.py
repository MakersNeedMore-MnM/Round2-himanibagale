"""Tests for the ``codelith config`` CLI command group."""

from __future__ import annotations

from pathlib import Path

import backend.cli.config_cmd as config_cmd
import backend.llm.config as llm_config
from backend.llm.config import MODEL_ROLES


def test_config_show_with_no_file(capsys, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_config, "config_path", lambda: tmp_path / "config.toml")
    llm_config._cache["mtime"] = None
    llm_config._cache["models"] = {}

    code = config_cmd.main(["show"])
    out = capsys.readouterr().out

    assert code == 0
    assert "not created" in out  # no side effects advertised
    for role in MODEL_ROLES:
        assert role in out


def test_config_set_creates_file_and_show_reflects_it(capsys, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_config, "config_path", lambda: tmp_path / "config.toml")
    llm_config._cache["mtime"] = None
    llm_config._cache["models"] = {}

    assert config_cmd.main(["set", "grading", "test/model"]) == 0
    out = capsys.readouterr().out
    assert "grading = test/model" in out
    assert llm_config.config_path().exists()

    capsys.readouterr()
    assert config_cmd.main(["show"]) == 0
    out = capsys.readouterr().out
    assert "test/model" in out
    assert "config.toml" in out


def test_config_set_unknown_role_exits_2(capsys, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_config, "config_path", lambda: tmp_path / "config.toml")
    code = config_cmd.main(["set", "bogus", "x/y"])
    assert code == 2
    assert "Unknown role" in capsys.readouterr().err
    assert not llm_config.config_path().exists()


def test_config_unset_removes_override(capsys, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_config, "config_path", lambda: tmp_path / "config.toml")
    llm_config._cache["mtime"] = None
    llm_config._cache["models"] = {}

    config_cmd.main(["set", "coding", "x/y"])
    capsys.readouterr()

    assert config_cmd.main(["unset", "coding"]) == 0
    out = capsys.readouterr().out
    assert "reset" in out


def test_config_unset_without_override_is_clean_noop(capsys, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(llm_config, "config_path", lambda: tmp_path / "config.toml")
    llm_config._cache["mtime"] = None
    llm_config._cache["models"] = {}

    assert config_cmd.main(["unset", "coding"]) == 0
    assert "nothing to unset" in capsys.readouterr().out
