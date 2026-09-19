"""Tests for keyring-backed API key storage (backend.llm.client).

The keyring layer is optional: with no keyring module (or a failing
backend) resolution must degrade to the historical env-var/.env
behavior, and :func:`store_api_key` must report failure rather than
leak the key into a plaintext file.
"""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

import backend.llm.client as client


@pytest.fixture(autouse=True)
def no_env_files(monkeypatch, tmp_path):
    """Point .env lookups at an empty temp dir and scrub both key env
    vars so the machine's real ~/.codelith/.env (or repo .env, loaded
    into os.environ by an earlier test's resolution call) can never
    satisfy resolution."""
    monkeypatch.setattr(client, "ENV_FILES", (tmp_path / ".env",))
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    monkeypatch.delenv(client.OPENROUTER_API_KEY_ENV, raising=False)


class _FakeKeyring(ModuleType):
    """Minimal stand-in for the ``keyring`` module."""

    def __init__(self, store: dict[tuple[str, str], str] | None = None, fail: bool = False):
        super().__init__("keyring")
        self.store = store or {}
        self.fail = fail
        self.set_calls: list[tuple[str, str, str]] = []

    def get_password(self, service: str, account: str):
        if self.fail:
            raise RuntimeError("no backend")
        return self.store.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        self.set_calls.append((service, account, password))
        if self.fail:
            raise RuntimeError("no backend")
        self.store[(service, account)] = password


def _install(monkeypatch, keyring_module: ModuleType | None) -> None:
    if keyring_module is None:
        # Simulate "keyring not installed": remove it from sys.modules and
        # make the import inside client fail.
        monkeypatch.setitem(sys.modules, "keyring", None)
    else:
        monkeypatch.setitem(sys.modules, "keyring", keyring_module)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_keyring_key_used_when_no_env_var(monkeypatch):
    fake = _FakeKeyring({(client.KEYRING_SERVICE, "groq"): "sk-from-keyring"})
    _install(monkeypatch, fake)
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    assert client.resolve_api_key() == "sk-from-keyring"


def test_env_var_beats_keyring(monkeypatch):
    fake = _FakeKeyring({(client.KEYRING_SERVICE, "groq"): "sk-from-keyring"})
    _install(monkeypatch, fake)
    monkeypatch.setenv(client.GROQ_API_KEY_ENV, "sk-from-env")
    assert client.resolve_api_key() == "sk-from-env"


def test_openrouter_key_resolved_from_keyring(monkeypatch):
    fake = _FakeKeyring({(client.KEYRING_SERVICE, "openrouter"): "or-key"})
    _install(monkeypatch, fake)
    monkeypatch.delenv(client.OPENROUTER_API_KEY_ENV, raising=False)
    assert client.resolve_agent_api_key() == "or-key"


def test_missing_keyring_module_degrades(monkeypatch):
    _install(monkeypatch, None)
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    # Must not raise; returns whatever .env resolution finds (None here).
    assert client.resolve_api_key() is None


def test_failing_backend_degrades(monkeypatch):
    _install(monkeypatch, _FakeKeyring(fail=True))
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    assert client.resolve_api_key() is None


# ---------------------------------------------------------------------------
# Storing keys (setup flow entry point)
# ---------------------------------------------------------------------------


def test_store_api_key_saves_to_keyring(monkeypatch):
    fake = _FakeKeyring()
    _install(monkeypatch, fake)
    assert client.store_api_key("groq", "gsk_new") is True
    assert fake.set_calls == [(client.KEYRING_SERVICE, "groq", "gsk_new")]
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    assert client.resolve_api_key() == "gsk_new"


def test_store_api_key_unknown_provider_rejected():
    import pytest

    with pytest.raises(ValueError):
        client.store_api_key("anthropic", "sk-x")


def test_store_api_key_empty_key_rejected():
    import pytest

    with pytest.raises(ValueError):
        client.store_api_key("groq", "  ")


def test_store_api_key_reports_failure_without_fallback_file(monkeypatch, tmp_path):
    _install(monkeypatch, _FakeKeyring(fail=True))
    assert client.store_api_key("groq", "gsk_x") is False
    # Nothing may have been written anywhere as a plaintext fallback.
    assert not (tmp_path / ".env").exists()
    assert client.resolve_api_key() is None
