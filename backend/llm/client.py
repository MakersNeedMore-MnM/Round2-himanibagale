"""LLM chat clients for the CodeLith daemon.

Two independent providers are used:

- **Groq** — the teaching-side models (teacher agent, assessment grading,
  concept detection, dashboard questions).  Key: ``GROQ_API_KEY``.
- **OpenRouter** — the workhorse coding models (coding agent, debug
  agent).  Key: ``OPENROUTER_API_KEY``.  The model is chosen with
  ``CODELITH_AGENT_MODEL`` (default: ``qwen/qwen3-coder-next``, a cheap
  code-specialised model with a 262k context and native tool calling).

Both providers are OpenAI-compatible, so a single ``openai`` SDK client
is used with a different ``base_url`` per provider.

API keys are resolved from, in order:

1. the environment variable (``GROQ_API_KEY`` / ``OPENROUTER_API_KEY``),
2. a ``.env`` file in the repository root,
3. a ``.env`` file in the daemon state directory (``~/.codelith/``).

Files are re-read on every request, so adding a key to a ``.env`` file
takes effect without restarting the daemon. Usage::

    from backend.llm.client import generate_reply

    reply = generate_reply("What is a closure?")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from backend.llm.config import get_model

GROQ_API_KEY_ENV = "GROQ_API_KEY"
# Kept for backwards compatibility with existing imports; teaching-side
# model selection now goes through backend.llm.config.get_model(role).
DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_COMPLETION_TOKENS = 4096
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Coding/debug agent workhorse model.  Qwen3-Coder-Next: code-specialised,
# native tool calling, 262k context, generous output budget.  Override with
# the CODELITH_AGENT_MODEL env var, e.g. "anthropic/claude-sonnet-4.5" for
# the strongest agentic coder (paid) or any OpenRouter "...:free" model.
DEFAULT_AGENT_MODEL = "qwen/qwen3-coder-next"
AGENT_MODEL_ENV = "CODELITH_AGENT_MODEL"
# Per-round completion budget for the coding/debug agents.  OpenRouter
# models (unlike Groq) expose this via the ``max_tokens`` parameter.
AGENT_MAX_TOKENS = 8192

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (
    REPO_ROOT / ".env",
    Path.home() / ".codelith" / ".env",
)

# OS credential store (Windows Credential Manager, macOS Keychain,
# Secret Service).  Keys land here when saved through `codelith setup`;
# env vars and .env files keep working unchanged for users who prefer
# them.  keyring is an optional dependency: absence or an unlocked/
# missing backend degrades gracefully to the .env path below.
KEYRING_SERVICE = "codelith"
KEYRING_ACCOUNTS = {
    GROQ_API_KEY_ENV: "groq",
    OPENROUTER_API_KEY_ENV: "openrouter",
}


def _keyring_get(env_name: str) -> Optional[str]:
    """Return a key from the OS credential store, or None.

    Never raises: any keyring failure (module missing, no backend,
    locked keychain) just means "not stored here" and resolution falls
    through to the env-var/.env layers.
    """
    try:
        import keyring
    except ImportError:
        return None
    try:
        secret = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNTS[env_name])
    except Exception:  # noqa: BLE001 - keyring backends raise many shapes
        return None
    return secret.strip() if secret and secret.strip() else None


def _keyring_set(env_name: str, api_key: str) -> bool:
    """Store a key in the OS credential store.  Returns True on success."""
    try:
        import keyring
    except ImportError:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNTS[env_name], api_key.strip())
        return True
    except Exception:  # noqa: BLE001 - no backend / locked store / ACL error
        return False


def store_api_key(provider: str, api_key: str) -> bool:
    """Securely persist *provider*'s API key (``"groq"``/``"openrouter"``).

    Public entry point for the first-run setup flow.  Returns False when
    no usable keyring backend exists — the caller should then fall back
    to advising a .env file instead of storing the key in plaintext.
    """
    env_name = {v: k for k, v in KEYRING_ACCOUNTS.items()}.get(provider)
    if not env_name:
        raise ValueError(f"unknown provider: {provider!r} (known: {', '.join(sorted(KEYRING_ACCOUNTS.values()))})")
    if not api_key.strip():
        raise ValueError("API key must not be empty")
    return _keyring_set(env_name, api_key)

SYSTEM_PROMPT = (
    "You are CodeLith, an AI mentor that blends coding assistance with "
    "adaptive teaching. The user is learning to code. Teach at their level: "
    "explain concepts clearly, use concrete examples, and guide them toward "
    "solutions instead of just giving the answer. Keep answers focused and "
    "conversational, and ask a question now and then to check understanding."
)

GRADING_SYSTEM_PROMPT = (
    "You are CodeLith, an AI mentor grading a learner's answer to a concept "
    "question. Judge whether the answer shows real understanding of the "
    "concept. Be fair: accept correct answers even if they are worded "
    "differently from a textbook, but reject answers that are wrong or "
    "miss the point. Respond ONLY with a JSON object of the form "
    '{"correct": true or false, "feedback": "..."}. Keep feedback to '
    "1-2 sentences: if the answer is wrong, name the key idea the learner "
    "missed without giving the full answer away."
)


def _load_dotenv(path: Path) -> None:
    """Load ``KEY=VALUE`` pairs from ``path`` without overriding existing vars."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_api_key() -> Optional[str]:
    """Return the Groq API key, or None if it is not configured anywhere.

    Resolution order: env var → OS keyring → .env files.  Existing
    setups (env var or .env) keep working unchanged; the keyring layer
    is only consulted when those are empty.
    """
    if os.environ.get(GROQ_API_KEY_ENV):
        return os.environ[GROQ_API_KEY_ENV].strip()
    stored = _keyring_get(GROQ_API_KEY_ENV)
    if stored:
        return stored
    for path in ENV_FILES:
        _load_dotenv(path)
        key = os.environ.get(GROQ_API_KEY_ENV)
        if key:
            return key.strip()
    return None


def resolve_agent_api_key() -> Optional[str]:
    """Return the OpenRouter API key, or None if it is not configured anywhere.

    Same resolution order as :func:`resolve_api_key`.
    """
    if os.environ.get(OPENROUTER_API_KEY_ENV):
        return os.environ[OPENROUTER_API_KEY_ENV].strip()
    stored = _keyring_get(OPENROUTER_API_KEY_ENV)
    if stored:
        return stored
    for path in ENV_FILES:
        _load_dotenv(path)
        key = os.environ.get(OPENROUTER_API_KEY_ENV)
        if key:
            return key.strip()
    return None


def resolve_agent_model() -> str:
    """Return the coding-agent model slug (CODELITH_AGENT_MODEL or default)."""
    return (os.environ.get(AGENT_MODEL_ENV) or DEFAULT_AGENT_MODEL).strip()


def get_client() -> OpenAI:
    """Return an OpenAI-compatible client pointed at Groq."""
    api_key = resolve_api_key()
    if not api_key:
        raise ValueError(
            "No Groq API key found. Set GROQ_API_KEY "
            "environment variable, or add it to a .env file."
        )
    return OpenAI(
        base_url=GROQ_BASE_URL,
        api_key=api_key,
    )


def get_agent_client() -> OpenAI:
    """Return an OpenAI-compatible client pointed at OpenRouter."""
    api_key = resolve_agent_api_key()
    if not api_key:
        raise ValueError(
            "No OpenRouter API key found. Set OPENROUTER_API_KEY "
            "environment variable, or add it to a .env file."
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )


def generate_reply(
    user_message: str,
    model: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> str:
    """Ask Groq for a reply to ``user_message`` using the CodeLith persona.

    ``model`` defaults to the resolved *teaching* role model (env var >
    ``config.toml`` > built-in default) when not given explicitly.

    ``history`` is an optional list of prior turns (``{"role", "content"}``
    dicts, oldest first) so follow-up questions keep their context.

    Never raises: a missing API key and API/network failures are converted
    into a readable message so the CLI keeps working without a key.
    """
    if model is None:
        model = get_model("teaching")
    api_key = resolve_api_key()
    if not api_key:
        return (
            "I need a Groq API key to think. Set the GROQ_API_KEY "
            "environment variable, or add it to a .env file in the project "
            "root (see the README), then try again."
        )
    try:
        client = get_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history or []:
            role = entry.get("role")
            content = (entry.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=MAX_COMPLETION_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001 - surface any API/network failure
        return f"(I couldn't reach Groq: {exc})"
    return completion.choices[0].message.content or ""


def grade_answer(
    question: str,
    answer: str,
    concept_name: str,
    concept_category: str = "",
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Grade a learner's answer to a concept question via the LLM.

    ``model`` defaults to the resolved *grading* role model (env var >
    ``config.toml`` > built-in default) when not given explicitly.

    Returns ``{"correct": bool, "feedback": str}``.  Never raises: any
    failure (missing key, API error, unparseable output) is converted into
    a conservative result — the answer is graded as not-correct with a
    readable explanation, so a broken grader can never inflate progress.
    """
    if model is None:
        model = get_model("grading")
    api_key = resolve_api_key()
    if not api_key:
        return {
            "correct": False,
            "feedback": (
                "(Grading needs a Groq API key — set GROQ_API_KEY or add it "
                "to a .env file, then submit again.)"
            ),
        }

    category_note = f" (category: {concept_category})" if concept_category else ""
    user_prompt = (
        f"Concept: {concept_name}{category_note}\n"
        f"Question: {question}\n\n"
        f"Learner's answer: {answer}\n\n"
        "Grade the answer. Respond ONLY with the JSON object."
    )
    try:
        client = get_client()
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": GRADING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=512,
        )
        raw = (completion.choices[0].message.content or "").strip()
        # Tolerate code fences or prose around the JSON object.
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"no JSON object in grader output: {raw[:200]}")
        parsed = json.loads(raw[start : end + 1])
        correct = bool(parsed.get("correct", False))
        feedback = str(parsed.get("feedback", "")).strip()
        return {"correct": correct, "feedback": feedback or ("Correct!" if correct else "Not quite — try again.")}
    except Exception as exc:  # noqa: BLE001 - conservative failure
        return {
            "correct": False,
            "feedback": f"(Grading failed: {exc}. Your answer was not recorded as correct — please submit again.)",
        }
