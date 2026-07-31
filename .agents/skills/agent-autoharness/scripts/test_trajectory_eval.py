#!/usr/bin/env python3

import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("trajectory_eval.py")
SPEC = importlib.util.spec_from_file_location("trajectory_eval", SCRIPT)
assert SPEC and SPEC.loader
TRAJECTORY_EVAL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TRAJECTORY_EVAL
SPEC.loader.exec_module(TRAJECTORY_EVAL)


def run_fixture(
    run_id: str,
    task_id: str = "task-1",
    attempt: int = 1,
    status: str = "passed",
    checks: list[dict] | None = None,
    events: list[dict] | None = None,
    reference: dict | None = None,
    tokens: int = 100,
) -> dict:
    if checks is None:
        checks = [{"id": "done", "required": True, "passed": status == "passed"}]
    if events is None:
        events = [
            {"seq": 1, "phase": "search", "action": "find", "target": "a.go", "status": "ok"},
            {"seq": 2, "phase": "read", "action": "inspect", "target": "a.go#Run", "status": "ok"},
            {"seq": 3, "phase": "edit", "action": "patch", "target": "a.go#Run", "status": "ok"},
            {"seq": 4, "phase": "verify", "action": "test", "target": "done", "covers": ["done"], "status": "ok"},
            {"seq": 5, "phase": "final", "action": "respond", "status": "ok"},
        ]
    if reference is None:
        reference = {
            "search_targets": ["a.go"],
            "read_targets": ["a.go#Run"],
            "edit_targets": ["a.go#Run"],
            "requirement_targets": ["done"],
        }
    return {
        "schema_version": 1,
        "run_id": run_id,
        "task_id": task_id,
        "attempt": attempt,
        "comparison_context": {
            "model": "test-model",
            "environment": "unit-test",
            "budget": {"max_tokens": 1000},
            "seed": 17,
        },
        "outcome": {"status": status, "checks": checks},
        "reference": reference,
        "events": events,
        "resources": {"total_tokens": tokens, "wall_time_ms": 1000},
    }


class TrajectoryEvalTest(unittest.TestCase):
    def test_empty_input_and_missing_checks_are_contract_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.jsonl"
            empty.touch()
            with self.assertRaises(TRAJECTORY_EVAL.ContractError):
                TRAJECTORY_EVAL.load_runs(empty)

        run = run_fixture("missing-checks")
        run["outcome"].pop("checks")
        with self.assertRaises(TRAJECTORY_EVAL.ContractError):
            TRAJECTORY_EVAL.validate_run(run)

        run = run_fixture("invalid-resources")
        run["resources"] = "unknown"
        with self.assertRaises(TRAJECTORY_EVAL.ContractError):
            TRAJECTORY_EVAL.validate_run(run)

    def test_contract_rejects_unknown_event_phase_and_status(self) -> None:
        run = run_fixture("invalid-event")
        run["events"][0]["phase"] = "seach"
        with self.assertRaises(TRAJECTORY_EVAL.ContractError):
            TRAJECTORY_EVAL.validate_run(run)

        run["events"][0]["phase"] = "search"
        run["events"][0]["status"] = "succes"
        with self.assertRaises(TRAJECTORY_EVAL.ContractError):
            TRAJECTORY_EVAL.validate_run(run)

    def test_scores_success_coverage_and_efficiency_separately(self) -> None:
        score = TRAJECTORY_EVAL.score_run(run_fixture("run-1"))

        self.assertTrue(score["outcome"]["strict_success"])
        self.assertEqual(score["outcome"]["completion_rate"], 1.0)
        self.assertEqual(score["coverage"]["phases"]["search"]["recall"], 1.0)
        self.assertEqual(score["coverage"]["requirement"]["recall"], 1.0)
        self.assertEqual(score["resources"]["tokens"], 100.0)
        self.assertTrue(score["trajectory_reasonable"])

    def test_low_precision_and_recall_remain_visible(self) -> None:
        run = run_fixture(
            "run-2",
            status="partial",
            events=[
                {"seq": 1, "phase": "search", "action": "find", "target": "wrong.go", "status": "ok"},
                {"seq": 2, "phase": "search", "action": "find", "target": "a.go", "status": "ok"},
                {"seq": 3, "phase": "read", "action": "inspect", "target": "wrong.go#X", "status": "ok"},
                {"seq": 4, "phase": "final", "action": "respond", "status": "ok"},
            ],
            reference={
                "search_targets": ["a.go", "b.go"],
                "read_targets": ["a.go#Run"],
                "finding_targets": ["bug-1"],
            },
        )

        score = TRAJECTORY_EVAL.score_run(run)

        self.assertEqual(score["coverage"]["phases"]["search"]["precision"], 0.5)
        self.assertEqual(score["coverage"]["phases"]["search"]["recall"], 0.5)
        self.assertEqual(score["coverage"]["phases"]["read"]["recall"], 0.0)
        self.assertEqual(score["coverage"]["phases"]["finding"]["recall"], 0.0)

    def test_reference_coverage_check_overrides_self_declared_completeness(self) -> None:
        run = run_fixture(
            "finding-closure",
            checks=[
                {
                    "id": "cover-all-known-findings",
                    "required": True,
                    "passed": True,
                    "grader": {
                        "kind": "reference-coverage",
                        "phase": "finding",
                        "minimum_recall": 1.0,
                    },
                }
            ],
            events=[
                {
                    "seq": 1,
                    "phase": "finding",
                    "action": "report",
                    "target": "bug-1",
                    "status": "ok",
                },
                {"seq": 2, "phase": "verify", "action": "audit", "target": "review", "status": "ok"},
                {"seq": 3, "phase": "final", "action": "respond", "status": "ok"},
            ],
            reference={"finding_targets": ["bug-1", "bug-2"]},
        )

        TRAJECTORY_EVAL.validate_run(run)
        score = TRAJECTORY_EVAL.score_run(run)
        flags = {item["id"] for item in score["reasonableness_flags"]}

        self.assertEqual(score["coverage"]["phases"]["finding"]["recall"], 0.5)
        self.assertFalse(score["outcome"]["checks"][0]["passed"])
        self.assertFalse(score["outcome"]["strict_success"])
        self.assertIn("declared_check_disagrees_with_grader", flags)

    def test_reference_coverage_check_passes_from_observed_finding_set(self) -> None:
        run = run_fixture(
            "finding-closure-complete",
            checks=[
                {
                    "id": "cover-all-known-findings",
                    "required": True,
                    "grader": {
                        "kind": "reference-coverage",
                        "phase": "finding",
                    },
                }
            ],
            events=[
                {"seq": 1, "phase": "finding", "action": "report", "target": "bug-1", "status": "ok"},
                {"seq": 2, "phase": "finding", "action": "report", "target": "bug-2", "status": "ok"},
                {"seq": 3, "phase": "verify", "action": "audit", "target": "review", "status": "ok"},
                {"seq": 4, "phase": "final", "action": "respond", "status": "ok"},
            ],
            reference={"finding_targets": ["bug-1", "bug-2"]},
        )

        TRAJECTORY_EVAL.validate_run(run)
        score = TRAJECTORY_EVAL.score_run(run)

        self.assertTrue(score["outcome"]["checks"][0]["passed"])
        self.assertTrue(score["outcome"]["strict_success"])

    def test_missing_resource_measurements_stay_null(self) -> None:
        run = run_fixture("run-no-resources")
        run.pop("resources")

        score = TRAJECTORY_EVAL.score_run(run)
        summary = TRAJECTORY_EVAL.summarize([score])

        self.assertIsNone(score["resources"]["tokens"])
        self.assertIsNone(score["resources"]["wall_time_ms"])
        self.assertIsNone(score["resources"]["tool_calls"])
        self.assertIsNone(summary["tokens_per_strict_success"])
        self.assertIsNone(summary["tool_calls_per_strict_success"])
        self.assertEqual(summary["measured_token_trials"], 0)

    def test_partial_token_or_event_telemetry_stays_null(self) -> None:
        run = run_fixture("partial-tokens")
        run["resources"] = {"input_tokens": 100}
        score = TRAJECTORY_EVAL.score_run(run)
        self.assertIsNone(score["resources"]["tokens"])

        run["events"][0]["tokens"] = 10
        score = TRAJECTORY_EVAL.score_run(run)
        self.assertIsNone(score["resources"]["tokens"])

    def test_tool_calls_require_explicit_telemetry_or_tool_events(self) -> None:
        run = run_fixture("run-tool-calls")
        run["resources"]["tool_calls"] = 4
        explicit = TRAJECTORY_EVAL.score_run(run)

        run["resources"].pop("tool_calls")
        run["events"].insert(
            -1,
            {"seq": 5, "phase": "tool", "action": "test", "target": "suite", "status": "ok"},
        )
        run["events"][-1]["seq"] = 6
        inferred = TRAJECTORY_EVAL.score_run(run)

        self.assertEqual(explicit["resources"]["tool_calls"], 4.0)
        self.assertEqual(inferred["resources"]["tool_calls"], 1.0)

    def test_reasonableness_flags_are_deterministic_leads(self) -> None:
        run = run_fixture(
            "run-3",
            events=[
                {"seq": 1, "phase": "edit", "action": "patch", "target": "a.go#Run", "status": "ok"},
                {"seq": 2, "phase": "verify", "action": "test", "target": "done", "covers": ["done"], "status": "ok"},
                {"seq": 3, "phase": "edit", "action": "patch", "target": "a.go#Run", "status": "ok"},
                {"seq": 4, "phase": "tool", "action": "fetch", "target": "api", "status": "failed"},
                {"seq": 5, "phase": "final", "action": "respond", "status": "ok"},
            ],
        )

        score = TRAJECTORY_EVAL.score_run(run)
        flags = {item["id"] for item in score["reasonableness_flags"]}

        self.assertIn("edit_without_prior_read", flags)
        self.assertIn("verification_precedes_last_edit", flags)
        self.assertIn("unrecovered_failure", flags)

    def test_declared_alternative_reference_can_match_valid_solution(self) -> None:
        run = run_fixture(
            "run-alt",
            events=[
                {"seq": 1, "phase": "search", "action": "find", "target": "alternative.go", "status": "ok"},
                {"seq": 2, "phase": "read", "action": "inspect", "target": "alternative.go#Fix", "status": "ok"},
                {"seq": 3, "phase": "verify", "action": "test", "target": "done", "covers": ["done"], "status": "ok"},
                {"seq": 4, "phase": "final", "action": "respond", "status": "ok"},
            ],
            reference={
                "search_targets": ["a.go"],
                "read_targets": ["a.go#Run"],
                "requirement_targets": ["done"],
                "alternatives": [
                    {
                        "search_targets": ["alternative.go"],
                        "read_targets": ["alternative.go#Fix"],
                    }
                ],
            },
        )

        score = TRAJECTORY_EVAL.score_run(run)

        self.assertEqual(score["reference_variant"], 1)
        self.assertEqual(score["coverage"]["macro_recall"], 1.0)

    def test_aggregate_distinguishes_any_pass_from_reliable_pass(self) -> None:
        scores = [
            TRAJECTORY_EVAL.score_run(run_fixture("a-1", task_id="a")),
            TRAJECTORY_EVAL.score_run(run_fixture("a-2", task_id="a", status="failed")),
            TRAJECTORY_EVAL.score_run(run_fixture("b-1", task_id="b")),
        ]

        summary = TRAJECTORY_EVAL.summarize(scores)

        self.assertEqual(summary["trial_success_rate"], 2 / 3)
        self.assertEqual(summary["task_achievement_rate"], 1.0)
        self.assertEqual(summary["reliable_task_rate"], 0.5)

    def test_compare_gate_names_task_regression(self) -> None:
        baseline = [TRAJECTORY_EVAL.score_run(run_fixture("base", task_id="a"))]
        challenger = [
            TRAJECTORY_EVAL.score_run(run_fixture("challenge", task_id="a", status="failed"))
        ]
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
        )

        report = TRAJECTORY_EVAL.compare_scores(baseline, challenger, args)

        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["regressions"], ["a"])
        self.assertTrue(any("task regressions" in item for item in report["gate_failures"]))

    def test_unmeasured_gate_is_inconclusive_unless_diagnostic_override_is_explicit(self) -> None:
        baseline_run = run_fixture("base-unmeasured")
        challenger_run = run_fixture("challenge-unmeasured")
        baseline_run.pop("resources")
        challenger_run.pop("resources")
        baseline = [TRAJECTORY_EVAL.score_run(baseline_run)]
        challenger = [TRAJECTORY_EVAL.score_run(challenger_run)]
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
            allow_unmeasured_gates=False,
        )

        report = TRAJECTORY_EVAL.compare_scores(baseline, challenger, args)
        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["gate_status"], "INCONCLUSIVE")
        self.assertEqual(report["unmeasured_gates"], ["tokens_per_strict_success"])

        args.allow_unmeasured_gates = True
        report = TRAJECTORY_EVAL.compare_scores(baseline, challenger, args)
        self.assertTrue(report["gate_passed"])
        self.assertEqual(report["gate_status"], "PASS_WITH_UNMEASURED")

    def test_comparison_context_mismatch_fails_gate(self) -> None:
        baseline_run = run_fixture("base-context")
        challenger_run = run_fixture("challenge-context")
        challenger_run["comparison_context"]["model"] = "different-model"
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
            allow_unmeasured_gates=False,
        )

        report = TRAJECTORY_EVAL.compare_scores(
            [TRAJECTORY_EVAL.score_run(baseline_run)],
            [TRAJECTORY_EVAL.score_run(challenger_run)],
            args,
        )

        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["gate_status"], "FAIL")
        self.assertTrue(any("comparison context differs" in item for item in report["gate_failures"]))

    def test_empty_comparison_context_value_is_unmeasured(self) -> None:
        baseline_run = run_fixture("base-empty-context")
        challenger_run = run_fixture("challenge-empty-context")
        baseline_run["comparison_context"]["budget"] = {}
        challenger_run["comparison_context"]["budget"] = {}
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
            allow_unmeasured_gates=False,
        )

        report = TRAJECTORY_EVAL.compare_scores(
            [TRAJECTORY_EVAL.score_run(baseline_run)],
            [TRAJECTORY_EVAL.score_run(challenger_run)],
            args,
        )

        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["gate_status"], "INCONCLUSIVE")
        self.assertIn("comparison_context", report["unmeasured_gates"])

    def test_compare_gate_rejects_unpaired_tasks_and_attempt_counts(self) -> None:
        baseline = [
            TRAJECTORY_EVAL.score_run(run_fixture("base-a", task_id="a")),
            TRAJECTORY_EVAL.score_run(run_fixture("base-b", task_id="b")),
        ]
        challenger = [
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-a-1", task_id="a")),
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-a-2", task_id="a", attempt=2)),
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-c", task_id="c")),
        ]
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
        )

        report = TRAJECTORY_EVAL.compare_scores(baseline, challenger, args)

        self.assertFalse(report["gate_passed"])
        self.assertIn("baseline and challenger task ID sets differ", report["gate_failures"])
        self.assertIn(
            "baseline and challenger task_id/attempt pairs differ", report["gate_failures"]
        )

    def test_compare_gate_names_reliability_regression_even_when_aggregate_is_flat(self) -> None:
        baseline = [
            TRAJECTORY_EVAL.score_run(run_fixture("base-a-1", task_id="a")),
            TRAJECTORY_EVAL.score_run(run_fixture("base-a-2", task_id="a", attempt=2)),
            TRAJECTORY_EVAL.score_run(run_fixture("base-b-1", task_id="b")),
            TRAJECTORY_EVAL.score_run(
                run_fixture("base-b-2", task_id="b", attempt=2, status="failed")
            ),
        ]
        challenger = [
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-a-1", task_id="a")),
            TRAJECTORY_EVAL.score_run(
                run_fixture("challenge-a-2", task_id="a", attempt=2, status="failed")
            ),
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-b-1", task_id="b")),
            TRAJECTORY_EVAL.score_run(run_fixture("challenge-b-2", task_id="b", attempt=2)),
        ]
        args = argparse.Namespace(
            max_task_regressions=0,
            min_task_achievement_delta=0.0,
            min_completion_delta=0.0,
            min_macro_recall_delta=0.0,
            max_reasonableness_flag_rate_delta=0.0,
            max_token_per_success_increase_ratio=0.10,
        )

        report = TRAJECTORY_EVAL.compare_scores(baseline, challenger, args)

        self.assertFalse(report["gate_passed"])
        self.assertEqual(report["reliability_regressions"], ["a"])
        self.assertEqual(report["baseline"]["reliable_task_rate"], 0.5)
        self.assertEqual(report["challenger"]["reliable_task_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
