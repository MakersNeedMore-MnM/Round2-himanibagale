"""Model-role resolution for CodeLith.

CodeLith's AI work is split into logical **roles** (coding, debugging,
teaching, ...).  Each role maps to an LLM model slug; every role
resolves independently through the same three-layer chain:

1. the role's environment variable (``CODELITH_MODEL_CODING`` ...),
2. ``~/.codelith/config.toml`` under ``[models]``,
3. the built-in default for that role.

The first layer that is set wins, so a shell env var can override the
config file for one command (CI, scripts), while the config file is the
durable per-machine override.

**No file is ever created automatically.**  A user who never customizes
models sees zero config behavior: all roles resolve to the built-in
defaults and nothing appears in ``~/.codelith/``.  ``config.toml`` comes
into existence only when the user runs ``codelith config set`` (or
hand-writes the file).

Roles are logical, not physical: nothing stops two roles from using the
same model, and multiple roles currently share the built-in defaults.

Usage::

    from backend.llm.config import get_model

    model = get_model("grading")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - depends on the interpreter running the tests
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - degraded mode, see below
        tomllib = None  # type: ignore[assignment]

from backend.daemon.state import state_dir

# ---------------------------------------------------------------------------
# Role registry
# ---------------------------------------------------------------------------

#: Every logical model role, with its built-in default and env-var name.
#: Defaults are the models CodeLith ships with today; a role with no
#: override resolves to exactly what it used before this module existed.
MODEL_ROLES: dict[str, dict[str, str]] = {
    "coding": {
        "default": "qwen/qwen3-coder-next",
        "env": "CODELITH_MODEL_CODING",
    },
    "debugging": {
        "default": "qwen/qwen3-coder-next",
        "env": "CODELITH_MODEL_DEBUGGING",
    },
    "teaching": {
        "default": "openai/gpt-oss-120b",
        "env": "CODELITH_MODEL_TEACHING",
    },
    "assessment": {
        "default": "openai/gpt-oss-120b",
        "env": "CODELITH_MODEL_ASSESSMENT",
    },
    "grading": {
        "default": "openai/gpt-oss-120b",
        "env": "CODELITH_MODEL_GRADING",
    },
    "detection": {
        "default": "openai/gpt-oss-120b",
        "env": "CODELITH_MODEL_DETECTION",
    },
}

CONFIG_FILE_NAME = "config.toml"

# mtime cache: the TOML file is parsed at most once per modification.
# Keeps the "edit the file, no daemon restart" behavior of the .env
# loader while avoiding a disk hit + reparse on every LLM call.
_cache: dict[str, object] = {"mtime": None, "models": {}}


def config_path() -> Path:
    """Return the config file path (``~/.codelith/config.toml``)."""
    return state_dir() / CONFIG_FILE_NAME


def _parse_toml(text: str) -> dict:
    """Parse *text* as TOML, or return {} when no parser is available."""
    if tomllib is None:  # pragma: no cover - Python < 3.11 without tomli
        return {}
    return tomllib.loads(text)


def _read_models_table(path: Path) -> dict[str, str]:
    """Return the ``[models]`` table from *path* as ``role -> slug``.

    Returns {} when the file is missing, unreadable, unparsable, or has
    no ``[models]`` table — a broken config file degrades to built-in
    defaults rather than breaking every LLM call.
    """
    try:
        data = _parse_toml(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # missing file / TOML syntax error
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        return {}
    return {
        str(role): str(slug).strip()
        for role, slug in models.items()
        if str(slug).strip()
    }


def _file_models() -> dict[str, str]:
    """Return the parsed ``[models]`` table, re-reading only when the file changed."""
    path = config_path()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        # No file (the common case) — reset the cache so a file created
        # later is picked up instead of being shadowed by a stale table.
        _cache["mtime"] = None
        _cache["models"] = {}
        return {}
    if _cache["mtime"] != mtime:
        _cache["models"] = _read_models_table(path)
        _cache["mtime"] = mtime
    models: dict[str, str] = _cache["models"]  # type: ignore[assignment]
    return models


def get_model(role: str) -> str:
    """Return the model slug for *role*.

    Resolution order: role env var → ``config.toml`` ``[models]`` →
    built-in default.  Unknown roles raise ``KeyError`` — a typo'd role
    is a programming error, not a runtime condition.
    """
    entry = MODEL_ROLES.get(role)
    if entry is None:
        raise KeyError(f"unknown model role: {role!r} (known: {', '.join(sorted(MODEL_ROLES))})")

    env_value = (os.environ.get(entry["env"]) or "").strip()
    if env_value:
        return env_value

    file_value = _file_models().get(role, "").strip()
    if file_value:
        return file_value

    return entry["default"]


# ---------------------------------------------------------------------------
# Explicit writes — the only way config.toml comes into existence
# ---------------------------------------------------------------------------


def set_model(role: str, slug: str) -> None:
    """Persist *role* → *slug* in ``config.toml``, creating the file.

    Preserves any other TOML content conservatively: when the existing
    file parses, the ``[models]`` table is updated in place and the rest
    of the document is re-emitted unchanged.  When it does not parse,
    the write is refused rather than destroying the user's file.

    Unknown roles are rejected — ``codelith config set`` is the only
    writer, and it validates against :data:`MODEL_ROLES` first.
    """
    if role not in MODEL_ROLES:
        raise KeyError(f"unknown model role: {role!r} (known: {', '.join(sorted(MODEL_ROLES))})")
    slug = slug.strip()
    if not slug:
        raise ValueError("model slug must not be empty")

    path = config_path()
    existing_text = ""
    try:
        existing_text = path.read_text(encoding="utf-8")
    except OSError:
        pass  # new file

    if existing_text.strip():
        try:
            data = _parse_toml(existing_text)
        except ValueError as exc:
            raise ValueError(
                f"{path} is not valid TOML ({exc}); fix or remove it before running "
                "`codelith config set`."
            ) from exc
        data.setdefault("models", {})
        data["models"][role] = slug
        body = _dump_toml(data)
    else:
        body = _dump_toml({"models": {role: slug}})

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _cache["mtime"] = None  # force re-read on next resolve


def unset_model(role: str) -> bool:
    """Remove *role* from ``config.toml``.  Returns True if it was present.

    The file itself is kept (other settings may live there); an empty
    ``[models]`` table is left behind rather than deleting the file,
    which keeps hand-edited comments and unrelated sections intact.
    """
    if role not in MODEL_ROLES:
        raise KeyError(f"unknown model role: {role!r} (known: {', '.join(sorted(MODEL_ROLES))})")

    path = config_path()
    try:
        data = _parse_toml(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    models = data.get("models")
    if not isinstance(models, dict) or role not in models:
        return False

    del models[role]
    path.write_text(_dump_toml(data), encoding="utf-8")
    _cache["mtime"] = None
    return True


def _dump_toml(data: dict) -> str:
    """Serialize *data* to a readable TOML string (tables one key deep)."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"[{key}]")
            for sub_key, sub_value in value.items():
                lines.append(f"{sub_key} = {_toml_string(str(sub_value))}")
            lines.append("")
        else:
            lines.append(f"{key} = {_toml_string(str(value))}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _toml_string(value: str) -> str:
    """Quote *value* as a basic TOML string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
