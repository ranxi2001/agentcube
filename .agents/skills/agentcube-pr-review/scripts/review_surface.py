#!/usr/bin/env python3
"""Produce deterministic AgentCube diff facts and heuristic review leads."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml


PATH_CATEGORIES = (
    ("api-crd", ("pkg/apis/", "manifests/charts/base/crds/")),
    ("generated", ("client-go/",)),
    ("workload-manager", ("cmd/workload-manager/", "pkg/workloadmanager/")),
    ("router", ("cmd/router/", "pkg/router/")),
    ("store", ("pkg/store/",)),
    ("picod", ("cmd/picod/", "pkg/picod/")),
    ("agentd", ("cmd/agentd/", "pkg/agentd/")),
    ("sdk-cli-integrations", ("sdk-python/", "cmd/cli/", "integrations/")),
    ("deployment", ("manifests/", "docker/")),
    ("ci-build", (".github/", "Makefile", "hack/")),
    ("e2e", ("test/e2e/",)),
    ("dependencies", ("go.mod", "go.sum")),
)

PRODUCTION_CATEGORIES = {
    "api-crd",
    "workload-manager",
    "router",
    "store",
    "picod",
    "agentd",
    "sdk-cli-integrations",
    "deployment",
}
E2E_COMMAND_PATTERN = (
    r"(?:make\s+e2e\b|test/e2e/run_e2e\.sh\b|go\s+test[^\n]*\./test/e2e(?:/\.\.\.)?)"
)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def object_text(repo: Path, ref: str, path: str) -> str | None:
    result = git(repo, "show", f"{ref}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def parse_changed_files(raw: str) -> list[dict[str, str]]:
    if "\0" in raw:
        fields = raw.split("\0")
        if fields and fields[-1] == "":
            fields.pop()
        files: list[dict[str, str]] = []
        index = 0
        while index < len(fields):
            status = fields[index]
            index += 1
            path_count = 2 if status.startswith(("R", "C")) else 1
            if index + path_count > len(fields):
                raise ValueError("incomplete NUL-delimited git --name-status output")
            paths = fields[index : index + path_count]
            index += path_count
            item = {"status": status, "path": paths[-1]}
            if path_count == 2:
                item["old_path"] = paths[0]
            files.append(item)
        return files

    files: list[dict[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        path = parts[-1]
        item = {"status": status, "path": path}
        if status.startswith(("R", "C")) and len(parts) >= 3:
            item["old_path"] = parts[1]
        files.append(item)
    return files


def categories_for(path: str) -> list[str]:
    categories: list[str] = []
    for name, prefixes in PATH_CATEGORIES:
        if any(path == prefix or path.startswith(prefix) for prefix in prefixes):
            categories.append(name)
    if path.endswith("_test.go") or "/tests/" in path or path.startswith("test/"):
        categories.append("tests")
    return sorted(set(categories)) or ["other"]


def extract_agent_sandbox_versions(go_mod: str, e2e_script: str) -> dict[str, str | None]:
    dependency = None
    match = re.search(r"(?:sigs\.k8s\.io|github\.com/[^/]+)/agent-sandbox\s+v([^\s]+)", go_mod)
    if match:
        dependency = match.group(1)

    runtime = None
    patterns = (
        r"AGENT_SANDBOX_VERSION=\$\{AGENT_SANDBOX_VERSION:-v?([^}\"'\s]+)\}",
        r"AGENT_SANDBOX_VERSION[^\n]*=v?([0-9][^\"'\s}]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, e2e_script)
        if match:
            runtime = match.group(1)
            break

    return {"go_dependency": dependency, "e2e_default": runtime}


def canonical_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def matrix_mapping_matches(combination: dict[str, Any], pattern: dict[str, Any]) -> bool:
    return all(
        key in combination and canonical_scalar(combination[key]) == canonical_scalar(value)
        for key, value in pattern.items()
    )


def matrix_combinations(job: dict[str, Any]) -> list[dict[str, Any]]:
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return [{}]

    axes: list[tuple[str, list[Any]]] = []
    for key, raw_values in matrix.items():
        if key in {"include", "exclude"}:
            continue
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        axes.append((str(key), values))

    combinations = (
        [
            dict(zip((key for key, _ in axes), values, strict=True))
            for values in itertools.product(*(values for _, values in axes))
        ]
        if axes
        else []
    )
    raw_excludes = matrix.get("exclude", [])
    excludes = raw_excludes if isinstance(raw_excludes, list) else [raw_excludes]
    excludes = [item for item in excludes if isinstance(item, dict)]
    combinations = [
        combination
        for combination in combinations
        if not any(matrix_mapping_matches(combination, excluded) for excluded in excludes)
    ]

    raw_includes = matrix.get("include", [])
    includes = raw_includes if isinstance(raw_includes, list) else [raw_includes]
    combinations.extend(dict(item) for item in includes if isinstance(item, dict))
    if not axes and not combinations and "include" not in matrix:
        return [{}]
    return combinations


def workflow_jobs(e2e_workflow: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    try:
        document = yaml.safe_load(e2e_workflow)
    except yaml.YAMLError:
        return []
    if not isinstance(document, dict):
        return []
    jobs = document.get("jobs")
    if isinstance(jobs, dict):
        workflow_env = document.get("env") if isinstance(document.get("env"), dict) else {}
        return [
            (job, workflow_env) for job in jobs.values() if isinstance(job, dict)
        ]
    if isinstance(document.get("steps"), list):
        return [(document, {})]
    if "run" in document:
        step = {"run": document.get("run")}
        if "env" in document:
            step["env"] = document.get("env")
        return [({"steps": [step], "strategy": document.get("strategy")}, {})]
    return []


def resolved_env_bool(value: Any, combination: dict[str, Any]) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    matrix_reference = re.fullmatch(
        r"\s*\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}\s*", value
    )
    if matrix_reference:
        value = combination.get(matrix_reference.group(1))
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return None
    normalized = value.strip().strip("\"'").lower()
    if normalized == "false":
        return False
    if normalized == "true":
        return True
    return None


def shell_assignment_bool(value: str, inherited: bool | None) -> bool | None:
    normalized = value.strip().strip("\"'")
    if normalized in {"$MTLS_ENABLED", "${MTLS_ENABLED}"}:
        return inherited
    if normalized.lower() == "false":
        return False
    if normalized.lower() == "true":
        return True
    return None


def leading_mtls_assignment(
    prefix: str, inherited: bool | None
) -> tuple[bool, bool, bool | None]:
    try:
        tokens = shlex.split(prefix, comments=True, posix=True)
    except ValueError:
        return False, False, None
    while tokens and tokens[0] in {"if", "!", "then", "do"}:
        tokens.pop(0)
    found = False
    value = inherited
    for token in tokens:
        assignment = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", token)
        if not assignment:
            return False, found, value
        if assignment.group(1) == "MTLS_ENABLED":
            found = True
            value = shell_assignment_bool(assignment.group(2), inherited)
    return True, found, value


def persistent_mtls_assignment(segment: str, inherited: bool | None) -> tuple[bool, bool | None]:
    try:
        tokens = shlex.split(segment, comments=True, posix=True)
    except ValueError:
        return False, inherited
    if not tokens:
        return False, inherited
    if tokens[0] == "export":
        tokens = tokens[1:]
    elif not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) for token in tokens):
        return False, inherited
    found = False
    value = inherited
    for token in tokens:
        assignment = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", token)
        if assignment and assignment.group(1) == "MTLS_ENABLED":
            found = True
            value = shell_assignment_bool(assignment.group(2), inherited)
    return found, value


def run_has_mtls_disabled_e2e(run: str, initial: bool | None) -> bool:
    run = run.replace("\\\n", " ")
    run = "\n".join(line for line in run.splitlines() if not line.lstrip().startswith("#"))
    state = initial
    for segment in re.split(r"\r?\n|;|&&|\|\|", run):
        segment = segment.strip()
        if not segment:
            continue
        for command in re.finditer(E2E_COMMAND_PATTERN, segment):
            command_position, has_override, override = leading_mtls_assignment(
                segment[: command.start()], state
            )
            if not command_position:
                continue
            effective = override if has_override else state
            if effective is False:
                return True
        changed, value = persistent_mtls_assignment(segment, state)
        if changed:
            state = value
    return False


def workflow_has_mtls_disabled_path(e2e_workflow: str) -> bool:
    for job, workflow_env in workflow_jobs(e2e_workflow):
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        job_env = job.get("env") if isinstance(job.get("env"), dict) else {}
        for combination in matrix_combinations(job):
            for step in steps:
                if not isinstance(step, dict) or not isinstance(step.get("run"), str):
                    continue
                run = step["run"]
                if not re.search(E2E_COMMAND_PATTERN, run):
                    continue
                step_env = step.get("env") if isinstance(step.get("env"), dict) else {}
                effective_env = {**workflow_env, **job_env, **step_env}
                initial = resolved_env_bool(
                    effective_env.get("MTLS_ENABLED"), combination
                )
                if run_has_mtls_disabled_e2e(run, initial):
                    return True
    return False


def dependency_runtime_versions(repo: Path, head: str) -> dict[str, str | None]:
    go_mod = object_text(repo, head, "go.mod") or ""
    e2e_script = object_text(repo, head, "test/e2e/run_e2e.sh") or ""
    return extract_agent_sandbox_versions(go_mod, e2e_script)


def extract_codeinterpreter_e2e_coverage(
    e2e_script: str, e2e_workflow: str, e2e_go: str
) -> dict[str, bool]:
    default_mtls = bool(re.search(r"^\s*MTLS_ENABLED=true\s*$", e2e_script, re.MULTILINE))
    workflow_disables_mtls = workflow_has_mtls_disabled_path(e2e_workflow)
    warm_pool_match = re.search(
        r"func TestCodeInterpreterWarmPool\([^)]*\)\s*\{(?P<body>.*?)(?=\nfunc |\Z)",
        e2e_go,
        re.DOTALL,
    )
    warm_pool_skips_mtls = bool(warm_pool_match and "skipIfMTLS" in warm_pool_match.group("body"))
    effective_mtls = default_mtls and not workflow_disables_mtls
    return {
        "default_mtls_enabled": default_mtls,
        "workflow_disables_mtls": workflow_disables_mtls,
        "warm_pool_skips_when_mtls": warm_pool_skips_mtls,
        "warm_pool_skipped_by_default": effective_mtls and warm_pool_skips_mtls,
    }


def codeinterpreter_e2e_coverage(repo: Path, head: str) -> dict[str, bool]:
    return extract_codeinterpreter_e2e_coverage(
        object_text(repo, head, "test/e2e/run_e2e.sh") or "",
        object_text(repo, head, ".github/workflows/e2e.yml") or "",
        object_text(repo, head, "test/e2e/e2e_test.go") or "",
    )


def build_report(repo: Path, base: str, head: str) -> dict[str, Any]:
    base_sha = git(repo, "rev-parse", base).stdout.strip()
    head_sha = git(repo, "rev-parse", head).stdout.strip()
    merge_base = git(repo, "merge-base", base_sha, head_sha).stdout.strip()
    base_is_ancestor = (
        git(repo, "merge-base", "--is-ancestor", base_sha, head_sha, check=False).returncode == 0
    )

    merge_result = git(repo, "merge-tree", "--write-tree", base_sha, head_sha, check=False)
    structurally_mergeable = merge_result.returncode == 0

    raw_files = git(repo, "diff", "--name-status", "-z", f"{base_sha}...{head_sha}").stdout
    files = parse_changed_files(raw_files)
    category_map: dict[str, list[str]] = {}
    for item in files:
        for category in categories_for(item["path"]):
            category_map.setdefault(category, []).append(item["path"])

    leads: list[dict[str, str]] = []
    versions = dependency_runtime_versions(repo, head_sha)
    codeinterpreter_coverage = codeinterpreter_e2e_coverage(repo, head_sha)
    if versions["go_dependency"] and versions["e2e_default"]:
        if versions["go_dependency"] != versions["e2e_default"]:
            leads.append(
                {
                    "id": "dependency-runtime-version-skew",
                    "reason": (
                        "go.mod uses agent-sandbox "
                        f"{versions['go_dependency']} while test/e2e/run_e2e.sh defaults to "
                        f"{versions['e2e_default']}"
                    ),
                    "next_check": "Inspect workflow overrides and live install logs before judging coverage.",
                }
            )

    if codeinterpreter_coverage["warm_pool_skipped_by_default"]:
        leads.append(
            {
                "id": "target-e2e-skipped-by-default",
                "reason": (
                    "run_e2e.sh defaults to mTLS, TestCodeInterpreterWarmPool calls skipIfMTLS, "
                    "and no workflow path explicitly supplies MTLS_ENABLED=false."
                ),
                "next_check": "Inspect live logs for SKIP and design explicit mTLS and CodeInterpreter coverage modes.",
            }
        )

    changed_paths = {item["path"] for item in files}
    api_type_change = any(path.startswith("pkg/apis/") and path.endswith(".go") for path in changed_paths)
    generated_change = any(
        path.startswith("client-go/") or path.startswith("manifests/charts/base/crds/")
        for path in changed_paths
    )
    if api_type_change and not generated_change:
        leads.append(
            {
                "id": "api-without-generated-contracts",
                "reason": "API Go types changed without client-go or chart CRD changes in the diff.",
                "next_check": "Determine whether markers/serialized contracts changed and run make gen-all.",
            }
        )

    production_categories = sorted(set(category_map) & PRODUCTION_CATEGORIES)
    has_tests = "tests" in category_map
    if production_categories and not has_tests:
        leads.append(
            {
                "id": "production-change-without-tests",
                "reason": "Production-facing categories changed without test files in the diff.",
                "next_check": "Verify existing coverage or identify the focused regression test that is missing.",
            }
        )

    ownership_categories = sorted(
        set(category_map) & {"workload-manager", "router", "store", "picod", "agentd"}
    )
    if len(ownership_categories) >= 2:
        leads.append(
            {
                "id": "cross-component-ownership",
                "reason": "Multiple responsibility-bearing components changed: " + ", ".join(ownership_categories),
                "next_check": "Build a writer/reader matrix and check for duplicated policy or contract drift.",
            }
        )

    return {
        "notice": "Heuristic leads are review prompts, not findings. Verify them against code and behavior.",
        "repository": str(repo.resolve()),
        "base": {"ref": base, "sha": base_sha},
        "head": {"ref": head, "sha": head_sha},
        "merge_base": merge_base,
        "base_is_ancestor": base_is_ancestor,
        "structurally_mergeable": structurally_mergeable,
        "merge_tree_diagnostics": merge_result.stderr.strip() or None,
        "changed_file_count": len(files),
        "changed_files": files,
        "categories": {key: sorted(value) for key, value in sorted(category_map.items())},
        "agent_sandbox_versions": versions,
        "codeinterpreter_e2e_coverage": codeinterpreter_coverage,
        "review_leads": leads,
        "diff_stat": git(repo, "diff", "--stat", f"{base_sha}...{head_sha}").stdout.rstrip(),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AgentCube Review Surface",
        "",
        f"> {report['notice']}",
        "",
        f"- Base: `{report['base']['ref']}` (`{report['base']['sha']}`)",
        f"- Head: `{report['head']['ref']}` (`{report['head']['sha']}`)",
        f"- Merge base: `{report['merge_base']}`",
        f"- Base is ancestor: `{str(report['base_is_ancestor']).lower()}`",
        f"- Structurally mergeable: `{str(report['structurally_mergeable']).lower()}`",
        f"- Changed files: `{report['changed_file_count']}`",
        "",
        "## Categories",
        "",
    ]
    for category, paths in report["categories"].items():
        lines.append(f"- `{category}`: {len(paths)}")

    lines.extend(["", "## Review Leads", ""])
    if not report["review_leads"]:
        lines.append("- None from deterministic heuristics.")
    for lead in report["review_leads"]:
        lines.append(f"- `{lead['id']}`: {lead['reason']} {lead['next_check']}")

    lines.extend(["", "## Diff Stat", "", "```text", report["diff_stat"], "```"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Git repository root")
    parser.add_argument("--base", required=True, help="Base ref")
    parser.add_argument("--head", default="HEAD", help="Head ref")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), args.base, args.head)
    if args.format == "markdown":
        print(markdown(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
