"""``codelith config`` — inspect and customize model roles.

This command group never starts the daemon and never touches the
network: ``show``, ``set``, and ``unset`` only read/write
``~/.codelith/config.toml`` and print current resolution.  It exists
purely for users who *want* to change models; running plain CodeLith
never creates the config file.

Usage::

    codelith config                 # show every role + resolved model
    codelith config show            # same
    codelith config set <role> <model-slug>
    codelith config unset <role>    # fall back to env var / default

The exit code is 2 for usage/validation errors so shell scripts can
distinguish them from plain "nothing to do" output.
"""

from __future__ import annotations

import argparse
import sys

from backend.llm import config as llm_config
from backend.llm.config import MODEL_ROLES, get_model, set_model, unset_model


def _print_show() -> None:
    """Print every role, its override source, and the resolved model."""
    import os

    path = llm_config.config_path()
    exists = path.exists()
    print(f"Config file: {path}" + ("" if exists else " (not created — using built-in defaults)"))
    print()
    header = f"{'Role':<12} {'Source':<10} Model"
    print(header)
    print("-" * len(header))
    for role in sorted(MODEL_ROLES):
        env_name = MODEL_ROLES[role]["env"]
        if (os.environ.get(env_name) or "").strip():
            source = f"env:{env_name}"
        elif exists and get_model(role) != MODEL_ROLES[role]["default"] and not (
            os.environ.get(env_name) or ""
        ).strip():
            # get_model returned something different from the default and
            # no env var is set, so it must have come from the file.
            source = "config.toml"
        else:
            source = "default"
        print(f"{role:<12} {source:<10} {get_model(role)}")
    print()
    print("Change a model:  codelith config set <role> <provider/model>")
    print("Reset a role:    codelith config unset <role>")
    print(f"Valid roles:     {', '.join(sorted(MODEL_ROLES))}")


def _cmd_show(_args: argparse.Namespace) -> int:
    _print_show()
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    role, slug = args.role, args.slug
    if role not in MODEL_ROLES:
        print(
            f"Unknown role: {role!r}. Valid roles: {', '.join(sorted(MODEL_ROLES))}",
            file=sys.stderr,
        )
        return 2
    try:
        set_model(role, slug)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"{role} = {slug}")
    print(f"Saved to {llm_config.config_path()}")
    return 0


def _cmd_unset(args: argparse.Namespace) -> int:
    role = args.role
    if role not in MODEL_ROLES:
        print(
            f"Unknown role: {role!r}. Valid roles: {', '.join(sorted(MODEL_ROLES))}",
            file=sys.stderr,
        )
        return 2
    if unset_model(role):
        print(f"{role} reset (now follows env var / built-in default).")
    else:
        print(f"{role} has no override in {llm_config.config_path()}; nothing to unset.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the ``codelith config`` argument parser (with subcommands)."""
    parser = argparse.ArgumentParser(
        prog="codelith config",
        description="Inspect or customize per-role model choices. "
        "Never starts the daemon; never creates config.toml unless you set a model.",
    )
    sub = parser.add_subparsers(dest="config_command")

    sub.add_parser("show", help="show every role and its resolved model")

    p_set = sub.add_parser("set", help="set the model for one role")
    p_set.add_argument("role", help=f"model role ({', '.join(sorted(MODEL_ROLES))})")
    p_set.add_argument("slug", help='model slug, e.g. "qwen/qwen3-coder-next" or "openai/gpt-oss-120b"')

    p_unset = sub.add_parser("unset", help="remove a role's override")
    p_unset.add_argument("role", help="model role to reset")

    # `codelith config` with no subcommand → show.
    parser.set_defaults(config_command="show", handler=_cmd_show)
    sub.choices["show"].set_defaults(handler=_cmd_show)  # type: ignore[index]
    sub.choices["set"].set_defaults(handler=_cmd_set)  # type: ignore[index]
    sub.choices["unset"].set_defaults(handler=_cmd_unset)  # type: ignore[index]
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``codelith config ...``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:  # pragma: no cover - set_defaults makes this unreachable
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
