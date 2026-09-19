"""Tests for first-run API key setup (backend.llm.key_setup).

Contract under test:
- validation is a real minimal request and fails closed (an
  unverifiable key is never stored);
- the key reaches the keyring ONLY after successful validation;
- provider entries are separate (groq vs openrouter) under the
  ``codelith`` service name;
- startup check prompts only for missing providers and never blocks
  non-interactive sessions;
- no key material is ever written to a file or log.
"""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

import backend.llm.client as client
import backend.llm.key_setup as ks
from backend.llm.key_setup import (
    PROVIDERS,
    SETUP_ORDER,
    collect_and_store_key,
    ensure_keys_at_startup,
    run_setup,
    validate_api_key,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """No env vars, no .env files — resolution hits keyring only."""
    monkeypatch.delenv(client.GROQ_API_KEY_ENV, raising=False)
    monkeypatch.delenv(client.OPENROUTER_API_KEY_ENV, raising=False)
    monkeypatch.setattr(client, "ENV_FILES", (tmp_path / ".env",))


class _FakeKeyring(ModuleType):
    def __init__(self, fail: bool = False):
        super().__init__("keyring")
        self.fail = fail
        self.store: dict[tuple[str, str], str] = {}
        self.set_calls: list[tuple[str, str, str]] = []

    def get_password(self, service, account):
        return self.store.get((service, account))

    def set_password(self, service, account, password):
        self.set_calls.append((service, account, password))
        if self.fail:
            raise RuntimeError("no backend")
        self.store[(service, account)] = password


@pytest.fixture
def fake_keyring(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    return fake


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def read(self, n: int) -> bytes:
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# Validation: fail closed, never store on failure
# ---------------------------------------------------------------------------


def test_validation_accepts_200(monkeypatch):
    monkeypatch.setattr(ks, "urlopen", lambda req, timeout: _FakeResponse(200))
    ok, msg = validate_api_key(PROVIDERS["groq"], "gsk_good")
    assert ok is True


def test_validation_rejects_401(monkeypatch):
    captured = {}

    def _raise(req, timeout):
        captured["auth"] = req.headers.get("Authorization")
        raise ks.HTTPError(req.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(ks, "urlopen", _raise)
    ok, msg = validate_api_key(PROVIDERS["groq"], "gsk_bad")
    assert ok is False
    assert "rejected" in msg.lower()
    assert captured["auth"] == "Bearer gsk_bad"  # key used for the check


def test_validation_sends_real_user_agent(monkeypatch):
    """Regression: Python-urllib's default UA is banned by Groq's
    Cloudflare (error code 1010, HTTP 403), which used to be misreported
    as an invalid key."""
    captured = {}

    def _ok(req, timeout):
        captured["ua"] = req.headers.get("User-agent") or req.headers.get("User-Agent")
        return _FakeResponse(200)

    monkeypatch.setattr(ks, "urlopen", _ok)
    validate_api_key(PROVIDERS["groq"], "gsk_x")
    assert captured["ua"] and "Python-urllib" not in captured["ua"]


def test_cloudflare_1010_is_not_reported_as_bad_key(monkeypatch):
    """A 403 with a Cloudflare error body must read as 'blocked', not
    'invalid key' — the key was never checked."""
    class _CFError(ks.HTTPError):
        def __init__(self):
            super().__init__("https://api.groq.com/openai/v1/models", 403, "Forbidden", None, None)

        def read(self, n=-1):
            return b"error code: 1010"

    monkeypatch.setattr(ks, "urlopen", lambda req, timeout: (_ for _ in ()).throw(_CFError()))
    ok, msg = validate_api_key(PROVIDERS["groq"], "gsk_x")
    assert ok is False
    assert "firewall" in msg.lower()
    assert "invalid" not in msg.lower() and "revoked" not in msg.lower()


def test_validation_rejects_network_failure_fail_closed(monkeypatch):
    monkeypatch.setattr(ks, "urlopen", lambda req, timeout: (_ for _ in ()).throw(ks.URLError("refused")))
    ok, msg = validate_api_key(PROVIDERS["groq"], "gsk_x")
    assert ok is False
    assert "could not reach" in msg.lower()


def test_providers_use_separate_keyring_accounts():
    assert SETUP_ORDER == ("groq", "openrouter")
    assert len({p.name for p in PROVIDERS.values()}) == 2
    assert {p.name for p in PROVIDERS.values()} == set(client.KEYRING_ACCOUNTS.values())
    assert all(p.key_page.startswith("https://") for p in PROVIDERS.values())


# ---------------------------------------------------------------------------
# collect_and_store_key: store only after validation success
# ---------------------------------------------------------------------------


def _urlopen_ok(monkeypatch):
    monkeypatch.setattr(ks, "urlopen", lambda req, timeout: _FakeResponse(200))


def test_valid_key_is_stored(fake_keyring, monkeypatch):
    _urlopen_ok(monkeypatch)
    assert collect_and_store_key(PROVIDERS["groq"], prompt_func=lambda _: "gsk_real") is True
    assert fake_keyring.set_calls == [(client.KEYRING_SERVICE, "groq", "gsk_real")]


def test_invalid_key_is_never_stored(fake_keyring, monkeypatch):
    monkeypatch.setattr(
        ks, "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(ks.HTTPError("u", 401, "no", None, None)),
    )
    # First answer invalid, second blank cancels the re-prompt loop.
    answers = iter(["gsk_wrong", ""])
    assert collect_and_store_key(PROVIDERS["groq"], prompt_func=lambda _: next(answers)) is False
    assert fake_keyring.set_calls == []


def test_store_failure_after_validation_is_reported(fake_keyring, monkeypatch):
    _urlopen_ok(monkeypatch)
    fake_keyring.fail = True
    assert collect_and_store_key(PROVIDERS["openrouter"], prompt_func=lambda _: "sk-or-x") is False
    # Nothing may fall back to a plaintext file.
    assert client.resolve_agent_api_key() is None


def test_blank_input_cancels(fake_keyring, monkeypatch):
    _urlopen_ok(monkeypatch)
    assert collect_and_store_key(PROVIDERS["groq"], prompt_func=lambda _: "  ") is False
    assert fake_keyring.set_calls == []


# ---------------------------------------------------------------------------
# Startup gate
# ---------------------------------------------------------------------------


def test_startup_quiet_when_all_keys_resolve(fake_keyring, monkeypatch, capsys):
    monkeypatch.setenv(client.GROQ_API_KEY_ENV, "env-g")
    monkeypatch.setenv(client.OPENROUTER_API_KEY_ENV, "env-o")
    ensure_keys_at_startup(interactive=False)
    assert capsys.readouterr().err == ""
    assert capsys.readouterr().out == ""


def test_startup_noninteractive_only_hints(fake_keyring, monkeypatch, capsys):
    ensure_keys_at_startup(interactive=False)
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "codelith setup" in out
    assert "Paste" not in out  # never prompts


def test_startup_interactive_prompts_only_missing(fake_keyring, monkeypatch, capsys):
    monkeypatch.setenv(client.GROQ_API_KEY_ENV, "env-g")
    monkeypatch.setattr(ks, "urlopen", lambda req, timeout: _FakeResponse(200))
    asked = []

    def _prompt(text):
        asked.append(text)
        return "sk-or-from-setup"

    ensure_keys_at_startup(interactive=True, prompt_func=_prompt)
    assert len(asked) == 1
    assert "OpenRouter" in asked[0]
    assert fake_keyring.set_calls == [(client.KEYRING_SERVICE, "openrouter", "sk-or-from-setup")]


# ---------------------------------------------------------------------------
# run_setup exit codes
# ---------------------------------------------------------------------------


def test_run_setup_success_exit_code(fake_keyring, monkeypatch):
    _urlopen_ok(monkeypatch)
    assert run_setup(prompt_func=lambda _: "gsk_ok") == 0


def test_run_setup_failure_exit_code(fake_keyring, monkeypatch):
    monkeypatch.setattr(
        ks, "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(ks.HTTPError("u", 401, "no", None, None)),
    )
    assert run_setup("groq", prompt_func=lambda _: "") == 1  # blank cancels → failure


# ---------------------------------------------------------------------------
# No plaintext leakage
# ---------------------------------------------------------------------------


def test_no_key_material_in_source_or_files(fake_keyring, monkeypatch, tmp_path):
    _urlopen_ok(monkeypatch)
    collect_and_store_key(PROVIDERS["groq"], prompt_func=lambda _: "gsk_secret_material")
    saved = fake_keyring.store[(client.KEYRING_SERVICE, "groq")]
    assert saved == "gsk_secret_material"  # only in the credential store
    # The temp .env pointed at by ENV_FILES was never created.
    assert not (tmp_path / ".env").exists()
