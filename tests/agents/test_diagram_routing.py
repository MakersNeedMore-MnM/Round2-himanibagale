"""Category-routed diagram generation.

The explanation+diagram prompts must branch on a concept's category:

- ``algorithm``  → flowchart (process/decision shape)
- ``structure``  → classDiagram
- ``api``        → sequenceDiagram (interaction shape)
- ``data_model`` → erDiagram
- ``decisions``  → flowchart (how the wired pieces connect)
- ``abstract``   → NO diagram at all — prose-only explanation

This is what fixes generic-looking diagrams: the model is told which
Mermaid *type* fits the concept instead of choosing freely.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from backend.agents.concept_detector import (
    CATEGORY_FIX_PROMPT,
    CONCEPT_PATTERNS,
    DIAGRAM_BACKFILL_PROMPT,
    LLM_DETECT_PROMPT,
    detect_concepts_with_llm,
)

DIAGRAM = "flowchart LR\n    A[Step] --> B[Done]"


class TestPromptsRouteDiagramTypeByCategory(unittest.TestCase):
    """The prompts must name the right Mermaid type per category."""

    def test_detect_prompt_names_all_four_diagram_types(self) -> None:
        self.assertIn("flowchart", LLM_DETECT_PROMPT)
        self.assertIn("classDiagram", LLM_DETECT_PROMPT)
        self.assertIn("sequenceDiagram", LLM_DETECT_PROMPT)
        self.assertIn("erDiagram", LLM_DETECT_PROMPT)

    def test_detect_prompt_ties_types_to_categories(self) -> None:
        # The routing must be stated per category, not as free advice.
        self.assertRegex(LLM_DETECT_PROMPT, r"algorithm.*flowchart")
        self.assertRegex(LLM_DETECT_PROMPT, r"structure.*classDiagram", )
        self.assertRegex(LLM_DETECT_PROMPT, r"api.*sequenceDiagram")
        self.assertRegex(LLM_DETECT_PROMPT, r"data_model.*erDiagram")

    def test_detect_prompt_makes_abstract_prose_only(self) -> None:
        self.assertRegex(LLM_DETECT_PROMPT, r"abstract[^\n]*\n[^\n]*no diagram|abstract.*prose-only")

    def test_detect_prompt_offers_and_routes_decisions(self) -> None:
        # The architecture/integration category must be listed as an
        # allowed value AND given a diagram type of its own.
        self.assertIn('"decisions"', LLM_DETECT_PROMPT)
        self.assertRegex(LLM_DETECT_PROMPT, r"decisions.*flowchart")
        self.assertRegex(LLM_DETECT_PROMPT, r"six strings")

    def test_fix_prompt_offers_the_decisions_category(self) -> None:
        self.assertIn("decisions", CATEGORY_FIX_PROMPT)

    def test_backfill_prompt_also_routes_by_category(self) -> None:
        self.assertIn("classDiagram", DIAGRAM_BACKFILL_PROMPT)
        self.assertIn("erDiagram", DIAGRAM_BACKFILL_PROMPT)
        self.assertIn("sequenceDiagram", DIAGRAM_BACKFILL_PROMPT)
        self.assertIn("decisions", DIAGRAM_BACKFILL_PROMPT)


class TestAbstractConceptsAreProseOnly(unittest.TestCase):
    """Genuinely abstract concepts must not carry a generated diagram."""

    def _client_with(self, responses: list[str]) -> tuple[mock.MagicMock, mock.MagicMock]:
        completions = mock.MagicMock()
        side_effects = []
        for resp in responses:
            completion = mock.MagicMock()
            completion.choices[0].message.content = resp
            side_effects.append(completion)
        completions.create.side_effect = side_effects
        client = mock.MagicMock()
        client.chat.completions = completions
        return client, completions

    def test_model_diagram_for_abstract_concept_is_stripped(self) -> None:
        response = json.dumps([
            {"name": "Separation of Concerns", "category": "abstract",
             "description": "Splitting a program into distinct sections.",
             "diagram": "flowchart LR\n    A[UI] --> B[Logic]"},
        ])
        client, completions = self._client_with([response])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].category, "abstract")
        self.assertEqual(
            detected[0].diagram, "",
            "abstract concepts must be prose-only — diagram must be stripped",
        )
        # No backfill call may chase a diagram for an abstract concept.
        self.assertEqual(completions.create.call_count, 1)

    def test_abstract_concept_without_diagram_skips_backfill(self) -> None:
        response = json.dumps([
            {"name": "Error Handling", "category": "abstract",
             "description": "Graceful failure paths.", "diagram": ""},
        ])
        client, completions = self._client_with([response])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].diagram, "")
        self.assertEqual(completions.create.call_count, 1, "no backfill for abstract")

    def test_concrete_concept_without_diagram_still_gets_backfill(self) -> None:
        response = json.dumps([
            {"name": "Binary Search", "category": "algorithm",
             "description": "Halving the search space each step.",
             "diagram": ""},
        ])
        backfill = json.dumps({"Binary Search": "flowchart TD\n    A[Start] --> B{mid}"})
        client, completions = self._client_with([response, backfill])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertIn("flowchart", detected[0].diagram)
        self.assertEqual(completions.create.call_count, 2, "backfill still applies to concrete categories")


class TestRegistryDiagramsFollowRouting(unittest.TestCase):
    """Curated registry entries must model the same category→type mapping."""

    def _diagram(self, name: str) -> str:
        for info in CONCEPT_PATTERNS.values():
            if info["name"] == name:
                return info.get("diagram", "")
        return ""

    def test_structure_entry_uses_class_diagram(self) -> None:
        diagram = self._diagram("Classes / OOP")
        self.assertTrue(diagram.startswith("classDiagram"))

    def test_data_model_entries_use_er_diagram(self) -> None:
        for name in ("TypeScript Interface", "TypeScript Type Alias"):
            diagram = self._diagram(name)
            self.assertTrue(
                diagram.startswith("erDiagram"),
                f"{name} should use erDiagram, got: {diagram[:40]!r}",
            )

    def test_api_entry_uses_sequence_diagram(self) -> None:
        self.assertTrue(self._diagram("Fetch API").startswith("sequenceDiagram"))

    def test_algorithm_entry_uses_flowchart(self) -> None:
        self.assertTrue(self._diagram("For Loops").startswith("flowchart"))


if __name__ == "__main__":
    unittest.main()
