"""Tests for the result-based debug router in ``backend.orchestrator.graph``.

``_route_after_coding`` must decide whether to invoke the debug agent by
inspecting structured tool execution results (``exit_code`` /
``stderr_present`` on ``run_command`` entries in ``tool_calls_log``) —
NOT by scanning the coding agent's reply text for keywords like
"error", "failed", or "traceback".

Test B is the regression test that matters: a clean reply that merely
*mentions* the word "error" must not trigger the debug agent, and it
must fail against the old keyword-scanning implementation.
"""

from __future__ import annotations

import inspect
import re
import unittest

from backend.orchestrator.graph import _route_after_coding


def _state(
    tool_calls_log: list[dict] | None = None,
    reply: str = "Done.",
    llm_error: bool = False,
) -> dict:
    """Build a minimal AgentState for routing tests."""
    from langchain_core.messages import AIMessage

    return {
        "messages": [AIMessage(content=reply)],
        "tool_calls_log": tool_calls_log or [],
        "llm_error": llm_error,
    }


def _run_entry(command: str = "python test.py", exit_code: int = 0, stderr_present: bool = False) -> dict:
    """A tool_calls_log entry for run_command, in the shape the coding
    agent attaches after executing a command."""
    import json

    return {
        "function": {
            "name": "run_command",
            "arguments": json.dumps({"command": command}),
        },
        "exit_code": exit_code,
        "stderr_present": stderr_present,
    }


def _read_entry(file_path: str = "src/app.py") -> dict:
    """A successful, non-command tool call (no exit code semantics)."""
    import json

    return {
        "function": {
            "name": "read_file",
            "arguments": json.dumps({"file_path": file_path}),
        }
    }


class TestARoutingRealFailureTriggersDebug(unittest.TestCase):
    """Test A: a genuinely failing command routes to the debug agent."""

    def test_nonzero_exit_code_routes_to_debug_agent(self) -> None:
        state = _state(
            tool_calls_log=[_run_entry(exit_code=1, stderr_present=True)],
            reply="Something went wrong while running the tests.",
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")

    def test_stderr_alone_routes_to_debug_agent(self) -> None:
        # Some CLIs fail with exit code 0 but emit error output; stderr
        # presence alone is treated as a failure signal.
        state = _state(
            tool_calls_log=[_run_entry(exit_code=0, stderr_present=True)],
            reply="Command finished.",
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")

    def test_most_recent_run_command_failure_routes_to_debug(self) -> None:
        state = _state(
            tool_calls_log=[
                _run_entry(command="python build.py", exit_code=0, stderr_present=False),
                _run_entry(command="python test.py", exit_code=1, stderr_present=True),
            ],
            reply="Tests failed.",
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")


class TestBKeywordFalsePositivesAreGone(unittest.TestCase):
    """Test B: the router is driven by results, not reply wording.

    The spec reply explicitly contains "error" — the old keyword scan
    (``any(sig in text for sig in ["test failed", "error", ...])``) would
    route this to the debug agent. The result-based router must not.
    """

    SPEC_REPLY = "No error remains, all tests are passing."

    def test_clean_results_with_error_word_in_reply_do_not_route_to_debug(self) -> None:
        state = _state(
            tool_calls_log=[
                _run_entry(command="python -m pytest", exit_code=0, stderr_present=False),
            ],
            reply=self.SPEC_REPLY,
        )
        self.assertEqual(_route_after_coding(state), "detect_concepts")

    def test_no_commands_at_all_with_error_word_in_reply_does_not_route(self) -> None:
        # Pure-explanation turns (no commands run) must never debug-route
        # on reply wording alone.
        state = _state(
            tool_calls_log=[_read_entry()],
            reply=self.SPEC_REPLY,
        )
        self.assertEqual(_route_after_coding(state), "detect_concepts")

    def test_wordy_reply_with_failed_results_still_routes_on_results(self) -> None:
        # Inverse direction: a cheerful reply cannot mask a real failure.
        state = _state(
            tool_calls_log=[
                _run_entry(command="python -m pytest", exit_code=1, stderr_present=True),
            ],
            reply=self.SPEC_REPLY,
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")


class TestCSelfCorrectedTurnDoesNotTriggerDebug(unittest.TestCase):
    """Test C: a failure the agent already fixed within the same turn must
    NOT trigger the debug agent.

    The router consults only the most recent ``run_command`` result: an
    early failing command followed by a later successful one means the
    coding agent self-corrected (e.g. build failed, fix applied, build
    re-run cleanly) and there is nothing left to debug.
    """

    def test_early_failure_then_later_success_does_not_route_to_debug(self) -> None:
        state = _state(
            tool_calls_log=[
                _run_entry(command="python build.py", exit_code=1, stderr_present=True),
                _read_entry(),
                _run_entry(command="python build.py", exit_code=0, stderr_present=False),
            ],
            reply="Build fixed and re-run successfully.",
        )
        self.assertEqual(_route_after_coding(state), "detect_concepts")

    def test_later_failure_after_early_success_routes_to_debug(self) -> None:
        state = _state(
            tool_calls_log=[
                _run_entry(command="python build.py", exit_code=0, stderr_present=False),
                _run_entry(command="python test.py", exit_code=1, stderr_present=True),
            ],
            reply="Build fine, tests failed.",
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")

    def test_later_command_with_stderr_still_routes_to_debug(self) -> None:
        # Self-correction must be a genuinely clean re-run: a later
        # command that exited 0 but wrote to stderr still triggers debug.
        state = _state(
            tool_calls_log=[
                _run_entry(command="python build.py", exit_code=1, stderr_present=True),
                _run_entry(command="python build.py", exit_code=0, stderr_present=True),
            ],
            reply="Build re-run.",
        )
        self.assertEqual(_route_after_coding(state), "debug_agent")


class TestLlmErrorPathUnchanged(unittest.TestCase):
    """The provider-error guard must keep short-circuiting to detect_concepts."""

    def test_llm_error_skips_debug_even_with_failing_results(self) -> None:
        state = _state(
            tool_calls_log=[_run_entry(exit_code=1, stderr_present=True)],
            reply="(LLM error: provider down)",
            llm_error=True,
        )
        self.assertEqual(_route_after_coding(state), "detect_concepts")

    def test_llm_error_flag_is_still_respected_in_source(self) -> None:
        # The guard must remain part of the implementation itself.
        import backend.orchestrator.graph as graph_mod

        src = inspect.getsource(graph_mod._route_after_coding)
        self.assertIn("llm_error", src)


class TestKeywordScanFullyRemoved(unittest.TestCase):
    """Acceptance criterion: the keyword scan is gone, not supplemented."""

    ROUTER_FUNC = "backend.orchestrator.graph._route_after_coding"

    def test_router_source_contains_no_keyword_signal_list(self) -> None:
        import backend.orchestrator.graph as graph_mod

        src = inspect.getsource(graph_mod._route_after_coding)
        for signal in ("test failed", "traceback", '"error"', "'error'"):
            self.assertNotIn(
                signal,
                src.lower(),
                f"router still contains keyword-scan signal {signal!r}",
            )

    def test_no_fail_signal_heuristic_remains_in_graph_module(self) -> None:
        import backend.orchestrator.graph as graph_mod

        src = inspect.getsource(graph_mod)
        self.assertIsNone(
            re.search(r"fail_signals|error_keywords|FAIL_SIGNALS", src),
            "keyword-scan heuristic still present in graph.py",
        )

    def test_router_reads_tool_calls_log(self) -> None:
        import backend.orchestrator.graph as graph_mod

        src = inspect.getsource(graph_mod._route_after_coding)
        self.assertIn("tool_calls_log", src)


if __name__ == "__main__":
    unittest.main()
