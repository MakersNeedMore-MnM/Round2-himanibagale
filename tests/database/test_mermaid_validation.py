"""Mermaid validation, identity caching, and store concurrency.

Three areas are covered here:

1. ``is_valid_mermaid`` — the lightweight parser: one label-stripping
   pass (``_strip_labels``) reduces the diagram to a skeleton of pure
   structural characters, and header/bracket/brace/quote checks run
   against that skeleton.
2. Detection backfill — a concept detected with a *malformed* diagram
   (not just a missing one) triggers the corrective backfill call, and
   a still-invalid replacement is never stored.
3. ``save_teaching`` — a *pure* validation gate: invalid diagrams are
   stripped to "" with no LLM call.  The single LLM repair attempt
   lives in concept_detector (which has the concept context to repair
   well); the gate must never repeat it.

The store itself (identity slugs, content-hash caching, real thread-
contention concurrency) is exercised in the classes below.
Isolation from the user's real ``~/.mentor`` is two-layered: a
structural guard in ``concepts._resolve_db_path`` (temp DB under any
test runner, fail-closed with no fixture cooperation needed) plus the
``IsolatedStoreTest`` base class here, which patches ``DB_PATH`` per
class for a private per-test database.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.agents.concept_detector import (
    CONCEPT_PATTERNS,
    MERMAID_DIAGRAM_TYPES,
    _strip_labels,
    detect_concepts_with_llm,
    is_valid_mermaid,
)

VALID = {
    "flowchart": "flowchart LR\n    A[Start] --> B{ok?}\n    B -- yes --> C[End]",
    "classDiagram": (
        "classDiagram\n"
        "    class Animal {\n"
        "        +String name\n"
        "        +speak()\n"
        "    }\n"
        "    Animal <|-- Dog"
    ),
    "sequenceDiagram": (
        "sequenceDiagram\n"
        "    participant A as App\n"
        "    A->>N: fetch(url)\n"
        "    N-->>A: response"
    ),
    "erDiagram": (
        "erDiagram\n"
        "    USER {\n"
        "        string id\n"
        "    }\n"
        "    ORDER ||--o{ USER : placed-by"
    ),
    "stateDiagram-v2": (
        "stateDiagram-v2\n"
        "    [*] --> pending\n"
        "    pending --> [*]"
    ),
}


class IsolatedStoreTest(unittest.TestCase):
    """Redirect the store into a temp DB so tests never touch real data.

    Patching HOME is not enough on Windows (ntpath.expanduser prefers
    USERPROFILE), so the module's ``DB_PATH`` is overridden directly
    and the module is restored by reload in cleanup.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        import importlib

        from backend.database import concepts as store

        self.store = importlib.reload(store)  # fresh module state
        self.store.DB_PATH = Path(self._tmp.name) / "mentor.db"
        self.store._schema_ready = False
        self.addCleanup(self._restore_store)
        self.addCleanup(self._tmp.cleanup)

    def _restore_store(self) -> None:
        import importlib

        from backend.database import concepts as store

        importlib.reload(store)  # rebind DB_PATH to the real HOME


class TestDecisionField(IsolatedStoreTest):
    """The ``decision`` field: author-choice capture, end to end.

    ``decision`` records WHY the code does what it does (a trade-off, a
    rejected alternative, a constraint honored) as distinct from the
    generic ``description`` of the technique itself.
    """

    def _detect_response(self, entry: dict) -> mock.MagicMock:
        client = mock.MagicMock()
        completion = mock.MagicMock()
        completion.choices[0].message.content = json.dumps([entry])
        client.chat.completions.create.return_value = completion
        return client

    def test_llm_detection_parses_decision_field(self) -> None:
        client = self._detect_response({
            "name": "Single-flight token refresh",
            "category": "abstract",
            "description": "Refreshes expired auth tokens once.",
            "decision": (
                "A single in-flight promise is reused instead of a lock "
                "because the app is single-tab and locks would deadlock "
                "on the synchronous refresh path."
            ),
            "diagram": "",
        })
        with mock.patch("backend.agents.concept_detector.resolve_api_key",
                        return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client",
                        return_value=client):
            detected = detect_concepts_with_llm("auth.ts", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertIn("single in-flight promise", detected[0].decision)

    def test_missing_decision_defaults_to_empty_not_error(self) -> None:
        # Models may omit the field entirely — must parse cleanly.
        client = self._detect_response({
            "name": "Recursion",
            "category": "algorithm",
            "description": "Self-referential function.",
            "diagram": VALID["flowchart"],
        })
        with mock.patch("backend.agents.concept_detector.resolve_api_key",
                        return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client",
                        return_value=client):
            detected = detect_concepts_with_llm("f.py", "code", set())
        self.assertEqual(detected[0].decision, "")

    def test_decision_flows_node_teacher_store(self) -> None:
        """detect node → teacher node → store, with the decision intact."""
        from backend.agents.concept_detector import detect_concepts
        from backend.agents.teacher_agent import teacher_agent_node
        from backend.agents.concept_detector import DetectedConcept

        decision = (
            "Denormalized onto the user row because the read path is "
            "100x hotter than the write path."
        )
        llm_concept = DetectedConcept(
            name="Denormalized view counts",
            category="data_model",
            description="Counts stored on the row.",
            source_file="db.py",
            diagram=VALID["erDiagram"],
            decision=decision,
        )
        tool_call = {"function": {
            "name": "write_file",
            "arguments": json.dumps({
                "file_path": "db.py", "content": "x = 1\n",
            }),
        }}
        with mock.patch(
            "backend.agents.concept_detector.detect_concepts_with_llm",
            return_value=[llm_concept],
        ):
            state = detect_concepts({
                "tool_calls_log": [tool_call],
                "concepts": [],
                "session": "dec",
            })
        detected = state["concepts_detected"]
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]["decision"], decision)

        teacher_agent_node({
            "messages": [],
            "concepts": [],
            "concepts_detected": detected,
            "session": "dec",
        })
        teachings = self.store.get_teachings("dec")
        self.assertEqual(len(teachings), 1)
        self.assertEqual(teachings[0]["decision"], decision)

    def test_concepts_table_persists_decision(self) -> None:
        self.store.save_concept(
            session="dec", name="Event Delegation", category="api",
            description="One listener for many children.",
            decision="Chosen over per-item listeners because the list "
                     "re-renders every keystroke.",
        )
        concepts = self.store.load_concepts("dec")
        self.assertIn("re-renders every keystroke", concepts[0]["decision"])

    def test_legacy_schema_without_decision_is_upgraded(self) -> None:
        """A pre-decision database must ALTER-migrate, keeping old rows."""
        import sqlite3

        # Build an OLD-schema store: current schema minus both decision
        # columns, seeded with one row per table.
        legacy_sql = self.store._SCHEMA.replace(
            "    decision     TEXT NOT NULL DEFAULT '',\n", ""
        )
        conn = sqlite3.connect(str(self.store.DB_PATH))
        conn.executescript(legacy_sql)
        conn.execute(
            "INSERT INTO concepts (slug, session, name) VALUES (?, ?, ?)",
            ("old-concept", "dec", "Old Concept"),
        )
        conn.execute(
            "INSERT INTO teachings (slug, session, concept_name) "
            "VALUES (?, ?, ?)",
            ("old-concept", "dec", "Old Concept"),
        )
        conn.commit()
        conn.close()

        # Next store touch runs ensure_schema → ALTER migration.
        self.store._schema_ready = False
        self.store.ensure_schema()

        concepts = self.store.load_concepts("dec")
        self.assertEqual(len(concepts), 1)
        self.assertEqual(concepts[0]["decision"], "")  # old row survived
        self.store.save_teaching("dec", {
            "concept_name": "New Thing", "explanation": "e",
            "decision": "d because b", "content_hash": "h1",
        })
        teachings = self.store.get_teachings("dec")
        self.assertEqual(
            [t["decision"] for t in teachings],
            ["", "d because b"],
        )


class TestIsValidMermaid(unittest.TestCase):
    def test_all_supported_types_accepted(self) -> None:
        for kind, diagram in VALID.items():
            self.assertTrue(
                is_valid_mermaid(diagram),
                f"valid {kind} diagram rejected",
            )

    def test_supported_type_list_is_routed_set(self) -> None:
        self.assertEqual(
            set(MERMAID_DIAGRAM_TYPES),
            {"flowchart", "classDiagram", "sequenceDiagram",
             "erDiagram", "stateDiagram-v2"},
        )

    def test_missing_header_rejected(self) -> None:
        self.assertFalse(is_valid_mermaid("A[Start] --> B[End]"))

    def test_unrouted_header_rejected(self) -> None:
        # "graph" is legal Mermaid but outside the category routing.
        self.assertFalse(is_valid_mermaid("graph TD\n    A[Start] --> B[End]"))

    def test_unbalanced_bracket_rejected(self) -> None:
        self.assertFalse(is_valid_mermaid("flowchart LR\n    A[Start --> B[End]"))

    def test_closer_before_opener_rejected(self) -> None:
        self.assertFalse(is_valid_mermaid("flowchart LR\n    A]Start[ --> B"))

    def test_stray_quote_outside_label_rejected(self) -> None:
        # Unclosed quote never forms a span, so it survives into the
        # skeleton and must fail there.
        self.assertFalse(is_valid_mermaid('flowchart LR\n    A["unclosed --> B'))

    def test_escaped_quote_inside_label_accepted(self) -> None:
        # The direct proof of the generalized strip: the quote lives
        # inside a label, so it is consumed by _strip_labels along with
        # the rest of the label content and never hits the quote check.
        diagram = 'flowchart LR\n    A["say \\"hi\\""] --> B[End]'
        self.assertNotIn('"', _strip_labels(diagram))
        self.assertTrue(is_valid_mermaid(diagram))

    def test_brace_outside_label_rejected_in_flowchart(self) -> None:
        self.assertFalse(
            is_valid_mermaid("flowchart LR\n    A[Start] }--> B[End]")
        )

    def test_er_cardinality_braces_accepted(self) -> None:
        # ||--o{ is ER cardinality, NOT an unbalanced brace.
        self.assertTrue(is_valid_mermaid(VALID["erDiagram"]))

    def test_class_attribute_braces_accepted(self) -> None:
        self.assertTrue(is_valid_mermaid(VALID["classDiagram"]))

    def test_fenced_diagram_accepted(self) -> None:
        fenced = "```mermaid\n" + VALID["flowchart"] + "\n```"
        self.assertTrue(is_valid_mermaid(fenced))

    def test_empty_or_non_string_rejected(self) -> None:
        self.assertFalse(is_valid_mermaid(""))
        self.assertFalse(is_valid_mermaid("   \n  "))
        self.assertFalse(is_valid_mermaid(None))  # type: ignore[arg-type]

    def test_every_registry_diagram_is_valid(self) -> None:
        for pattern, info in CONCEPT_PATTERNS.items():
            diagram = info.get("diagram", "")
            self.assertTrue(
                diagram and is_valid_mermaid(diagram),
                f"registry entry {pattern!r} has invalid diagram: "
                f"{diagram[:60]!r}",
            )


class TestBackfillTriggersOnInvalidDiagram(unittest.TestCase):
    """Malformed diagram (not just missing) must trigger the backfill call."""

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

    def test_malformed_diagram_triggers_backfill_and_is_replaced(self) -> None:
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "A function that calls itself.",
             "diagram": "flowchart LR\n    A[Base case --> B[Recurse]"},
        ])
        backfill = json.dumps({"Recursion": VALID["flowchart"]})
        client, completions = self._client_with([detect, backfill])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertTrue(is_valid_mermaid(detected[0].diagram))
        self.assertEqual(
            completions.create.call_count, 2,
            "malformed diagram must trigger exactly one backfill call",
        )

    def test_invalid_backfill_replacement_is_not_stored(self) -> None:
        bad = "flowchart LR\n    A[Base case --> B[Recurse]"
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "A function that calls itself.",
             "diagram": bad},
        ])
        junk_backfill = json.dumps({"Recursion": "flowchart LR\n    A[oops"})
        client, completions = self._client_with([detect, junk_backfill])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(completions.create.call_count, 2)
        self.assertEqual(
            detected[0].diagram, bad,
            "an invalid replacement must not overwrite the diagram — "
            "the save path strips it instead",
        )

    def test_valid_diagram_skips_backfill(self) -> None:
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "A function that calls itself.",
             "diagram": VALID["flowchart"]},
        ])
        client, completions = self._client_with([detect])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(len(detected), 1)
        self.assertEqual(completions.create.call_count, 1, "no backfill for valid diagrams")


class TestSaveTeachingIsAPureValidationGate(IsolatedStoreTest):
    """save_teaching validates and strips — it must never call the LLM."""

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

    def _save_and_load(self, diagram: str) -> list[dict]:
        self.store.save_teaching(
            "t", {"concept_name": "C", "explanation": "prose", "diagram": diagram}
        )
        return self.store.get_teachings("t")

    def test_valid_diagram_saved_untouched(self) -> None:
        client, completions = self._client_with([])
        with mock.patch("backend.llm.client.resolve_api_key", return_value="k"), \
             mock.patch("backend.llm.client.get_client", return_value=client):
            saved = self._save_and_load(VALID["erDiagram"])
        self.assertEqual(saved[0]["diagram"], VALID["erDiagram"])
        self.assertEqual(
            completions.create.call_count, 0,
            "valid diagram must not cost an LLM call",
        )

    def test_invalid_diagram_stripped_with_zero_llm_calls(self) -> None:
        bad = "flowchart LR\n    A[Start --> B[End]"
        client, completions = self._client_with([])
        with mock.patch("backend.llm.client.resolve_api_key", return_value="k"), \
             mock.patch("backend.llm.client.get_client", return_value=client):
            saved = self._save_and_load(bad)
        self.assertEqual(saved[0]["diagram"], "")
        self.assertEqual(
            completions.create.call_count, 0,
            "the gate is cheap and deterministic — no repair attempt here",
        )

    def test_failed_detector_repair_is_not_retried_by_save(self) -> None:
        # End-to-end regression: concept_detector's single repair
        # attempt fails (backfill returns junk), the still-invalid
        # diagram flows into save_teaching, and the LLM call count must
        # NOT increase — one attempt at the expensive thing, ever.
        bad = "flowchart LR\n    A[Start --> B[End]"
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "A function that calls itself.",
             "diagram": bad},
        ])
        junk_backfill = json.dumps({"Recursion": "flowchart LR\n    A[oops"})
        det_client, det_completions = self._client_with([detect, junk_backfill])
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=det_client):
            detected = detect_concepts_with_llm("x.py", "code", set())
        self.assertEqual(det_completions.create.call_count, 2)  # detect + failed repair
        self.assertFalse(is_valid_mermaid(detected[0].diagram))

        save_client, save_completions = self._client_with([])
        with mock.patch("backend.llm.client.resolve_api_key", return_value="k"), \
             mock.patch("backend.llm.client.get_client", return_value=save_client):
            self.store.save_teaching("t", {
                "concept_name": detected[0].name,
                "explanation": "prose",
                "diagram": detected[0].diagram,
            })
        self.assertEqual(
            save_completions.create.call_count, 0,
            "save_teaching must not repeat concept_detector's failed repair",
        )
        self.assertEqual(self.store.get_teachings("t")[0]["diagram"], "")

    def test_invalid_diagram_strip_leaves_prose_intact(self) -> None:
        # No LLM mocking at all: the gate must not need the network.
        saved = self._save_and_load("flowchart LR\n    A[Start --> B[End]")
        self.assertEqual(saved[0]["diagram"], "")
        self.assertEqual(saved[0]["explanation"], "prose")


class TestGenerationTimeCacheSkip(unittest.TestCase):
    """The identity cache must gate the EXPENSIVE call, not just the write.

    Regression for the step-5-shaped bug: with only a write-time
    no-op in save_teaching, a resurfacing concept with unchanged code
    still paid for a full LLM generation call whose output was then
    silently discarded.  The detect_concepts NODE must skip the
    generation call itself when the exact file content already
    produced a stored concept.
    """

    def _tool_call(self, file_path: str, content: str) -> dict:
        return {
            "function": {
                "name": "write_file",
                "arguments": json.dumps({"file_path": file_path, "content": content}),
            },
        }

    def _node_state(self, code: str) -> dict:
        from backend.database import concepts as store

        return {
            "tool_calls_log": [self._tool_call("x.py", code)],
            "concepts": store.load_concepts("s"),
            "session": "s",
            "current_mode_config": {"llm_detection": True},
        }

    def _run_node(self, state: dict) -> mock.MagicMock:
        from backend.agents.concept_detector import detect_concepts

        client = mock.MagicMock()
        # resolve_api_key is patched too: an unconfigured machine must
        # not make this test pass vacuously — with a key "available",
        # a failed cache check WILL reach the LLM and fail the count.
        with mock.patch("backend.agents.concept_detector.resolve_api_key",
                        return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client",
                        return_value=client):
            detect_concepts(state)
        return client

    def test_resurfaced_concept_unchanged_code_skips_generation_call(self):
        from backend.database import concepts as store

        code = "def recurse(n):\n    return recurse(n - 1)\n"
        h = store.content_hash(code)
        # Prime: the concept was taught from THIS content of THIS file.
        store.save_concept(
            "s", "Recursion", "algorithm", "Calls itself.",
            source_file="x.py", code_hash=h,
        )
        store.save_teaching("s", {
            "concept_name": "Recursion",
            "concept_category": "algorithm",
            "explanation": "Calls itself.",
            "diagram": VALID["flowchart"],
            "source_file": "x.py",
            "content_hash": h,
        })

        client = self._run_node(self._node_state(code))
        self.assertEqual(
            client.chat.completions.create.call_count, 0,
            "unchanged code resurfacing in the same file must skip the "
            "generation LLM call entirely — not just the write",
        )

    def test_changed_code_still_pays_for_generation(self):
        from backend.database import concepts as store

        code = "def recurse(n):\n    return recurse(n - 1)\n"
        h = store.content_hash(code)
        store.save_concept(
            "s", "Recursion", "algorithm", "Calls itself.",
            source_file="x.py", code_hash=h,
        )
        store.save_teaching("s", {
            "concept_name": "Recursion",
            "concept_category": "algorithm",
            "explanation": "Calls itself.",
            "diagram": VALID["flowchart"],
            "source_file": "x.py",
            "content_hash": h,
        })

        changed = code + "\n# changed"
        client = self._run_node(self._node_state(changed))
        self.assertEqual(
            client.chat.completions.create.call_count, 1,
            "changed code must NOT hit the file cache — recompute",
        )


class TestConcurrentWrites(unittest.TestCase):
    """Real contention: WAL must survive a daemon-write/dashboard-read race.

    Sequential unit tests prove the logic but pass just as easily with
    no concurrency handling at all.  This test hammers the store from
    many threads at once — writer threads calling save_teaching and
    save_assessment interleaved with reader threads polling like the
    dashboard does — and fails on ANY exception, most importantly
    sqlite3.OperationalError('database is locked').
    """

    WORKERS = 8
    ROUNDS = 25

    def test_threaded_writers_and_readers_never_hit_database_locked(self):
        from concurrent.futures import ThreadPoolExecutor

        from backend.database import concepts as store

        errors: list[Exception] = []

        def writer(i: int) -> None:
            try:
                for j in range(self.ROUNDS):
                    store.save_teaching("c", {
                        "concept_name": f"Concept {i}-{j}",
                        "concept_category": "algorithm",
                        "explanation": "x",
                        "content_hash": f"h-{i}-{j}",
                    })
                    store.save_assessment("c", {
                        "id": f"a-{i}-{j}", "question": "q?",
                    })
            except Exception as exc:  # noqa: BLE001 - collected below
                errors.append(exc)

        def reader(i: int) -> None:
            try:
                for _ in range(self.ROUNDS):
                    store.get_teachings("c")
                    store.get_pending_assessments("c")
                    store.get_assessment_counts("c")
            except Exception as exc:  # noqa: BLE001 - collected below
                errors.append(exc)

        jobs = [(writer, i) for i in range(self.WORKERS)] + \
               [(reader, i) for i in range(2)]
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(fn, i) for fn, i in jobs]
            for f in futures:
                f.result()  # re-raises anything that escaped collection

        self.assertEqual(errors, [], "concurrent access surfaced errors")
        self.assertEqual(len(store.get_teachings("c")), self.WORKERS * self.ROUNDS)
        self.assertEqual(len(store.get_all_assessments("c")), self.WORKERS * self.ROUNDS)


class TestConceptIdentity(IsolatedStoreTest):
    """Identity is the concept name — not which file it appeared in."""

    def test_slug_is_stable_across_files_and_formattings(self) -> None:
        from backend.database.concept_slug import concept_slug

        self.assertEqual(concept_slug("useEffect"), concept_slug("useEffect"))
        self.assertEqual(concept_slug("Classes / OOP"), "classes-oop")
        self.assertEqual(concept_slug("__init__ (Constructor)"), "init-constructor")
        self.assertEqual(concept_slug("  Event   Listeners  "), "event-listeners")

    def test_same_concept_in_new_file_moves_not_duplicates(self) -> None:
        self.store.save_concept(
            "s", "Recursion", "algorithm", "Calls itself.",
            source_file="a.py", code_hash="h1",
        )
        # Same concept name detected later in a DIFFERENT file.
        self.store.save_concept(
            "s", "Recursion", "algorithm", "Calls itself.",
            source_file="other/deep/b.py", code_hash="h1",
        )
        concepts = self.store.load_concepts("s")
        self.assertEqual(len(concepts), 1, "identity is the name, not the file")
        self.assertEqual(concepts[0]["source_file"], "other/deep/b.py")

    def test_bulk_merge_dedups_by_slug_not_file(self) -> None:
        self.store.save_concepts_bulk("s", [
            {"name": "Fetch API", "category": "api",
             "description": "d1", "source_file": "x.js"},
        ])
        self.store.save_concepts_bulk("s", [
            {"name": "Fetch  API", "category": "api",  # different spacing
             "description": "d2", "source_file": "y.js"},
        ])
        concepts = self.store.load_concepts("s")
        self.assertEqual(len(concepts), 1)
        self.assertEqual(concepts[0]["source_file"], "y.js")


class TestIdentityCache(IsolatedStoreTest):
    """Explanations/diagrams are reused only when the code is unchanged."""

    def setUp(self) -> None:
        super().setUp()
        self.hash_a = self.store.content_hash("code version a")
        self.hash_b = self.store.content_hash("code version b")

    def _prime(self) -> None:
        self.store.save_concept(
            "s", "Memoization", "algorithm", "Caching results.",
            source_file="m.py", code_hash=self.hash_a,
        )
        self.store.save_teaching("s", {
            "concept_name": "Memoization",
            "concept_category": "algorithm",
            "explanation": "Caching results.",
            "diagram": VALID["flowchart"],
            "source_file": "m.py",
            "content_hash": self.hash_a,
        })

    def test_cache_hit_on_same_code(self) -> None:
        self._prime()
        cached = self.store.get_cached_teaching(
            "s", "memoization", self.hash_a
        )
        self.assertIsNotNone(cached)
        self.assertEqual(cached["explanation"], "Caching results.")
        self.assertEqual(cached["diagram"], VALID["flowchart"])
        self.assertTrue(cached["cached"])

    def test_cache_miss_when_code_changed(self) -> None:
        self._prime()
        cached = self.store.get_cached_teaching("s", "memoization", self.hash_b)
        self.assertIsNone(cached, "changed code must invalidate the cache")

    def test_cache_miss_without_prior_teaching(self) -> None:
        self._prime()
        cached = self.store.get_cached_teaching("s", "debounce", self.hash_a)
        self.assertIsNone(cached)

    def test_teaching_resave_same_hash_is_noop(self) -> None:
        self._prime()
        self.store.save_teaching("s", {
            "concept_name": "Memoization",
            "concept_category": "algorithm",
            "explanation": "DIFFERENT explanation from a re-detection",
            "diagram": "flowchart TD\n    X[Y] --> Z[Z]",
            "source_file": "other.py",
            "content_hash": self.hash_a,  # same code
        })
        t = self.store.get_teachings("s")[0]
        self.assertEqual(
            t["explanation"], "Caching results.",
            "unchanged code must keep the original teaching",
        )
        self.assertEqual(len(self.store.get_teachings("s")), 1)

    def test_teaching_resave_new_hash_updates(self) -> None:
        self._prime()
        self.store.save_teaching("s", {
            "concept_name": "Memoization",
            "concept_category": "algorithm",
            "explanation": "Fresh explanation for changed code",
            "diagram": VALID["flowchart"],
            "source_file": "m.py",
            "content_hash": self.hash_b,
        })
        t = self.store.get_teachings("s")[0]
        self.assertEqual(t["explanation"], "Fresh explanation for changed code")

    def test_detector_uses_cached_diagram_before_backfill(self) -> None:
        # Store a valid canonical diagram for (slug, hash) — diagrams
        # are cached on the concept row.
        self.store.save_concept(
            "s", "Recursion", "algorithm", "Calls itself.",
            source_file="r.py", code_hash=self.hash_a,
            diagram=VALID["flowchart"],
        )
        # ...then detect the same concept, code unchanged, diagram missing.
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "Calls itself.", "diagram": ""},
        ])
        client = mock.MagicMock()
        completion = mock.MagicMock()
        completion.choices[0].message.content = detect
        client.chat.completions.create.return_value = completion
        # concept_detector bound get_cached_diagram at import time —
        # rebind it to the isolated store for this test.
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client), \
             mock.patch("backend.agents.concept_detector.get_cached_diagram",
                        self.store.get_cached_diagram):
            detected = detect_concepts_with_llm(
                "r.py", "code", set(), session="s", code_hash=self.hash_a
            )
        self.assertEqual(client.chat.completions.create.call_count, 1,
                         "cache hit must skip the backfill call")
        self.assertEqual(detected[0].diagram, VALID["flowchart"])

    def test_detector_with_empty_hash_never_touches_store(self) -> None:
        # Hash-less callers (existing tests, external code) must not
        # depend on or populate the database.
        detect = json.dumps([
            {"name": "Recursion", "category": "algorithm",
             "description": "Calls itself.", "diagram": ""},
        ])
        client = mock.MagicMock()
        completion = mock.MagicMock()
        completion.choices[0].message.content = detect
        client.chat.completions.create.return_value = completion
        with mock.patch("backend.agents.concept_detector.resolve_api_key", return_value="k"), \
             mock.patch("backend.agents.concept_detector.get_client", return_value=client):
            detect_concepts_with_llm("r.py", "code", set())
        self.assertEqual(self.store.load_concepts("default"), [])
        self.assertEqual(self.store.get_teachings("default"), [])


if __name__ == "__main__":
    unittest.main()
