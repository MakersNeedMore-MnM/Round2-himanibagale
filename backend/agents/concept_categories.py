"""Category taxonomy for detected concepts.

Every concept detected — registry or LLM — must carry one of six fixed
categories so the dashboard can group, filter, and route diagrams
by category:

- ``algorithm``  — loops, sorting, searching, recursion, big-O reasoning
- ``structure``  — classes, interfaces, inheritance, encapsulation, OOP
- ``api``        — calls into a defined interface: fetch, DOM, SDKs, hooks
- ``data_model`` — how data is shaped/moved: schemas, interfaces, JSON
  payloads, ORMs, validation
- ``decisions``  — architecture and integration choices made in THIS
  codebase: which service/library/tool was picked for a job (Supabase
  for auth, Stripe for billing), and how features are wired together
  (who owns what, which module reaches which).  Named ``decisions``,
  it is distinct from the singular ``decision`` field on a concept,
  which records the rationale on ANY category.
- ``abstract``   — cross-cutting ideas that aren't one of the above:
  error handling, module systems, async, design patterns

``DEFAULT_CATEGORY`` exists only for the legacy "General" alias mapping;
detections are never silently default-filled — the guard in
``concept_detector`` retries once and then rejects concepts whose
category cannot be reconciled with this taxonomy.
"""

from __future__ import annotations

CONCEPT_CATEGORIES: tuple[str, ...] = (
    "algorithm",
    "structure",
    "api",
    "data_model",
    "decisions",
    "abstract",
)

DEFAULT_CATEGORY = "abstract"

# Free-text category labels that clearly mean one of the taxonomy values.
# Used by the guard's tolerant normalization before declaring a response
# invalid and retrying.
_CATEGORY_ALIASES: dict[str, str] = {
    "algorithms": "algorithm",
    "loop": "algorithm",
    "loops": "algorithm",
    "control flow": "algorithm",
    "control-flow": "algorithm",
    "functional programming": "algorithm",
    "recursion": "algorithm",
    "oop": "structure",
    "object-oriented programming": "structure",
    "python oop": "structure",
    "typescript": "structure",
    "class": "structure",
    "classes": "structure",
    "interface": "structure",
    "interfaces": "structure",
    "api": "api",
    "apis": "api",
    "networking": "api",
    "dom / browser api": "api",
    "dom/browser api": "api",
    "browser api": "api",
    "react hook": "api",
    "react hooks": "api",
    "sdk": "api",
    "data model": "data_model",
    "data_model": "data_model",
    "data modeling": "data_model",
    "schema": "data_model",
    "schema/shape": "data_model",
    "data shape": "data_model",
    "type system": "data_model",
    "types": "data_model",
    "type": "data_model",
    "decision": "decisions",
    "decisions": "decisions",
    "design decision": "decisions",
    "design decisions": "decisions",
    "architecture": "decisions",
    "architectural decision": "decisions",
    "architectural decisions": "decisions",
    "system design": "decisions",
    "tech stack": "decisions",
    "technology choice": "decisions",
    "tool choice": "decisions",
    "tooling": "decisions",
    "integration": "decisions",
    "integrations": "decisions",
    "third-party integration": "decisions",
    "third party service": "decisions",
    "infrastructure": "decisions",
    "wiring": "decisions",
    "abstract": "abstract",
    "abstraction": "abstract",
    "general": DEFAULT_CATEGORY,
    "other": DEFAULT_CATEGORY,
    "misc": DEFAULT_CATEGORY,
    "pattern": "abstract",
    "patterns": "abstract",
    "python pattern": "abstract",
    "asynchronous pattern": "abstract",
    "async": "abstract",
    "error handling": "abstract",
    "module system": "abstract",
    "modules": "abstract",
}


def normalize_category(value: object) -> str | None:
    """Map a raw LLM/registry category string onto the taxonomy.

    Returns the canonical taxonomy slug, or ``None`` when the value is
    missing/empty — callers decide whether to retry or reject (never
    silently default-fill).
    """
    if not isinstance(value, str):
        return None
    key = " ".join(value.strip().lower().replace("-", "_").split())
    if not key:
        return None
    key = key.replace("__", "_")
    if key in CONCEPT_CATEGORIES:
        return key
    return _CATEGORY_ALIASES.get(key)


def is_valid_category(value: object) -> bool:
    """True when *value* is exactly a canonical taxonomy slug."""
    return value in CONCEPT_CATEGORIES
