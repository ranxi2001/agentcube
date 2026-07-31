#!/usr/bin/env python3
"""Score observable agent trajectories and regression-gate harness changes."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


SCHEMA_VERSION = 1
OUTCOME_STATUSES = {"passed", "partial", "failed", "blocked"}
EVENT_SUCCESS = {"ok", "completed"}
EVENT_FAILURE = {"failed", "timed_out"}
EVENT_STATUSES = EVENT_SUCCESS | EVENT_FAILURE | {"skipped"}
EVENT_PHASES = {"search", "read", "edit", "finding", "verify", "tool", "final"}
REFERENCE_PHASES = ("search", "read", "edit", "finding")
REFERENCE_KEYS = {phase: f"{phase}_targets" for phase in REFERENCE_PHASES}
REFERENCE_COVERAGE_PHASES = set(REFERENCE_PHASES) | {"requirement"}
COMPARISON_CONTEXT_FIELDS = ("model", "environment", "budget", "seed")


class ContractError(ValueError):
    """Raised when a run does not satisfy the observable trajectory contract."""


def load_runs(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ContractError("input contains no runs")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(value, dict) and isinstance(value.get("runs"), list):
        value = value["runs"]
    elif isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ContractError("input must be one run, a run array, {\"runs\": [...]}, or JSONL")
    if not value:
        raise ContractError("input contains no runs")
    for run in value:
        validate_run(run)
    run_ids = [run["run_id"] for run in value]
    if len(run_ids) != len(set(run_ids)):
        raise ContractError("run IDs must be unique within an input")
    trial_ids = [(run["task_id"], run.get("attempt", 1)) for run in value]
    if len(trial_ids) != len(set(trial_ids)):
        raise ContractError("task_id/attempt pairs must be unique within an input")
    return value


def validate_run(run: dict[str, Any]) -> None:
    if run.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"run {run.get('run_id', '<unknown>')}: schema_version must be 1")
    for key in ("run_id", "task_id"):
        if not isinstance(run.get(key), str) or not run[key].strip():
            raise ContractError(f"run: {key} must be a non-empty string")
    attempt = run.get("attempt", 1)
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ContractError(f"run {run['run_id']}: attempt must be a positive integer")
    context = run.get("comparison_context")
    if context is not None and not isinstance(context, dict):
        raise ContractError(f"run {run['run_id']}: comparison_context must be an object")
    resources = run.get("resources")
    if resources is not None and not isinstance(resources, dict):
        raise ContractError(f"run {run['run_id']}: resources must be an object")
    outcome = run.get("outcome")
    if not isinstance(outcome, dict) or outcome.get("status") not in OUTCOME_STATUSES:
        raise ContractError(f"run {run['run_id']}: invalid outcome.status")
    checks = outcome.get("checks")
    if not isinstance(checks, list):
        raise ContractError(f"run {run['run_id']}: outcome.checks must be a list")
    seen_check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            raise ContractError(f"run {run['run_id']}: every outcome check needs a string id")
        if check["id"] in seen_check_ids:
            raise ContractError(f"run {run['run_id']}: duplicate outcome check {check['id']}")
        seen_check_ids.add(check["id"])
        if not isinstance(check.get("required", True), bool):
            raise ContractError(f"run {run['run_id']}: check required must be boolean")
        grader = check.get("grader")
        if grader is None:
            if not isinstance(check.get("passed"), bool):
                raise ContractError(f"run {run['run_id']}: declared check passed must be boolean")
            continue
        if not isinstance(grader, dict) or grader.get("kind") != "reference-coverage":
            raise ContractError(
                f"run {run['run_id']}: check grader.kind must be reference-coverage"
            )
        if grader.get("phase") not in REFERENCE_COVERAGE_PHASES:
            raise ContractError(
                f"run {run['run_id']}: reference-coverage phase must be one of "
                f"{sorted(REFERENCE_COVERAGE_PHASES)}"
            )
        minimum = grader.get("minimum_recall", 1.0)
        if (
            isinstance(minimum, bool)
            or not isinstance(minimum, (int, float))
            or not 0 <= float(minimum) <= 1
        ):
            raise ContractError(
                f"run {run['run_id']}: reference-coverage minimum_recall must be between 0 and 1"
            )
        if "passed" in check and not isinstance(check["passed"], bool):
            raise ContractError(f"run {run['run_id']}: declared check passed must be boolean")
    events = run.get("events")
    if not isinstance(events, list):
        raise ContractError(f"run {run['run_id']}: events must be a list")
    sequences: list[int] = []
    for event in events:
        if not isinstance(event, dict):
            raise ContractError(f"run {run['run_id']}: every event must be an object")
        if not isinstance(event.get("seq"), int) or event["seq"] < 0:
            raise ContractError(f"run {run['run_id']}: every event needs a non-negative integer seq")
        if event.get("phase") not in EVENT_PHASES:
            raise ContractError(
                f"run {run['run_id']}: event phase must be one of {sorted(EVENT_PHASES)}"
            )
        if event.get("status", "ok") not in EVENT_STATUSES:
            raise ContractError(
                f"run {run['run_id']}: event status must be one of {sorted(EVENT_STATUSES)}"
            )
        if "covers" in event and not (
            isinstance(event["covers"], list)
            and all(isinstance(item, str) for item in event["covers"])
        ):
            raise ContractError(f"run {run['run_id']}: event covers must be a string list")
        sequences.append(event["seq"])
    if len(sequences) != len(set(sequences)) or sequences != sorted(sequences):
        raise ContractError(f"run {run['run_id']}: event seq values must be unique and increasing")


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def phase_metrics(observed: set[str], gold: set[str]) -> dict[str, float | int | None]:
    if not gold:
        return {
            "observed": len(observed),
            "gold": 0,
            "matched": 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "excess_ratio": None,
        }
    matched = len(observed & gold)
    precision = matched / len(observed) if observed else 0.0
    recall = matched / len(gold)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "observed": len(observed),
        "gold": len(gold),
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "excess_ratio": len(observed) / len(gold),
    }


def target_path(target: str) -> str:
    return target.split("#", 1)[0]


def event_identity(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("phase", "")),
        str(event.get("action", event.get("tool", ""))),
        str(event.get("target", "")),
    )


def observed_targets(events: list[dict[str, Any]], phase: str) -> set[str]:
    return {
        str(event["target"])
        for event in events
        if event.get("phase") == phase and event.get("target") and event.get("status", "ok") in EVENT_SUCCESS
    }


def reference_variants(run: dict[str, Any]) -> list[dict[str, Any]]:
    reference = run.get("reference") or {}
    if not isinstance(reference, dict):
        raise ContractError(f"run {run['run_id']}: reference must be an object")
    variants = [reference]
    alternatives = reference.get("alternatives", [])
    if alternatives and not (
        isinstance(alternatives, list) and all(isinstance(item, dict) for item in alternatives)
    ):
        raise ContractError(f"run {run['run_id']}: reference.alternatives must be an object list")
    for alternative in alternatives:
        merged = {key: value for key, value in reference.items() if key != "alternatives"}
        merged.update(alternative)
        variants.append(merged)
    return variants


def score_reference(events: list[dict[str, Any]], reference: dict[str, Any]) -> dict[str, Any]:
    phases: dict[str, Any] = {}
    recalls: list[float] = []
    f1_values: list[float] = []
    for phase, key in REFERENCE_KEYS.items():
        raw = reference.get(key, [])
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ContractError(f"reference.{key} must be a string list")
        metric = phase_metrics(observed_targets(events, phase), set(raw))
        phases[phase] = metric
        if metric["recall"] is not None:
            recalls.append(float(metric["recall"]))
            f1_values.append(float(metric["f1"]))

    requirement_raw = reference.get("requirement_targets", [])
    if not isinstance(requirement_raw, list) or not all(isinstance(item, str) for item in requirement_raw):
        raise ContractError("reference.requirement_targets must be a string list")
    covered: set[str] = set()
    for event in events:
        if event.get("phase") != "verify" or event.get("status", "ok") not in EVENT_SUCCESS:
            continue
        covered.update(str(item) for item in event.get("covers", []))
        if event.get("target"):
            covered.add(str(event["target"]))
    requirement = phase_metrics(covered, set(requirement_raw))
    if requirement["recall"] is not None:
        recalls.append(float(requirement["recall"]))
        f1_values.append(float(requirement["f1"]))
    return {
        "phases": phases,
        "requirement": requirement,
        "macro_recall": mean(recalls) if recalls else None,
        "macro_f1": mean(f1_values) if f1_values else None,
    }


def choose_reference(run: dict[str, Any], events: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    candidates = [score_reference(events, reference) for reference in reference_variants(run)]
    index = max(
        range(len(candidates)),
        key=lambda item: (
            -1.0 if candidates[item]["macro_f1"] is None else candidates[item]["macro_f1"],
            -item,
        ),
    )
    return index, candidates[index]


def resolve_outcome_checks(
    checks: list[dict[str, Any]], coverage: dict[str, Any]
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for check in checks:
        grader = check.get("grader")
        if grader is None:
            resolved.append(
                {
                    "id": check["id"],
                    "required": check.get("required", True),
                    "passed": check["passed"],
                    "source": "declared",
                }
            )
            continue
        phase = grader["phase"]
        metric = coverage["requirement"] if phase == "requirement" else coverage["phases"][phase]
        recall = metric["recall"]
        minimum = float(grader.get("minimum_recall", 1.0))
        passed = recall is not None and float(recall) >= minimum
        resolved.append(
            {
                "id": check["id"],
                "required": check.get("required", True),
                "passed": passed,
                "source": "reference-coverage",
                "phase": phase,
                "recall": recall,
                "minimum_recall": minimum,
                "declared_passed": check.get("passed"),
            }
        )
    return resolved


def outcome_score(run: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    outcome = run["outcome"]
    checks = resolve_outcome_checks(outcome.get("checks", []), coverage)
    required = [check for check in checks if check["required"]]
    if required:
        passed = sum(1 for check in required if check["passed"])
        completion = passed / len(required)
    else:
        passed = 0
        completion = {"passed": 1.0, "partial": 0.5}.get(outcome["status"], 0.0)
    strict = outcome["status"] == "passed" and completion == 1.0
    return {
        "status": outcome["status"],
        "required_checks": len(required),
        "passed_required_checks": passed,
        "completion_rate": completion,
        "strict_success": strict,
        "checks": checks,
    }


def reasonableness_flags(
    run: dict[str, Any], events: list[dict[str, Any]], outcome: dict[str, Any], repeat_threshold: int
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if run["outcome"]["status"] == "passed" and outcome["completion_rate"] < 1.0:
        flags.append({"id": "passed_with_incomplete_required_checks"})
    for check in outcome["checks"]:
        if (
            check["source"] == "reference-coverage"
            and check["declared_passed"] is not None
            and check["declared_passed"] != check["passed"]
        ):
            flags.append(
                {
                    "id": "declared_check_disagrees_with_grader",
                    "check": check["id"],
                    "declared": check["declared_passed"],
                    "derived": check["passed"],
                }
            )
    verify_events = [event for event in events if event.get("phase") == "verify" and event.get("status", "ok") in EVENT_SUCCESS]
    edit_events = [event for event in events if event.get("phase") == "edit" and event.get("status", "ok") in EVENT_SUCCESS]
    if outcome["strict_success"] and not verify_events:
        flags.append({"id": "passed_without_verification"})
    for edit in edit_events:
        if (edit.get("metadata") or {}).get("new_target"):
            continue
        target = str(edit.get("target", ""))
        prior_read = any(
            event.get("phase") == "read"
            and event.get("status", "ok") in EVENT_SUCCESS
            and event["seq"] < edit["seq"]
            and target
            and target_path(str(event.get("target", ""))) == target_path(target)
            for event in events
        )
        if target and not prior_read:
            flags.append({"id": "edit_without_prior_read", "seq": edit["seq"], "target": target})
    if edit_events and verify_events and max(event["seq"] for event in verify_events) < max(
        event["seq"] for event in edit_events
    ):
        flags.append({"id": "verification_precedes_last_edit"})
    final_events = [event for event in events if event.get("phase") == "final"]
    if not final_events:
        flags.append({"id": "missing_final_event"})
    elif events and max(event["seq"] for event in final_events) < max(event["seq"] for event in events):
        flags.append({"id": "action_after_final"})

    identities = Counter(event_identity(event) for event in events)
    for identity, count in sorted(identities.items()):
        if count > repeat_threshold:
            flags.append(
                {
                    "id": "repeated_action_loop",
                    "phase": identity[0],
                    "action": identity[1],
                    "target": identity[2],
                    "count": count,
                }
            )
    for event in events:
        if event.get("status") not in EVENT_FAILURE:
            continue
        identity = event_identity(event)
        recovered = any(
            later["seq"] > event["seq"]
            and event_identity(later) == identity
            and later.get("status", "ok") in EVENT_SUCCESS
            for later in events
        )
        if not recovered:
            flags.append(
                {
                    "id": "unrecovered_failure",
                    "seq": event["seq"],
                    "phase": identity[0],
                    "action": identity[1],
                    "target": identity[2],
                }
            )
    return flags


def resource_score(run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    resources = run.get("resources") or {}
    total_tokens = resources.get("total_tokens")
    if total_tokens is None and all(key in resources for key in ("input_tokens", "output_tokens")):
        total_tokens = sum(
            float(resources.get(key, 0) or 0) for key in ("input_tokens", "output_tokens")
        )
    if total_tokens is None and events and all("tokens" in event for event in events):
        total_tokens = sum(float(event.get("tokens", 0) or 0) for event in events)
    wall_time = resources.get("wall_time_ms")
    if wall_time is None and events and all("duration_ms" in event for event in events):
        wall_time = sum(float(event.get("duration_ms", 0) or 0) for event in events)
    tool_events = [event for event in events if event.get("phase") == "tool" or event.get("tool")]
    tool_calls = resources.get("tool_calls")
    if tool_calls is None and tool_events:
        tool_calls = len(tool_events)
    failed_events = [event for event in events if event.get("status") in EVENT_FAILURE]
    identities = Counter(event_identity(event) for event in events)
    repeated = sum(max(count - 1, 0) for count in identities.values())
    return {
        "wall_time_ms": None if wall_time is None else float(wall_time),
        "tokens": None if total_tokens is None else float(total_tokens),
        "estimated_cost_usd": (
            None
            if "estimated_cost_usd" not in resources
            else float(resources.get("estimated_cost_usd", 0) or 0)
        ),
        "events": len(events),
        "tool_calls": None if tool_calls is None else float(tool_calls),
        "failed_events": len(failed_events),
        "failed_event_rate": len(failed_events) / len(events) if events else 0.0,
        "repeated_events": repeated,
    }


def diagnoses(score: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    def add(signal: str, layer: str, direction: str) -> None:
        item = {"signal": signal, "layer": layer, "repair_direction": direction}
        if item not in candidates:
            candidates.append(item)

    phases = score["coverage"]["phases"]
    for phase in REFERENCE_PHASES:
        recall = phases[phase]["recall"]
        precision = phases[phase]["precision"]
        if recall is not None and recall < 0.8:
            mapping = {
                "search": ("Context", "improve source routing or task-specific retrieval"),
                "read": ("Context/Tool Interface", "expose and inspect the required symbol or evidence"),
                "edit": ("Tool Interface/Verification", "plan all required edit sites and verify the resulting diff"),
                "finding": ("Context/Observability", "restore acceptance coverage and evidence capture"),
            }
            layer, direction = mapping[phase]
            add(f"low_{phase}_recall", layer, direction)
        if precision is not None and precision < 0.2 and recall is not None and recall >= 0.8:
            add(
                f"low_{phase}_precision",
                "Context",
                "reduce irrelevant exploration without pruning known relevant targets",
            )
    requirement_recall = score["coverage"]["requirement"]["recall"]
    if requirement_recall is not None and requirement_recall < 1.0:
        add("incomplete_requirement_coverage", "Verification", "map every acceptance item to explicit evidence")
    if score["resources"]["failed_event_rate"] > 0.2:
        add("high_failed_event_rate", "Tool Interface/Observability", "surface actionable errors and fix the failing adapter boundary")
    flag_map = {
        "passed_with_incomplete_required_checks": ("Governance", "block completion until required checks pass"),
        "declared_check_disagrees_with_grader": (
            "Verification/Governance",
            "derive completion from the frozen reference instead of a trajectory-provided boolean",
        ),
        "passed_without_verification": ("Verification/Governance", "require deterministic evidence before completion"),
        "edit_without_prior_read": ("Context/Governance", "require target inspection or declare a new target"),
        "verification_precedes_last_edit": ("Verification", "rerun validation after the final edit"),
        "missing_final_event": ("Observability", "emit an explicit finalization event"),
        "action_after_final": ("Lifecycle", "make finalization terminal"),
        "unrecovered_failure": ("Lifecycle/Observability", "classify failure and record a bounded recovery or stop"),
        "repeated_action_loop": ("Lifecycle/Context", "add loop detection, retry budget, or new evidence requirement"),
    }
    for flag in score["reasonableness_flags"]:
        layer, direction = flag_map[flag["id"]]
        add(flag["id"], layer, direction)
    return candidates


def score_run(run: dict[str, Any], repeat_threshold: int = 3) -> dict[str, Any]:
    events = run["events"]
    reference_index, coverage = choose_reference(run, events)
    outcome = outcome_score(run, coverage)
    result = {
        "run_id": run["run_id"],
        "task_id": run["task_id"],
        "attempt": run.get("attempt", 1),
        "comparison_context": run.get("comparison_context"),
        "outcome": outcome,
        "reference_variant": reference_index,
        "coverage": coverage,
        "resources": resource_score(run, events),
        "reasonableness_flags": reasonableness_flags(run, events, outcome, repeat_threshold),
    }
    result["trajectory_reasonable"] = not result["reasonableness_flags"]
    result["repair_candidates"] = diagnoses(result)
    return result


def mean_values(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return mean(present) if present else None


def summarize(scores: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        by_task[score["task_id"]].append(score)
    successes = sum(1 for score in scores if score["outcome"]["strict_success"])
    achieved = sorted(
        task_id
        for task_id, task_scores in by_task.items()
        if any(score["outcome"]["strict_success"] for score in task_scores)
    )
    reliable = sorted(
        task_id
        for task_id, task_scores in by_task.items()
        if task_scores and all(score["outcome"]["strict_success"] for score in task_scores)
    )
    totals: dict[str, float | None] = {}
    for key in ("wall_time_ms", "tokens", "estimated_cost_usd", "tool_calls"):
        measured = [float(score["resources"][key]) for score in scores if score["resources"][key] is not None]
        totals[key] = sum(measured) if measured else None
    for key in ("events", "failed_events", "repeated_events"):
        totals[key] = sum(float(score["resources"][key]) for score in scores)

    successful_measured_tokens = [
        float(score["resources"]["tokens"])
        for score in scores
        if score["outcome"]["strict_success"] and score["resources"]["tokens"] is not None
    ]
    successful_measured_time = [
        float(score["resources"]["wall_time_ms"])
        for score in scores
        if score["outcome"]["strict_success"] and score["resources"]["wall_time_ms"] is not None
    ]
    successful_measured_tools = [
        float(score["resources"]["tool_calls"])
        for score in scores
        if score["outcome"]["strict_success"] and score["resources"]["tool_calls"] is not None
    ]
    successful_events = [
        float(score["resources"]["events"])
        for score in scores
        if score["outcome"]["strict_success"]
    ]
    phase_summary: dict[str, Any] = {}
    for phase in REFERENCE_PHASES:
        phase_summary[phase] = {
            metric: mean_values(score["coverage"]["phases"][phase][metric] for score in scores)
            for metric in ("precision", "recall", "f1", "excess_ratio")
        }
    summary = {
        "trials": len(scores),
        "tasks": len(by_task),
        "strict_successes": successes,
        "trial_success_rate": safe_ratio(successes, len(scores)),
        "achieved_tasks": achieved,
        "task_achievement_rate": safe_ratio(len(achieved), len(by_task)),
        "reliable_tasks": reliable,
        "reliable_task_rate": safe_ratio(len(reliable), len(by_task)),
        "mean_completion_rate": mean_values(score["outcome"]["completion_rate"] for score in scores),
        "mean_macro_recall": mean_values(score["coverage"]["macro_recall"] for score in scores),
        "mean_macro_f1": mean_values(score["coverage"]["macro_f1"] for score in scores),
        "phase_metrics": phase_summary,
        "requirement_metrics": {
            metric: mean_values(score["coverage"]["requirement"][metric] for score in scores)
            for metric in ("precision", "recall", "f1", "excess_ratio")
        },
        "reasonable_trials": sum(1 for score in scores if score["trajectory_reasonable"]),
        "reasonable_trial_rate": mean_values(1.0 if score["trajectory_reasonable"] else 0.0 for score in scores),
        "reasonableness_flag_rate": safe_ratio(
            sum(len(score["reasonableness_flags"]) for score in scores), len(scores)
        ),
        "failed_event_rate": safe_ratio(float(totals["failed_events"]), float(totals["events"])),
        "totals": totals,
        "measured_token_trials": sum(1 for score in scores if score["resources"]["tokens"] is not None),
        "measured_wall_time_trials": sum(1 for score in scores if score["resources"]["wall_time_ms"] is not None),
        "measured_tool_call_trials": sum(1 for score in scores if score["resources"]["tool_calls"] is not None),
        "mean_tokens_per_run": mean_values(score["resources"]["tokens"] for score in scores),
        "mean_wall_time_ms_per_run": mean_values(score["resources"]["wall_time_ms"] for score in scores),
        "tokens_per_strict_success": (
            mean(successful_measured_tokens) if successful_measured_tokens else None
        ),
        "wall_time_ms_per_strict_success": (
            mean(successful_measured_time) if successful_measured_time else None
        ),
        "tool_calls_per_strict_success": (
            mean(successful_measured_tools) if successful_measured_tools else None
        ),
        "events_per_strict_success": mean(successful_events) if successful_events else None,
    }
    return summary


def task_success_map(scores: list[dict[str, Any]]) -> dict[str, bool]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for score in scores:
        grouped[score["task_id"]].append(bool(score["outcome"]["strict_success"]))
    return {task_id: any(values) for task_id, values in grouped.items()}


def trial_map(scores: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(score["task_id"], int(score["attempt"])): score for score in scores}


def task_reliable_map(scores: list[dict[str, Any]]) -> dict[str, bool]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for score in scores:
        grouped[score["task_id"]].append(bool(score["outcome"]["strict_success"]))
    return {task_id: all(values) for task_id, values in grouped.items()}


def delta(challenger: float | None, baseline: float | None) -> float | None:
    if challenger is None or baseline is None:
        return None
    return challenger - baseline


def compare_scores(
    baseline_scores: list[dict[str, Any]],
    challenger_scores: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if not baseline_scores or not challenger_scores:
        raise ContractError("baseline and challenger must each contain at least one run")
    baseline = summarize(baseline_scores)
    challenger = summarize(challenger_scores)
    base_tasks = task_success_map(baseline_scores)
    challenge_tasks = task_success_map(challenger_scores)
    base_trials = trial_map(baseline_scores)
    challenge_trials = trial_map(challenger_scores)
    base_reliable = task_reliable_map(baseline_scores)
    challenge_reliable = task_reliable_map(challenger_scores)
    common = sorted(set(base_tasks) & set(challenge_tasks))
    achievement_regressions = [task for task in common if base_tasks[task] and not challenge_tasks[task]]
    reliability_regressions = [
        task for task in common if base_reliable[task] and not challenge_reliable[task]
    ]
    regressions = sorted(set(achievement_regressions) | set(reliability_regressions))
    improvements = [task for task in common if not base_tasks[task] and challenge_tasks[task]]
    reliability_improvements = [
        task for task in common if not base_reliable[task] and challenge_reliable[task]
    ]
    warnings: list[str] = []
    contract_failures: list[str] = []
    if set(base_tasks) != set(challenge_tasks):
        contract_failures.append("baseline and challenger task ID sets differ")
    if set(base_trials) != set(challenge_trials):
        contract_failures.append("baseline and challenger task_id/attempt pairs differ")
    unmeasured_gates: list[str] = []
    missing_context: list[str] = []
    context_mismatches: list[str] = []
    for task_id, attempt in sorted(set(base_trials) & set(challenge_trials)):
        baseline_context = base_trials[(task_id, attempt)].get("comparison_context") or {}
        challenger_context = challenge_trials[(task_id, attempt)].get("comparison_context") or {}
        missing = [
            field
            for field in COMPARISON_CONTEXT_FIELDS
            if field not in baseline_context
            or field not in challenger_context
            or baseline_context[field] is None
            or challenger_context[field] is None
            or baseline_context[field] == ""
            or challenger_context[field] == ""
            or baseline_context[field] == {}
            or challenger_context[field] == {}
        ]
        if missing:
            missing_context.append(f"{task_id}@{attempt} ({', '.join(missing)})")
            continue
        different = [
            field
            for field in COMPARISON_CONTEXT_FIELDS
            if baseline_context[field] != challenger_context[field]
        ]
        if different:
            context_mismatches.append(f"{task_id}@{attempt} ({', '.join(different)})")
    if missing_context:
        unmeasured_gates.append("comparison_context")
        warnings.append("missing comparison context for: " + "; ".join(missing_context))
    if context_mismatches:
        contract_failures.append("comparison context differs for: " + "; ".join(context_mismatches))
    deltas = {
        "task_achievement_rate": delta(challenger["task_achievement_rate"], baseline["task_achievement_rate"]),
        "mean_completion_rate": delta(challenger["mean_completion_rate"], baseline["mean_completion_rate"]),
        "reliable_task_rate": delta(challenger["reliable_task_rate"], baseline["reliable_task_rate"]),
        "mean_macro_recall": delta(challenger["mean_macro_recall"], baseline["mean_macro_recall"]),
        "finding_recall": delta(
            challenger["phase_metrics"]["finding"]["recall"],
            baseline["phase_metrics"]["finding"]["recall"],
        ),
        "requirement_recall": delta(
            challenger["requirement_metrics"]["recall"], baseline["requirement_metrics"]["recall"]
        ),
        "reasonableness_flag_rate": delta(
            challenger["reasonableness_flag_rate"], baseline["reasonableness_flag_rate"]
        ),
        "tokens_per_strict_success": delta(
            challenger["tokens_per_strict_success"], baseline["tokens_per_strict_success"]
        ),
        "wall_time_ms_per_strict_success": delta(
            challenger["wall_time_ms_per_strict_success"], baseline["wall_time_ms_per_strict_success"]
        ),
        "tool_calls_per_strict_success": delta(
            challenger["tool_calls_per_strict_success"], baseline["tool_calls_per_strict_success"]
        ),
        "events_per_strict_success": delta(
            challenger["events_per_strict_success"], baseline["events_per_strict_success"]
        ),
        "failed_event_rate": delta(challenger["failed_event_rate"], baseline["failed_event_rate"]),
    }
    failures: list[str] = list(contract_failures)
    if len(regressions) > args.max_task_regressions:
        failures.append(
            f"task regressions {len(regressions)} exceed limit {args.max_task_regressions}: {', '.join(regressions)}"
        )
    checks = (
        ("task_achievement_rate", args.min_task_achievement_delta),
        ("mean_completion_rate", args.min_completion_delta),
        ("mean_macro_recall", args.min_macro_recall_delta),
    )
    for name, minimum in checks:
        value = deltas[name]
        if value is None:
            unmeasured_gates.append(name)
        elif value + 1e-12 < minimum:
            failures.append(f"{name} delta {value:.4f} is below {minimum:.4f}")
    flag_delta = deltas["reasonableness_flag_rate"]
    if flag_delta is not None and flag_delta - 1e-12 > args.max_reasonableness_flag_rate_delta:
        failures.append(
            f"reasonableness flag-rate delta {flag_delta:.4f} exceeds {args.max_reasonableness_flag_rate_delta:.4f}"
        )
    base_cost = baseline["tokens_per_strict_success"]
    challenge_cost = challenger["tokens_per_strict_success"]
    if base_cost and challenge_cost is not None:
        ratio = challenge_cost / base_cost - 1.0
        if ratio - 1e-12 > args.max_token_per_success_increase_ratio:
            failures.append(
                f"token-per-success increase {ratio:.1%} exceeds {args.max_token_per_success_increase_ratio:.1%}"
            )
    else:
        ratio = None
        unmeasured_gates.append("tokens_per_strict_success")
    allow_unmeasured = bool(getattr(args, "allow_unmeasured_gates", False))
    if failures:
        gate_status = "FAIL"
    elif unmeasured_gates and not allow_unmeasured:
        gate_status = "INCONCLUSIVE"
    elif unmeasured_gates:
        gate_status = "PASS_WITH_UNMEASURED"
    else:
        gate_status = "PASS"
    return {
        "gate_passed": not failures and (allow_unmeasured or not unmeasured_gates),
        "gate_status": gate_status,
        "gate_failures": failures,
        "warnings": warnings,
        "baseline": baseline,
        "challenger": challenger,
        "deltas": deltas,
        "token_per_success_increase_ratio": ratio,
        "unmeasured_gates": unmeasured_gates,
        "common_tasks": len(common),
        "regressions": regressions,
        "achievement_regressions": achievement_regressions,
        "reliability_regressions": reliability_regressions,
        "improvements": improvements,
        "reliability_improvements": reliability_improvements,
    }


def fmt(value: Any, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return "n/a"
        return f"{value:.1%}" if percent else f"{value:.4f}"
    return str(value)


def score_markdown(scores: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Agent AutoHarness Evaluation",
        "",
        f"- Trials: `{summary['trials']}`",
        f"- Tasks: `{summary['tasks']}`",
        f"- Trial success: `{fmt(summary['trial_success_rate'], True)}`",
        f"- Task achievement: `{fmt(summary['task_achievement_rate'], True)}`",
        f"- Reliable task rate: `{fmt(summary['reliable_task_rate'], True)}`",
        f"- Mean completion: `{fmt(summary['mean_completion_rate'], True)}`",
        f"- Mean macro recall: `{fmt(summary['mean_macro_recall'], True)}`",
        f"- Reasonable trajectory rate: `{fmt(summary['reasonable_trial_rate'], True)}`",
        "",
        "## Runs",
        "",
        "| Run | Task | Success | Completion | Macro recall | Tokens | Tool calls | Flags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for score in scores:
        flags = ", ".join(flag["id"] for flag in score["reasonableness_flags"]) or "none"
        lines.append(
            f"| `{score['run_id']}` | `{score['task_id']}` | "
            f"{fmt(score['outcome']['strict_success'])} | "
            f"{fmt(score['outcome']['completion_rate'], True)} | "
            f"{fmt(score['coverage']['macro_recall'], True)} | "
            f"{fmt(score['resources']['tokens'])} | {fmt(score['resources']['tool_calls'])} | {flags} |"
        )
    lines.extend(["", "## Coverage", "", "| Phase | Precision | Recall | F1 | Excess ratio |", "| --- | --- | --- | --- | --- |"])
    for phase in REFERENCE_PHASES:
        metric = summary["phase_metrics"][phase]
        lines.append(
            f"| {phase} | {fmt(metric['precision'], True)} | {fmt(metric['recall'], True)} | "
            f"{fmt(metric['f1'], True)} | {fmt(metric['excess_ratio'])} |"
        )
    requirement = summary["requirement_metrics"]
    lines.append(
        f"| requirement | {fmt(requirement['precision'], True)} | {fmt(requirement['recall'], True)} | "
        f"{fmt(requirement['f1'], True)} | {fmt(requirement['excess_ratio'])} |"
    )
    lines.extend(
        [
            "",
            "## Efficiency",
            "",
            f"- Total tokens: `{fmt(summary['totals']['tokens'])}`",
            f"- Tokens per strict success: `{fmt(summary['tokens_per_strict_success'])}`",
            f"- Wall time per strict success (ms): `{fmt(summary['wall_time_ms_per_strict_success'])}`",
            f"- Tool calls per strict success: `{fmt(summary['tool_calls_per_strict_success'])}`",
            f"- Observable events per strict success: `{fmt(summary['events_per_strict_success'])}`",
            f"- Failed event rate: `{fmt(summary['failed_event_rate'], True)}`",
            f"- Repeated events: `{fmt(summary['totals']['repeated_events'])}`",
            "",
            "## Repair Candidates",
            "",
        ]
    )
    candidates: dict[tuple[str, str, str], int] = Counter(
        (item["signal"], item["layer"], item["repair_direction"])
        for score in scores
        for item in score["repair_candidates"]
    )
    if not candidates:
        lines.append("- None from deterministic trajectory signals.")
    for (signal, layer, direction), count in candidates.items():
        lines.append(f"- `{signal}` ({count} run(s)), layer `{layer}`: {direction}.")
    return "\n".join(lines)


def compare_markdown(report: dict[str, Any]) -> str:
    baseline = report["baseline"]
    challenger = report["challenger"]
    lines = [
        "# Agent AutoHarness Comparison",
        "",
        f"- Gate: `{report['gate_status']}`",
        f"- Common tasks: `{report['common_tasks']}`",
        f"- Improvements: `{', '.join(report['improvements']) or 'none'}`",
        f"- Reliability improvements: `{', '.join(report['reliability_improvements']) or 'none'}`",
        f"- Regressions: `{', '.join(report['regressions']) or 'none'}`",
        f"- Reliability regressions: `{', '.join(report['reliability_regressions']) or 'none'}`",
        f"- Unmeasured gates: `{', '.join(report['unmeasured_gates']) or 'none'}`",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Challenger | Delta |",
        "| --- | --- | --- | --- |",
    ]
    rows = (
        ("task achievement", baseline["task_achievement_rate"], challenger["task_achievement_rate"], True),
        ("trial success", baseline["trial_success_rate"], challenger["trial_success_rate"], True),
        ("reliable task rate", baseline["reliable_task_rate"], challenger["reliable_task_rate"], True),
        ("completion", baseline["mean_completion_rate"], challenger["mean_completion_rate"], True),
        ("finding recall", baseline["phase_metrics"]["finding"]["recall"], challenger["phase_metrics"]["finding"]["recall"], True),
        ("requirement recall", baseline["requirement_metrics"]["recall"], challenger["requirement_metrics"]["recall"], True),
        ("macro recall", baseline["mean_macro_recall"], challenger["mean_macro_recall"], True),
        ("reasonableness flags per trial", baseline["reasonableness_flag_rate"], challenger["reasonableness_flag_rate"], False),
        ("tokens per success", baseline["tokens_per_strict_success"], challenger["tokens_per_strict_success"], False),
        ("wall time per success (ms)", baseline["wall_time_ms_per_strict_success"], challenger["wall_time_ms_per_strict_success"], False),
        ("tool calls per success", baseline["tool_calls_per_strict_success"], challenger["tool_calls_per_strict_success"], False),
        ("observable events per success", baseline["events_per_strict_success"], challenger["events_per_strict_success"], False),
        ("failed event rate", baseline["failed_event_rate"], challenger["failed_event_rate"], True),
    )
    for label, baseline_value, challenger_value, percent in rows:
        value_delta = delta(challenger_value, baseline_value)
        lines.append(
            f"| {label} | {fmt(baseline_value, percent)} | {fmt(challenger_value, percent)} | "
            f"{fmt(value_delta, percent)} |"
        )
    lines.extend(["", "## Gate Evidence", ""])
    if report["gate_failures"]:
        lines.extend(f"- FAIL: {failure}" for failure in report["gate_failures"])
    else:
        lines.append("- All measurable configured regression gates passed.")
    if report["unmeasured_gates"]:
        if report["gate_status"] == "PASS_WITH_UNMEASURED":
            lines.append(
                "- UNMEASURED: diagnostic override accepted missing measurements for "
                + ", ".join(report["unmeasured_gates"])
                + "; this is not promotion evidence."
            )
        else:
            lines.append(
                "- INCONCLUSIVE: no comparable measurement for "
                + ", ".join(report["unmeasured_gates"])
                + "."
            )
    lines.extend(f"- WARNING: {warning}" for warning in report["warnings"])
    return "\n".join(lines)


def add_common_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repeat-threshold", type=int, default=3)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Score one run set")
    score_parser.add_argument("--input", required=True, type=Path)
    add_common_input(score_parser)

    compare_parser = subparsers.add_parser("compare", help="Compare baseline and challenger run sets")
    compare_parser.add_argument("--baseline", required=True, type=Path)
    compare_parser.add_argument("--challenger", required=True, type=Path)
    compare_parser.add_argument("--max-task-regressions", type=int, default=0)
    compare_parser.add_argument("--min-task-achievement-delta", type=float, default=0.0)
    compare_parser.add_argument("--min-completion-delta", type=float, default=0.0)
    compare_parser.add_argument("--min-macro-recall-delta", type=float, default=0.0)
    compare_parser.add_argument("--max-reasonableness-flag-rate-delta", type=float, default=0.0)
    compare_parser.add_argument("--max-token-per-success-increase-ratio", type=float, default=0.10)
    compare_parser.add_argument(
        "--allow-unmeasured-gates",
        action="store_true",
        help="allow diagnostic passage when configured metrics are unavailable; never use for promotion",
    )
    add_common_input(compare_parser)

    args = parser.parse_args()
    try:
        if args.command == "score":
            scores = [score_run(run, args.repeat_threshold) for run in load_runs(args.input)]
            summary = summarize(scores)
            report = {"runs": scores, "summary": summary}
            print(json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else score_markdown(scores, summary))
            return 0
        baseline_scores = [score_run(run, args.repeat_threshold) for run in load_runs(args.baseline)]
        challenger_scores = [score_run(run, args.repeat_threshold) for run in load_runs(args.challenger)]
        report = compare_scores(baseline_scores, challenger_scores, args)
        print(json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else compare_markdown(report))
        return 0 if report["gate_passed"] else 1
    except (OSError, ContractError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
