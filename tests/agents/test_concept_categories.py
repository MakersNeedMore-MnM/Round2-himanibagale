"""Category tagging for detected concepts.

Every detected concept — registry-scan or LLM — must carry a ``category``
from the fixed six-value taxonomy (``algorithm``, ``structure``, ``api``,
``data_model``, ``decisions``, ``abstract``).  These tests:

1. Feed one file each for a loop, a class, an API call, and a data model
   and assert the raw detection output carries a *sensible, populated*
   category — never null, never a default fallback.
2. Exercise the guard: an LLM response with a missing or out-of-set
   category must trigger one corrective retry, and concepts still invalid
   after the retry must be rejected (never default-filled).
3. Cover the ``decisions`` category — architecture/integration choices
   (which service was picked, how features are wired) — including the
   free-text wordings a model uses for it.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from backend.agents.concept_categories import (
    CONCEPT_CATEGORIES,
    is_valid_category,
    normalize_category,
)
from backend.agents.concept_detector import (
    CONCEPT_PATTERNS,
    DetectedConcept,
    detect_concepts_from_file,
    detect_concepts_with_llm,
)

# ---------------------------------------------------------------------------
# The four sample files — one per requested kind
# ---------------------------------------------------------------------------


LOOP_FILE = ("loops.py", '''def sum_to_n(n):
    total = 0
    for i in range(n):
        total += i
    return total
''')

CLASS_FILE = ("models.py", '''class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        raise NotImplementedError
''')

API_FILE = ("client.js", '''async function loadUser(id) {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}
''')

DATA_MODEL_FILE = ("user.ts", '''export interface User {
    id: string
    email: string
    displayName: string
}

export type UserRecord = Record<string, User>
''')


def _assert_populated_taxonomy_category(test: unittest.TestCase, concept) -> None:
    """category must exist, be a real string, and be IN the taxonomy."""
    category = getattr(concept, "category", None) or concept.get("category")
    test.assertIsInstance(category, str)
    test.assertTrue(category.strip(), f"empty category on {concept!r}")
    test.assertTrue(
        is_valid_category(category),
        f"category {category!r} outside taxonomy {CONCEPT_CATEGORIES}",
    )


class TestRegistryDetectionTagsCategories(unittest.TestCase):
    """Feeding one file per kind: loop, class, API call, data model."""

    def _detect(self, file_tuple: tuple[str, str]) -> list[DetectedConcept]:
        path, content = file_tuple
        return detect_concepts_from_file(path, content)

    def test_loop_file_gets_algorithm_category(self) -> None:
        detected = self._detect(LOOP_FILE)
        self.assertTrue(detected, "loop file should detect at least one concept")
        for c in detected:
            self.assertEqual(c.category, "algorithm")

    def test_class_file_gets_structure_category(self) -> None:
        detected = self._detect(CLASS_FILE)
        self.assertTrue(detected, "class file should detect at least one concept")
        self.assertIn("Classes / OOP", {c.name for c in detected})
        for c in detected:
            self.assertEqual(c.category, "structure")

    def test_class_file_diagrams_use_class_diagram(self) -> None:
        # Routing contract end-to-end: structure concepts detected from
        # the class file must carry a classDiagram, not a generic one.
        detected = self._detect(CLASS_FILE)
        self.assertTrue(detected)
        for c in detected:
            self.assertEqual(c.category, "structure")
            self.assertTrue(
                c.diagram.startswith("classDiagram"),
                f"{c.name} should use classDiagram, got: {c.diagram[:40]!r}",
            )

    def test_api_file_gets_api_category(self) -> None:
        detected = self._detect(API_FILE)
        self.assertTrue(detected, "API file should detect at least one concept")
        cats = {c.name: c.category for c in detected}
        # The API call itself must be tagged api...
        self.assertEqual(cats.get("Fetch API"), "api")
        # ...while async/await in the same file is sensibly abstract —
        # every concept populated and inside the taxonomy either way.
        for c in detected:
            _assert_populated_taxonomy_category(self, c)
        self.assertEqual(cats.get("Async/Await"), "abstract")

    def test_data_model_file_gets_data_model_category(self) -> None:
        detected = self._detect(DATA_MODEL_FILE)
        self.assertTrue(detected, "data model file should detect at least one concept")
        names = {c.name for c in detected}
        self.assertTrue(
            "TypeScript Interface" in names or "TypeScript Type Alias" in names,
            f"expected interface/type alias detection, got {names}",
        )
        for c in detected:
            self.assertEqual(c.category, "data_model")

    def test_registry_has_no_free_text_categories_left(self) -> None:
        # Every registry entry must now carry a canonical taxonomy value
        # plus its old human-readable label as subcategory.
        for pattern, info in CONCEPT_PATTERNS.items():
            self.assertIn(
                info["category"],
                CONCEPT_CATEGORIES,
                f"registry entry for {pattern!r} has non-taxonomy category {info['category']!r}",
            )
            self.assertTrue(info.get("subcategory"), f"{pattern!r} missing subcategory")


class TestNormalizeCategory(unittest.TestCase):
    def test_canonical_values_pass_through(self) -> None:
        for cat in CONCEPT_CATEGORIES:
            self.assertEqual(normalize_category(cat), cat)

    def test_common_llm_wordings_map_into_taxonomy(self) -> None:
        self.assertEqual(normalize_category("OOP"), "structure")
        self.assertEqual(normalize_category("Networking"), "api")
        self.assertEqual(normalize_category("DOM / Browser API"), "api")
        self.assertEqual(normalize_category("React Hook"), "api")
        self.assertEqual(normalize_category("Control Flow"), "algorithm")
        self.assertEqual(normalize_category("Data Model"), "data_model")
        self.assertEqual(normalize_category("schema/shape"), "data_model")

    def test_decision_wordings_map_into_taxonomy(self) -> None:
        # A model describing an architectural/integration choice rather
        # than a coding technique must land in ``decisions``.
        self.assertEqual(normalize_category("decisions"), "decisions")
        self.assertEqual(normalize_category("Decision"), "decisions")
        self.assertEqual(normalize_category("design decision"), "decisions")
        self.assertEqual(normalize_category("Architecture"), "decisions")
        self.assertEqual(normalize_category("architectural decisions"), "decisions")
        self.assertEqual(normalize_category("integration"), "decisions")
        self.assertEqual(normalize_category("Tech Stack"), "decisions")

    def test_missing_or_empty_is_none_not_default(self) -> None:
        self.assertIsNone(normalize_category(None))
        self.assertIsNone(normalize_category(""))
        self.assertIsNone(normalize_category("   "))
        self.assertIsNone(normalize_category(123))

    def test_unmappable_junk_is_none(self) -> None:
        self.assertIsNone(normalize_category("quantum entanglement"))


class TestLLMDetectionCategoryGuard(unittest.TestCase):
    """The guard: parse → validate → one corrective retry → reject."""

    def _llm_response(self, concepts: list[dict]) -> str:
        return json.dumps(concepts)

    def _patch_client(self, responses: list[str]) -> mock.MagicMock:
        completions = mock.MagicMock()
        side_effects = []
        for resp in responses:
            completion = mock.MagicMock()
            completion.choices[0].message.content = resp
            side_effects.append(completion)
        completions.create.side_effect = side_effects
        client = mock.MagicMock()
        client.chat.completions = completions
        return client

    def test_valid_categories_pass_through(self) -> None:
        response = self._llm_response([
            {"name": "Memoization", "category": "algorithm",
             "description": "Caching computed results.", "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
        ])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=self._patch_client([response])):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].category, "algorithm")

    def test_free_text_category_is_normalized_into_taxonomy(self) -> None:
        response = self._llm_response([
            {"name": "Event Listeners", "category": "DOM / Browser API",
             "description": "Registering callbacks on events.", "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
        ])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=self._patch_client([response])):
            detected = detect_concepts_with_llm("x.js", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].category, "api")

    def test_missing_category_triggers_retry_then_accepts_fixed_value(self) -> None:
        bad = self._llm_response([
            {"name": "Debounce", "description": "Delays invocation until input settles.",
             "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
        ])
        good = json.dumps({"Debounce": {"category": "abstract"}})
        client = self._patch_client([bad, good])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.js", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].category, "abstract")
        self.assertEqual(client.chat.completions.create.call_count, 2, "expected one corrective retry")

    def test_invalid_category_retries_then_rejects_concept(self) -> None:
        bad = self._llm_response([
            {"name": "Quantum Sort", "category": "quantum entanglement",
             "description": "Not a real technique.", "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
        ])
        still_bad = json.dumps({"Quantum Sort": {"category": "magic"}})
        client = self._patch_client([bad, still_bad])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(detected, [], "concept with unrecoverable category must be rejected")
        self.assertEqual(client.chat.completions.create.call_count, 2, "retry budget is exactly one")

    def test_decisions_concept_survives_with_diagram_and_rationale(self) -> None:
        response = self._llm_response([
            {
                "name": "Supabase session auth",
                "category": "decisions",
                "description": (
                    "Login sessions are delegated to Supabase instead of "
                    "being implemented in the backend."
                ),
                "decision": (
                    "Uses Supabase auth so the app never stores password "
                    "hashes or session tokens itself."
                ),
                "diagram": (
                    "flowchart LR\n"
                    "    U[Login form] --> S[Supabase auth]\n"
                    "    S --> T[(Session store)]"
                ),
            },
        ])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=self._patch_client([response])):
            detected = detect_concepts_with_llm("auth.ts", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].category, "decisions")
        self.assertTrue(detected[0].decision.strip(), "a decisions concept must carry its rationale")
        self.assertTrue(
            detected[0].diagram.startswith("flowchart"),
            f"decisions concepts connect pieces with a flowchart, got: {detected[0].diagram[:40]!r}",
        )

    def test_valid_concepts_survive_alongside_rejected_ones(self) -> None:
        bad = self._llm_response([
            {"name": "Memoization", "category": "algorithm",
             "description": "Caching results.", "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
            {"name": "Mystery Pattern", "category": "wizardry",
             "description": "Unclassifiable.", "diagram": "flowchart LR\n    A[Lab] --> B[Lab2]"},
        ])
        retry = json.dumps({"Mystery Pattern": {"category": ""}})
        client = self._patch_client([bad, retry])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual([c.name for c in detected], ["Memoization"])
        self.assertEqual(detected[0].category, "algorithm")


if __name__ == "__main__":
    unittest.main()
