"""First-run API key setup via the OS credential store.

Reuses the storage layer in :mod:`backend.llm.client` (service name
``codelith``, one keyring account per provider) and adds what the CLI
needs:

- **Validation** — a minimal authenticated request to the provider is
  made BEFORE the key is stored; an invalid key is never saved.
- **Interactive setup** — terminal prompt naming the provider, with the
  provider's official key page, via :func:`collect_and_store_key`.
- **Startup check** — :func:`ensure_keys_at_startup` runs at the start
  of ``codelith`` (after subcommand dispatch, before the daemon) and
  prompts only for providers whose key cannot be resolved from any
  layer (env var → keyring → .env).  Non-interactive sessions (scripts,
  CI) are never blocked: they get a hint instead of a prompt.

No key is ever hardcoded, written to a file, or logged.  If the OS
credential store is unavailable, setup fails loudly rather than
leaking the key into plaintext.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.llm.client import (
    KEYRING_ACCOUNTS,
    OPENROUTER_API_KEY_ENV,
    GROQ_API_KEY_ENV,
    resolve_agent_api_key,
    resolve_api_key,
    store_api_key,
)

VALIDATION_TIMEOUT = 15  # seconds


@dataclass(frozen=True)
class Provider:
    """One API provider's setup metadata and key-page pointer."""

    name: str  # keyring account name, matches KEYRING_ACCOUNTS values
    display: str
    key_page: str
    env_var: str
    validation_url: str
    resolver: object  # () -> Optional[str]


PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        name="groq",
        display="Groq",
        key_page="https://console.groq.com/keys",
        env_var=GROQ_API_KEY_ENV,
        validation_url="https://api.groq.com/openai/v1/models",
        resolver=resolve_api_key,
    ),
    "openrouter": Provider(
        name="openrouter",
        display="OpenRouter",
        key_page="https://openrouter.ai/keys",
        env_var=OPENROUTER_API_KEY_ENV,
        validation_url="https://openrouter.ai/api/v1/key",
        resolver=resolve_agent_api_key,
    ),
}

SETUP_ORDER = ("groq", "openrouter")


def validate_api_key(provider: Provider, api_key: str) -> tuple[bool, str]:
    """Make one minimal authenticated request to *provider*.

    Returns ``(ok, message)``.  Fail-closed: any ambiguity (network
    down, unknown status) counts as invalid so an unverifiable key is
    never stored.
    """
    request = Request(
        provider.validation_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            # Cloudflare (Groq's edge) blocks Python-urllib's default
            # signature with "error code: 1010" before the key is ever
            # checked — a 403 that looks exactly like a bad key.  A
            # proper User-Agent gets through; the OpenAI SDK does the
            # same, which is why the agents never saw this.
            "User-Agent": "codelith/0.1 (api-key validation)",
            # OpenRouter prefers identifying headers; harmless for Groq.
            "HTTP-Referer": "https://github.com/codelith",
            "X-Title": "CodeLith",
        },
    )
    try:
        with urlopen(request, timeout=VALIDATION_TIMEOUT) as response:
            response.read(64)
            if 200 <= response.status < 300:
                return True, f"{provider.display} key validated."
            return False, f"{provider.display} returned HTTP {response.status}."
    except HTTPError as exc:
        try:
            body = exc.read(200).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - body is best-effort context
            body = ""
        if exc.code == 401:
            return False, f"{provider.display} rejected the key (invalid or revoked)."
        if exc.code == 403 and "error code:" in body:
            return False, (
                f"{provider.display}'s firewall blocked the check before the "
                "key could be verified — try again in a moment."
            )
        if exc.code == 403:
            return False, f"{provider.display} rejected the key (forbidden)."
        return False, f"{provider.display} returned HTTP {exc.code} — try again later."
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"Could not reach {provider.display} to validate the key ({reason})."


def collect_and_store_key(provider: Provider, prompt_func=None) -> bool:
    """Interactively obtain, validate, and store one provider's key.

    Prompts name the provider and point at its official key page.  The
    key is stored ONLY after successful validation; validation failure
    re-prompts (blank input cancels).  Returns True when a valid key is
    in the OS credential store.

    ``prompt_func`` is injectable for tests; it receives the prompt
    text and returns the entered key.
    """
    if prompt_func is None:
        from getpass import getpass

        prompt_func = getpass

    print(f"\nNo {provider.display} API key found.")
    print(f"{provider.display} powers "
          + ("teaching, explanations, and grading."
             if provider.name == "groq"
             else "the coding and debugging agents.")
          + f" Create a key at {provider.key_page}")

    while True:
        try:
            key = prompt_func(f"Paste your {provider.display} API key (Enter to cancel): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        key = (key or "").strip()
        if not key:
            print(f"Setup skipped — {provider.display} features will be unavailable.")
            return False

        ok, message = validate_api_key(provider, key)
        if not ok:
            print(f"  ✗ {message} The key was NOT saved — check it and try again.")
            continue

        if store_api_key(provider.name, key):
            print(f"  ✓ {message} Saved to your OS credential store.")
            return True
        print(
            "  ✗ Key validated, but the OS credential store is unavailable, "
            "so it was NOT saved. Install/unlock your system's keyring backend "
            "(on Linux: gnome-keyring or kwallet) and run `codelith setup`."
        )
        return False


def _missing_providers() -> list[Provider]:
    """Providers whose key cannot be resolved from any existing layer."""
    missing = []
    for name in SETUP_ORDER:
        provider = PROVIDERS[name]
        try:
            if not provider.resolver():
                missing.append(provider)
        except Exception:  # noqa: BLE001 - resolution must never crash startup
            missing.append(provider)
    return missing


def ensure_keys_at_startup(stream=None, prompt_func=None, interactive: bool | None = None) -> None:
    """Startup gate: prompt only for providers with no resolvable key.

    Never raises and never blocks non-interactive sessions — scripts and
    CI get a one-line hint pointing at ``codelith setup`` instead.
    """
    if stream is None:
        stream = sys.stdout
    if interactive is None:
        interactive = bool(sys.stdin and sys.stdin.isatty())

    missing = _missing_providers()
    if not missing:
        return

    names = " and ".join(p.display for p in missing)
    if not interactive:
        print(
            f"[codelith] {names} API key(s) not configured — "
            "run `codelith setup` to add them interactively.",
            file=stream,
        )
        return

    print(f"[codelith] First-run setup: a {names} API key is needed.")
    for provider in missing:
        collect_and_store_key(provider, prompt_func=prompt_func)


def run_setup(provider_name: str | None = None, prompt_func=None) -> int:
    """Explicit ``codelith setup [provider]`` entry point.

    Validates and (re)stores keys even when one already exists — the
    natural fix for a revoked or mistyped key.  Returns a process exit
    code.
    """
    targets = (
        [PROVIDERS[provider_name]]
        if provider_name
        else [PROVIDERS[name] for name in SETUP_ORDER]
    )
    failed = False
    for provider in targets:
        if not collect_and_store_key(provider, prompt_func=prompt_func):
            failed = True
    return 1 if failed else 0


# Sanity: the storage layer's accounts and this registry must not drift.
assert set(PROVIDERS) == set(KEYRING_ACCOUNTS.values()), (
    "key_setup providers must match backend.llm.client keyring accounts"
)
