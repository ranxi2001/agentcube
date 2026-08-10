#!/usr/bin/env python3
"""Build an evidence ledger for an AgentCube final-head PR review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import review_surface


GENERATED_PREFIXES = (
    "client-go/",
    "manifests/charts/base/crds/",
)
GENERATED_FILENAMES = {"go.sum", "package-lock.json", "pnpm-lock.yaml", "uv.lock"}
URL_RE = re.compile(r"https?://[^\s<>()\[\]`\"']+")
GO_SCOPE_TOKEN_RE = re.compile(
    r"\./(?:\.\.\.|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*(?:/\.\.\.)?)"
)
GO_TEST_SAFE_BOOL_FLAGS = {
    "-asan",
    "-cover",
    "-failfast",
    "-fullpath",
    "-json",
    "-msan",
    "-race",
    "-v",
}
GO_TEST_SAFE_VALUE_FLAGS = {
    "-count",
    "-covermode",
    "-coverpkg",
    "-coverprofile",
    "-cpu",
    "-mod",
    "-p",
    "-parallel",
    "-shuffle",
    "-timeout",
    "-vet",
}
CI_WAIVER_SETUP_ACTIONS = {
    "actions/checkout",
    "actions/setup-go",
    "dorny/paths-filter",
    "jlumbroso/free-disk-space",
}
CI_WAIVER_RUN_EVENTS = {"push", "workflow_dispatch"}
CI_WAIVER_RUNNERS = {"ubuntu-22.04", "ubuntu-24.04"}
PULL_REQUEST_HEAD_EXPRESSION = "${{ github.event.pull_request.head.sha }}"
GOOS_VALUES = {
    "aix",
    "android",
    "darwin",
    "dragonfly",
    "freebsd",
    "illumos",
    "ios",
    "js",
    "linux",
    "netbsd",
    "openbsd",
    "plan9",
    "solaris",
    "wasip1",
    "windows",
}
GOARCH_VALUES = {
    "386",
    "amd64",
    "arm",
    "arm64",
    "loong64",
    "mips",
    "mips64",
    "mips64le",
    "mipsle",
    "ppc64",
    "ppc64le",
    "riscv64",
    "s390x",
    "wasm",
}
VERSION_COMPARE_RE = re.compile(
    r"\[\[[^\n]*(?:VERSION|version|v[0-9]+\.)[^\n]*\s(?:<|>)\s[^\n]*\]\]"
)
PERSONAL_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|home)[\\/]|/(?:Users|home)/[^/$\s]+/)")
ACCEPTANCE_RE = re.compile(
    r"(?:\[[ xX]\]|\bmust\b|\brequired\b|\bshould\b|\bupgrade\b|\bmigrat\w*\b|"
    r"\bpreserv\w*\b|\bcompatib\w*\b)",
    re.IGNORECASE,
)
GO_FUNC_START_RE = re.compile(
    r"^\s*func\s+(?:\((?P<receiver>[^)]*)\)\s*)?"
    r"(?P<name>[A-Z][A-Za-z0-9_]*)\s*",
    re.MULTILINE,
)
K8S_MODULE_RE = re.compile(
    r"^\s*(k8s\.io/(?:api|apimachinery|client-go))\s+"
    r"(v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+][^\s]+)?)",
    re.MULTILINE,
)
CODEGEN_VERSION_RE = re.compile(
    r"^\s*CODEGEN_VERSION\s*=\s*[\"']?"
    r"(v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+][^\"'\s]+)?)",
    re.MULTILINE,
)
GENERATED_HEADER_LINE_RE = re.compile(
    r"^\s*(?://|#|/\*|<!--)\s*Code generated\b[^\r\n]*\bDO NOT EDIT\.?"
    r"(?:\s*\*/|\s*-->)?\s*$",
)
FINDING_STATUSES = {
    "fixed",
    "present",
    "not-applicable",
    "duplicate-on-current-pr",
    "accepted-by-maintainer",
}
BLOCKING_FINDING_STATUSES = {"present", "duplicate-on-current-pr"}
SCOPE_DISPOSITIONS = {"keep", "remove", "separate", "unresolved", "mixed"}
SCOPE_HUNK_DISPOSITIONS = SCOPE_DISPOSITIONS - {"mixed"}
BLOCKING_SCOPE_DISPOSITIONS = {"remove", "separate", "unresolved"}
BOUNDARY_STATUSES = {"resolved", "not-applicable", "present", "accepted-by-maintainer"}
BLOCKING_BOUNDARY_STATUSES = {"present"}
URL_STATUSES = BOUNDARY_STATUSES
BLOCKING_URL_STATUSES = BLOCKING_BOUNDARY_STATUSES


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return review_surface.git(repo, *args, check=check)


def changed_lines(
    repo: Path,
    base: str,
    head: str,
    files: list[dict[str, str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return added and deleted diff lines grouped by the new-side path."""
    added: dict[str, list[str]] = defaultdict(list)
    deleted: dict[str, list[str]] = defaultdict(list)
    for item in files:
        path = item["path"]
        pathspecs = list(dict.fromkeys([item.get("old_path"), path]))
        result = git(
            repo,
            "--literal-pathspecs",
            "diff",
            "--no-ext-diff",
            "--unified=0",
            f"{base}...{head}",
            "--",
            *(value for value in pathspecs if value is not None),
        )
        in_hunk = False
        for line in result.stdout.splitlines():
            if line.startswith("diff --git "):
                in_hunk = False
            elif line.startswith("@@"):
                in_hunk = True
            elif in_hunk and line.startswith("+"):
                added[path].append(line[1:])
            elif in_hunk and line.startswith("-"):
                deleted[path].append(line[1:])
    return dict(added), dict(deleted)


def has_generated_header(content: str) -> bool:
    in_block_comment = False
    block_end = ""
    for raw_line in content[:500].splitlines():
        if GENERATED_HEADER_LINE_RE.fullmatch(raw_line):
            return True
        stripped = raw_line.strip()
        if not stripped:
            continue
        if in_block_comment:
            if block_end in stripped:
                if stripped.split(block_end, 1)[1].strip():
                    return False
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" in stripped[2:]:
                if stripped.split("*/", 1)[1].strip():
                    return False
            else:
                in_block_comment = True
                block_end = "*/"
            continue
        if stripped.startswith("<!--"):
            if "-->" in stripped[4:]:
                if stripped.split("-->", 1)[1].strip():
                    return False
            else:
                in_block_comment = True
                block_end = "-->"
            continue
        if stripped.startswith(("//", "#", "--")):
            continue
        return False
    return False


def is_generated(path: str, content: str | None) -> bool:
    if path.startswith(GENERATED_PREFIXES):
        return True
    if Path(path).name in GENERATED_FILENAMES:
        return True
    if Path(path).name.startswith("zz_generated."):
        return True
    return bool(content and has_generated_header(content))


def handwritten_files(
    repo: Path, head: str, files: list[dict[str, str]]
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for item in files:
        path = item["path"]
        content = None if item["status"].startswith("D") else review_surface.object_text(repo, head, path)
        if is_generated(path, content):
            continue
        ledger.append(
            {
                "status": item["status"],
                "path": path,
                "categories": review_surface.categories_for(path),
                "reviewer_gate": "record rationale, contract, and evidence",
            }
        )
    return ledger


def directory_has_go_files(repo: Path, head: str, directory: str) -> bool:
    pathspec = "." if directory == "." else directory
    names = git(
        repo,
        "--literal-pathspecs",
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        head,
        "--",
        pathspec,
    ).stdout
    return any(
        name.endswith(".go") and str(Path(name).parent) == directory
        for name in names.split("\0")
        if name
    )


def go_module_roots(repo: Path, head: str) -> list[str]:
    names = git(repo, "ls-tree", "-r", "-z", "--name-only", head).stdout
    roots = {
        str(Path(name).parent)
        for name in names.split("\0")
        if name and Path(name).name == "go.mod"
    }
    return sorted(roots, key=lambda value: (len(Path(value).parts), value))


def module_root_for_directory(directory: str, module_roots: Iterable[str]) -> str:
    matches = [
        root
        for root in module_roots
        if root == "." or directory == root or directory.startswith(f"{root}/")
    ]
    return max(matches, key=lambda value: len(Path(value).parts), default=".")


def changed_test_constraint(repo: Path, head: str, path: str) -> dict[str, str] | None:
    filename = Path(path).name
    stem = filename[: -len("_test.go")]
    parts = stem.split("_")
    goos: str | None = None
    goarch: str | None = None
    if parts and parts[-1] in GOARCH_VALUES:
        goarch = parts[-1]
        if len(parts) > 1 and parts[-2] in GOOS_VALUES:
            goos = parts[-2]
    elif parts and parts[-1] in GOOS_VALUES:
        goos = parts[-1]
    reasons: list[str] = []
    if goos is not None and goos != "linux":
        reasons.append(f"GOOS suffix {goos}")
    if goarch is not None and goarch != "amd64":
        reasons.append(f"GOARCH suffix {goarch}")
    content = review_surface.object_text(repo, head, path) or ""
    if re.search(r"(?m)^\ufeff?[^\S\r\n]*//\s*(?:go:build|\+build)\b", content):
        reasons.append("source build constraint")
    if not reasons:
        return None
    return {"path": path, "reason": "; ".join(reasons)}


def changed_go_test_packages(
    files: list[dict[str, Any]],
    repo: Path | None = None,
    head: str | None = None,
) -> list[dict[str, Any]]:
    direct_runnable: set[str] = set()
    removed_or_moved: set[str] = set()
    constraints: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in files:
        path = item["path"]
        old_path = item.get("old_path")
        if path.endswith("_test.go"):
            directory = str(Path(path).parent)
            if item["status"].startswith("D"):
                removed_or_moved.add(directory)
            else:
                direct_runnable.add(directory)
                if repo is not None and head is not None:
                    constraint = changed_test_constraint(repo, head, path)
                    if constraint is not None:
                        constraints[directory].append(constraint)
        if item["status"].startswith("R") and old_path and old_path.endswith("_test.go"):
            removed_or_moved.add(str(Path(old_path).parent))

    module_roots = go_module_roots(repo, head) if repo is not None and head is not None else []
    packages: list[dict[str, Any]] = []
    for directory in sorted(direct_runnable | removed_or_moved):
        package = "." if directory == "." else f"./{directory}"
        if directory in direct_runnable:
            state = "runnable"
        elif repo is None or head is None:
            state = "runnable"
        else:
            state = "runnable" if directory_has_go_files(repo, head, directory) else "deleted"
        row = {"package": package, "state": state}
        if repo is not None and head is not None:
            row["module_root"] = module_root_for_directory(directory, module_roots)
            row["unverified_test_constraints"] = constraints.get(directory, [])
        packages.append(row)
    return packages


def logical_lines(text: str) -> list[str]:
    lines: list[str] = []
    current = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        current = f"{current} {stripped}".strip() if current else stripped
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        lines.append(current)
        current = ""
    if current:
        lines.append(current)
    return lines


def go_test_scopes(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except ValueError:
        return []
    for index in range(len(tokens) - 1):
        if tokens[index : index + 2] != ["go", "test"]:
            continue
        scopes: set[str] = set()
        for token in tokens[index + 2 :]:
            if token in {";", "&&", "||", "|", "&"}:
                break
            if GO_SCOPE_TOKEN_RE.fullmatch(token):
                scopes.add(token)
        return sorted(scopes)
    return []


def unconditional_direct_go_test(command: str) -> tuple[str, list[str]] | None:
    lines = [line for line in logical_lines(command) if line and not line.lstrip().startswith("#")]
    if len(lines) != 1:
        return None
    line = lines[0]
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except ValueError:
        return None
    if any(token in {";", "&&", "||", "|", "&"} for token in tokens):
        return None
    if tokens[:2] != ["go", "test"]:
        return None
    arguments = tokens[2:]
    scopes: set[str] = set()
    argument_index = 0
    while argument_index < len(arguments):
        token = arguments[argument_index]
        if "$" in token or "`" in token:
            return None
        flag, separator, value = token.partition("=")
        if flag in GO_TEST_SAFE_BOOL_FLAGS:
            if separator and value.lower() not in {"true", "false"}:
                return None
            argument_index += 1
            continue
        if flag in GO_TEST_SAFE_VALUE_FLAGS:
            if not separator:
                argument_index += 1
                if argument_index >= len(arguments):
                    return None
                value = arguments[argument_index]
            if not value or "$" in value or "`" in value:
                return None
            if flag == "-count":
                try:
                    if int(value) <= 0:
                        return None
                except ValueError:
                    return None
            argument_index += 1
            continue
        if GO_SCOPE_TOKEN_RE.fullmatch(token):
            scopes.add(token)
            argument_index += 1
            continue
        # Unknown build/test flags and positional arguments can change which tests execute.
        if token:
            return None
        argument_index += 1
    return (line, sorted(scopes)) if scopes else None


def parse_makefile(text: str) -> dict[str, dict[str, list[str]]]:
    targets: dict[str, dict[str, list[str]]] = {}
    current: list[str] = []
    for raw in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])\s*([^#]*)", raw)
        if match:
            target = match.group(1)
            deps = [token for token in match.group(2).split() if re.fullmatch(r"[A-Za-z0-9_.-]+", token)]
            targets.setdefault(target, {"deps": [], "recipes": []})["deps"].extend(deps)
            current = [target]
        elif raw.startswith("\t") and current:
            for target in current:
                targets[target]["recipes"].append(raw.strip())
        elif raw and not raw[0].isspace():
            current = []
    return targets


def resolve_make_recipes(
    target: str,
    targets: dict[str, dict[str, list[str]]],
    seen: set[str] | None = None,
) -> list[str]:
    seen = set() if seen is None else set(seen)
    if target in seen or target not in targets:
        return []
    seen.add(target)
    recipes: list[str] = []
    data = targets[target]
    for recipe in data["recipes"]:
        recipes.append(recipe)
        for nested in re.findall(r"(?:\$\(MAKE\)|\bmake)\s+([A-Za-z0-9_.-]+)", recipe):
            recipes.extend(resolve_make_recipes(nested, targets, seen))
    for dependency in data["deps"]:
        recipes.extend(resolve_make_recipes(dependency, targets, seen))
    return recipes


def resolve_make_go_tests(
    target: str, targets: dict[str, dict[str, list[str]]]
) -> list[tuple[str, list[str]]]:
    evidence: list[tuple[str, list[str]]] = []
    for recipe in resolve_make_recipes(target, targets):
        scopes = go_test_scopes(recipe)
        if scopes:
            evidence.append((recipe, scopes))
    return evidence


def shell_script_paths(command: str) -> list[str]:
    return list(
        dict.fromkeys(
            re.findall(
                r"(?:^|[\s;&|])(?:bash\s+)?(?:\./)?((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.sh)\b",
                command,
            )
        )
    )


def workflow_test_evidence(repo: Path, head: str) -> list[dict[str, Any]]:
    names = git(repo, "ls-tree", "-r", "--name-only", head, ".github/workflows").stdout.splitlines()
    makefile = review_surface.object_text(repo, head, "Makefile") or ""
    targets = parse_makefile(makefile)
    evidence: list[dict[str, Any]] = []
    job_name_counts: dict[tuple[str, str], int] = defaultdict(int)
    module_roots = go_module_roots(repo, head)
    nested_module_packages = [f"./{root}" for root in module_roots if root != "."]
    root_module_present = "." in module_roots

    def disabled(value: Any) -> bool:
        if value is False:
            return True
        return isinstance(value, str) and value.strip().lower() in {
            "false",
            "${{ false }}",
        }

    def failure_propagates(value: Any) -> bool:
        if value is None or value is False:
            return True
        return isinstance(value, str) and value.strip().lower() in {
            "false",
            "${{ false }}",
        }

    def environment_is_empty(value: Any) -> bool:
        return value is None or value == {}

    def run_defaults(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        defaults = value.get("defaults")
        if not isinstance(defaults, dict):
            return {}
        run = defaults.get("run")
        return run if isinstance(run, dict) else {}

    def prior_steps_preserve_checkout(steps: list[Any], current_index: int) -> bool:
        checkout_count = 0
        for prior_step in steps[: current_index - 1]:
            if not isinstance(prior_step, dict):
                return False
            if disabled(prior_step.get("if")):
                continue
            if not failure_propagates(prior_step.get("continue-on-error")):
                return False
            if isinstance(prior_step.get("run"), str):
                return False
            uses = prior_step.get("uses")
            if not isinstance(uses, str):
                return False
            action_match = re.fullmatch(
                r"(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>[0-9a-fA-F]{40})",
                uses,
            )
            if not action_match or action_match.group("action") not in CI_WAIVER_SETUP_ACTIONS:
                return False
            if action_match.group("action") == "actions/checkout":
                checkout_options = prior_step.get("with", {})
                if not isinstance(checkout_options, dict):
                    return False
                if any(
                    checkout_options.get(key) not in {None, ""}
                    for key in ("repository", "path", "sparse-checkout")
                ):
                    return False
                if checkout_options.get("ref") not in {head, PULL_REQUEST_HEAD_EXPRESSION}:
                    return False
                if checkout_options.get("clean") not in {
                    None,
                    True,
                    "true",
                    "${{ true }}",
                }:
                    return False
                if prior_step.get("if") is not None:
                    return False
                checkout_count += 1
        return checkout_count == 1

    def add_candidate(
        workflow: str,
        job_id: str,
        job_name: str,
        step_name: str,
        step_index: int,
        source: str,
        command: str,
        direct_waiver_candidate: bool = False,
        job_identity_static: bool = False,
        step_name_unique: bool = False,
        exact_head_checkout: bool = False,
    ) -> None:
        scopes = go_test_scopes(command)
        if scopes:
            evidence.append(
                {
                    "workflow": workflow,
                    "job": job_id,
                    "job_name": job_name,
                    "step": step_name,
                    "step_index": step_index,
                    "source": source,
                    "command": command,
                    "scopes": scopes,
                    "direct_waiver_candidate": direct_waiver_candidate,
                    "job_identity_static": job_identity_static,
                    "step_name_unique": step_name_unique,
                    "exact_head_checkout": exact_head_checkout,
                    "nested_module_packages": nested_module_packages,
                }
            )

    def add_script_candidates(
        workflow: str,
        job_id: str,
        job_name: str,
        step_name: str,
        step_index: int,
        source: str,
        command: str,
    ) -> None:
        for script in shell_script_paths(command):
            script_content = review_surface.object_text(repo, head, script) or ""
            for script_line in logical_lines(script_content):
                add_candidate(
                    workflow,
                    job_id,
                    job_name,
                    step_name,
                    step_index,
                    f"{source} -> {script}",
                    script_line,
                )

    for name in sorted(path for path in names if path.endswith((".yml", ".yaml"))):
        content = review_surface.object_text(repo, head, name) or ""
        try:
            workflow = review_surface.yaml.safe_load(content) or {}
        except review_surface.yaml.YAMLError as error:
            raise ValueError(f"{name}: invalid workflow YAML: {error}") from error
        jobs = workflow.get("jobs", {}) if isinstance(workflow, dict) else {}
        workflow_env = workflow.get("env", {}) if isinstance(workflow, dict) else {}
        workflow_run_defaults = run_defaults(workflow)
        if not isinstance(jobs, dict):
            continue
        for raw_job_id, raw_job in jobs.items():
            if not isinstance(raw_job_id, str) or not isinstance(raw_job, dict):
                continue
            if disabled(raw_job.get("if")):
                continue
            job_name_value = raw_job.get("name", raw_job_id)
            job_name = job_name_value if isinstance(job_name_value, str) else raw_job_id
            job_name_counts[(name, job_name)] += 1
            steps = raw_job.get("steps", [])
            if not isinstance(steps, list):
                continue
            job_run_defaults = run_defaults(raw_job)
            container = raw_job.get("container")
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict) or disabled(step.get("if")):
                    continue
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                step_name_value = step.get("name")
                step_name = (
                    step_name_value
                    if isinstance(step_name_value, str) and step_name_value.strip()
                    else ""
                )
                step_name_count = sum(
                    1
                    for candidate_step in steps
                    if isinstance(candidate_step, dict)
                    and candidate_step.get("name") == step_name
                )
                has_matrix = isinstance(raw_job.get("strategy"), dict) and (
                    "matrix" in raw_job["strategy"]
                )
                job_identity_static = not has_matrix and "${{" not in job_name
                effective_working_directory = step.get(
                    "working-directory",
                    job_run_defaults.get(
                        "working-directory", workflow_run_defaults.get("working-directory")
                    ),
                )
                effective_shell = step.get(
                    "shell", job_run_defaults.get("shell", workflow_run_defaults.get("shell"))
                )
                exact_head_checkout = prior_steps_preserve_checkout(steps, index)
                execution_context_safe = (
                    failure_propagates(raw_job.get("continue-on-error"))
                    and failure_propagates(step.get("continue-on-error"))
                    and environment_is_empty(workflow_env)
                    and environment_is_empty(raw_job.get("env"))
                    and environment_is_empty(step.get("env"))
                    and container is None
                    and exact_head_checkout
                    and effective_working_directory in {None, ".", "${{ github.workspace }}"}
                    and effective_shell in {None, "bash", "sh"}
                    and raw_job.get("runs-on") in CI_WAIVER_RUNNERS
                )
                verifiable_context = (
                    job_identity_static
                    and bool(step_name)
                    and step_name_count == 1
                    and execution_context_safe
                )
                direct = unconditional_direct_go_test(run) if verifiable_context else None
                source = f"{name}:{raw_job_id}:{step_name or f'run-{index}'}"
                for line in logical_lines(run):
                    add_candidate(
                        name,
                        raw_job_id,
                        job_name,
                        step_name,
                        index,
                        source,
                        line,
                        direct_waiver_candidate=bool(direct and direct[0] == line),
                        job_identity_static=job_identity_static,
                        step_name_unique=step_name_count == 1,
                        exact_head_checkout=exact_head_checkout,
                    )
                    add_script_candidates(
                        name, raw_job_id, job_name, step_name, index, source, line
                    )
                    for target in re.findall(r"\bmake\s+([A-Za-z0-9_.-]+)", line):
                        make_source = f"{source} -> Makefile:{target}"
                        for recipe in resolve_make_recipes(target, targets):
                            add_candidate(
                                name,
                                raw_job_id,
                                job_name,
                                step_name,
                                index,
                                make_source,
                                recipe,
                            )
                            add_script_candidates(
                                name,
                                raw_job_id,
                                job_name,
                                step_name,
                                index,
                                make_source,
                                recipe,
                            )
    unique: dict[
        tuple[str, str, str, int, str, str, tuple[str, ...], tuple[str, ...]],
        dict[str, Any],
    ] = {}
    for item in evidence:
        item["ci_waivable"] = bool(
            item["direct_waiver_candidate"]
            and item["job_identity_static"]
            and item["step_name_unique"]
            and item["exact_head_checkout"]
            and root_module_present
            and job_name_counts[(item["workflow"], item["job_name"])] == 1
        )
        key = (
            item["workflow"],
            item["job"],
            item["step"],
            item["step_index"],
            item["source"],
            item["command"],
            tuple(item["scopes"]),
            tuple(item["nested_module_packages"]),
        )
        unique[key] = item
    return [unique[key] for key in sorted(unique)]


def scope_covers_package(
    scope: str, package: str, nested_module_packages: Iterable[str] = ()
) -> bool:
    if any(
        package == module or package.startswith(f"{module}/")
        for module in nested_module_packages
    ):
        return False
    if scope == "./...":
        prefix = "."
    elif scope.endswith("/..."):
        prefix = scope[:-4].rstrip("/")
    else:
        return scope == package
    if package == prefix:
        return True
    if not package.startswith(f"{prefix}/"):
        return False
    relative_segments = package[len(prefix) + 1 :].split("/")
    return not any(
        segment in {"testdata", "vendor"} or segment.startswith((".", "_"))
        for segment in relative_segments
    )


def package_coverage(
    packages: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    ci_closures: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ci_closures = {} if ci_closures is None else ci_closures
    coverage: list[dict[str, Any]] = []
    for item in packages:
        matches = [
            entry
            for entry in evidence
            if item["state"] == "runnable"
            and not item.get("unverified_test_constraints")
            and any(
                scope_covers_package(
                    scope,
                    item["package"],
                    entry.get("nested_module_packages", ()),
                )
                for scope in entry["scopes"]
            )
        ]
        coverage.append(
            {
                **item,
                "ci_covered": item["package"] in ci_closures,
                "workflow_candidates": matches,
                "ci_closure": ci_closures.get(item["package"]),
            }
        )
    return coverage


def acceptance_candidates(files: Iterable[Path], notes: Iterable[str]) -> list[str]:
    candidates = [note.strip() for note in notes if note.strip()]
    for path in files:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and ACCEPTANCE_RE.search(line):
                candidates.append(line)
    return list(dict.fromkeys(candidates))


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    schema_version = value.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    return value


def json_object_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_finding_ledger(paths: Iterable[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_ledgers: set[tuple[str, int]] = set()
    for raw_path in paths:
        path = Path(raw_path)
        value = load_json_object(path)
        ledger_id = value.get("ledger_id")
        ledger_version = value.get("ledger_version")
        entries = value.get("findings")
        if not isinstance(ledger_id, str) or not ledger_id.strip():
            raise ValueError(f"{path}: ledger_id must be a non-empty string")
        if (
            isinstance(ledger_version, bool)
            or not isinstance(ledger_version, int)
            or ledger_version < 1
        ):
            raise ValueError(f"{path}: ledger_version must be a positive integer")
        if not isinstance(entries, list):
            raise ValueError(f"{path}: findings must be a list")
        if not entries:
            raise ValueError(
                f"{path}: findings must not be empty; use --no-carry-forward-findings instead"
            )
        ledger_key = (ledger_id.strip(), ledger_version)
        if ledger_key in seen_ledgers:
            raise ValueError(f"duplicate finding ledger: {ledger_key[0]} v{ledger_key[1]}")
        seen_ledgers.add(ledger_key)
        ledger_digest = json_object_digest(value)
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{path}: every finding must be an object")
            finding_id = entry.get("id")
            summary = entry.get("summary")
            provenance = entry.get("provenance")
            finding_paths = entry.get("paths", [])
            if not isinstance(finding_id, str) or not finding_id.strip():
                raise ValueError(f"{path}: every finding needs a non-empty string id")
            if finding_id in seen:
                raise ValueError(f"duplicate finding id: {finding_id}")
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError(f"{path}: finding {finding_id} needs a non-empty summary")
            if not (
                isinstance(provenance, list)
                and provenance
                and all(isinstance(item, str) and item.strip() for item in provenance)
            ):
                raise ValueError(f"{path}: finding {finding_id} needs non-empty provenance")
            if not (
                isinstance(finding_paths, list)
                and all(isinstance(item, str) and item.strip() for item in finding_paths)
            ):
                raise ValueError(f"{path}: finding {finding_id} paths must be a string list")
            seen.add(finding_id)
            findings.append(
                {
                    "id": finding_id,
                    "summary": summary.strip(),
                    "provenance": provenance,
                    "paths": finding_paths,
                    "ledger_id": ledger_key[0],
                    "ledger_version": ledger_version,
                    "ledger_digest": ledger_digest,
                    "ledger_source": str(path),
                }
            )
    return findings


def validated_target(target: Any, source: str | Path) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError(f"{source}: target must be an object")
    repository = target.get("repository")
    pull_request = target.get("pull_request")
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError(f"{source}: target.repository must be owner/repo")
    if isinstance(pull_request, bool) or not isinstance(pull_request, int) or pull_request < 1:
        raise ValueError(f"{source}: target.pull_request must be a positive integer")
    return {"repository": repository, "pull_request": pull_request}


def required_scope_text(entry: dict[str, Any], key: str, source: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}: {key} must be a non-empty string")
    return value.strip()


def required_scope_path(entry: dict[str, Any], source: str) -> str:
    value = entry.get("path")
    if not isinstance(value, str) or value == "" or "\0" in value:
        raise ValueError(f"{source}: path must be a non-empty NUL-free string")
    return value


def required_scope_evidence(entry: dict[str, Any], source: str) -> list[str]:
    evidence = entry.get("evidence")
    if not (
        isinstance(evidence, list)
        and evidence
        and all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise ValueError(f"{source}: evidence must be a non-empty string list")
    return [item.strip() for item in evidence]


def load_scope_closure(
    raw_path: str | None,
    handwritten: list[dict[str, Any]],
    expected_head: str,
    expected_target: dict[str, Any],
    expected_base: str | None = None,
    expected_merge_base: str | None = None,
) -> dict[str, Any]:
    expected_target = validated_target(expected_target, "command-line target")
    expected_paths = {item["path"] for item in handwritten}
    if not raw_path:
        return {
            "source_provided": False,
            "source": None,
            "expected_head": expected_head,
            "declared_head": None,
            "head_matches": None,
            "expected_base": expected_base,
            "declared_base": None,
            "base_matches": None,
            "expected_merge_base": expected_merge_base,
            "declared_merge_base": None,
            "merge_base_matches": None,
            "expected_target": expected_target,
            "missing_paths": sorted(expected_paths),
            "blocking_items": [],
            "rows": [{**item, "scope": None} for item in handwritten],
        }

    path = Path(raw_path)
    value = load_json_object(path)
    target = validated_target(value.get("target"), path)
    if target != expected_target:
        raise ValueError(
            f"{path}: scope target {target['repository']}#{target['pull_request']} "
            f"does not match command-line target "
            f"{expected_target['repository']}#{expected_target['pull_request']}"
        )
    declared_head = value.get("head")
    if not isinstance(declared_head, str) or not re.fullmatch(r"[0-9a-f]{40}", declared_head):
        raise ValueError(f"{path}: head must be an exact commit SHA")
    declared_base = value.get("base")
    if expected_base is not None:
        if not isinstance(declared_base, str) or not re.fullmatch(r"[0-9a-f]{40}", declared_base):
            raise ValueError(f"{path}: base must be an exact commit SHA")
    declared_merge_base = value.get("merge_base")
    if expected_merge_base is not None:
        if not isinstance(declared_merge_base, str) or not re.fullmatch(
            r"[0-9a-f]{40}", declared_merge_base
        ):
            raise ValueError(f"{path}: merge_base must be an exact commit SHA")
    entries = value.get("files")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: files must be a list")

    closures: dict[str, dict[str, Any]] = {}
    blocking_items: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every scope file must be an object")
        changed_path = required_scope_path(entry, str(path))
        source = f"{path}: scope file {changed_path!r}"
        if changed_path not in expected_paths:
            raise ValueError(f"{source} is not a hand-written changed path")
        if changed_path in closures:
            raise ValueError(f"{path}: duplicate scope path {changed_path}")
        disposition = entry.get("disposition")
        if not isinstance(disposition, str) or disposition not in SCOPE_DISPOSITIONS:
            raise ValueError(
                f"{source}: disposition must be one of {sorted(SCOPE_DISPOSITIONS)}"
            )
        independently_mergeable = entry.get("independently_mergeable")
        if not isinstance(independently_mergeable, bool):
            raise ValueError(f"{source}: independently_mergeable must be boolean")
        atomicity = entry.get("atomicity")
        if atomicity is not None and (not isinstance(atomicity, str) or not atomicity.strip()):
            raise ValueError(f"{source}: atomicity must be a non-empty string when supplied")

        hunks_value = entry.get("hunks", [])
        if not isinstance(hunks_value, list):
            raise ValueError(f"{source}: hunks must be a list")
        if disposition == "mixed" and len(hunks_value) < 2:
            raise ValueError(f"{source}: mixed disposition needs at least two material hunks")
        if disposition != "mixed" and hunks_value:
            raise ValueError(f"{source}: hunks are only valid with mixed disposition")

        hunks: list[dict[str, Any]] = []
        seen_labels: set[str] = set()
        for hunk in hunks_value:
            if not isinstance(hunk, dict):
                raise ValueError(f"{source}: every material hunk must be an object")
            label = required_scope_text(hunk, "label", source)
            hunk_source = f"{source} hunk {label}"
            if label in seen_labels:
                raise ValueError(f"{source}: duplicate material hunk label {label}")
            seen_labels.add(label)
            hunk_disposition = hunk.get("disposition")
            if not isinstance(hunk_disposition, str) or hunk_disposition not in SCOPE_HUNK_DISPOSITIONS:
                raise ValueError(
                    f"{hunk_source}: disposition must be one of "
                    f"{sorted(SCOPE_HUNK_DISPOSITIONS)}"
                )
            normalized_hunk = {
                "label": label,
                "disposition": hunk_disposition,
                "acceptance": required_scope_text(hunk, "acceptance", hunk_source),
                "owning_surface": required_scope_text(hunk, "owning_surface", hunk_source),
                "rationale": required_scope_text(hunk, "rationale", hunk_source),
                "evidence": required_scope_evidence(hunk, hunk_source),
            }
            hunks.append(normalized_hunk)
            if hunk_disposition in BLOCKING_SCOPE_DISPOSITIONS:
                blocking_items.append(f"{changed_path}#{label}")

        ready_disposition = disposition == "keep" or (
            disposition == "mixed"
            and all(hunk["disposition"] == "keep" for hunk in hunks)
        )
        if independently_mergeable and ready_disposition:
            if not isinstance(atomicity, str) or not atomicity.strip():
                raise ValueError(
                    f"{source}: independently mergeable ready item needs non-empty atomicity"
                )

        normalized = {
            "path": changed_path,
            "group": required_scope_text(entry, "group", source),
            "disposition": disposition,
            "acceptance": required_scope_text(entry, "acceptance", source),
            "owning_surface": required_scope_text(entry, "owning_surface", source),
            "independently_mergeable": independently_mergeable,
            "atomicity": atomicity.strip() if isinstance(atomicity, str) else None,
            "rationale": required_scope_text(entry, "rationale", source),
            "evidence": required_scope_evidence(entry, source),
            "hunks": hunks,
        }
        closures[changed_path] = normalized
        if disposition in BLOCKING_SCOPE_DISPOSITIONS:
            blocking_items.append(changed_path)

    missing_paths = sorted(expected_paths - closures.keys())
    return {
        "source_provided": True,
        "source": str(path),
        "expected_head": expected_head,
        "declared_head": declared_head,
        "head_matches": declared_head == expected_head,
        "expected_base": expected_base,
        "declared_base": declared_base,
        "base_matches": None if expected_base is None else declared_base == expected_base,
        "expected_merge_base": expected_merge_base,
        "declared_merge_base": declared_merge_base,
        "merge_base_matches": (
            None if expected_merge_base is None else declared_merge_base == expected_merge_base
        ),
        "expected_target": expected_target,
        "missing_paths": missing_paths,
        "blocking_items": blocking_items,
        "rows": [{**item, "scope": closures.get(item["path"])} for item in handwritten],
    }


def scope_closure_state(closure: dict[str, Any]) -> str:
    if not closure["source_provided"]:
        return "not-provided"
    if closure["head_matches"] is False:
        return "stale-head"
    if closure["base_matches"] is False or closure["merge_base_matches"] is False:
        return "stale-surface"
    if closure["missing_paths"]:
        return "incomplete"
    if closure["blocking_items"]:
        return "blocked"
    return "ready"


def closure_target(value: dict[str, Any], path: Path) -> dict[str, Any]:
    return validated_target(value.get("target"), path)


def validate_decision_evidence(
    entry: dict[str, Any], status: str, target: dict[str, Any], path: Path
) -> dict[str, Any] | None:
    subject = entry.get("id") or entry.get("key") or "entry"
    decision = entry.get("decision")
    if decision is None and status not in {"duplicate-on-current-pr", "accepted-by-maintainer"}:
        return None
    if not isinstance(decision, dict):
        raise ValueError(f"{path}: {subject} needs structured decision evidence")
    url = decision.get("url")
    expected_prefix = (
        f"https://github.com/{target['repository']}/pull/{target['pull_request']}"
    )
    comment_url_re = re.compile(
        rf"{re.escape(expected_prefix)}#(?:discussion_r|issuecomment-|pullrequestreview-)\d+"
    )
    if not isinstance(url, str) or not comment_url_re.fullmatch(url):
        raise ValueError(
            f"{path}: {subject} decision URL must target a current-PR comment"
        )
    if status == "accepted-by-maintainer":
        author = decision.get("author")
        association = decision.get("author_association")
        if not isinstance(author, str) or not author.strip():
            raise ValueError(f"{path}: accepted {subject} needs decision author")
        if not isinstance(association, str) or association not in {
            "OWNER",
            "MEMBER",
            "COLLABORATOR",
        }:
            raise ValueError(
                f"{path}: accepted {subject} needs maintainer author_association"
            )
    return decision


def boundary_lead_key(entry: dict[str, Any]) -> str:
    identity = {
        "id": entry.get("id"),
        "path": entry.get("path"),
        "evidence": entry.get("evidence"),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"{entry.get('id', 'lead')}:{digest}"


def load_manual_evidence_closure(
    raw_path: str | None,
    expected_head: str,
    expected_target: dict[str, Any],
    leads: list[dict[str, Any]],
    packages: list[dict[str, str]],
    workflow_candidates: list[dict[str, Any]],
    urls: list[str],
) -> dict[str, Any]:
    expected_target = validated_target(expected_target, "command-line target")
    keyed_by_key: dict[str, dict[str, Any]] = {}
    for item in leads:
        key = boundary_lead_key(item)
        keyed_by_key.setdefault(key, {**item, "key": key})
    keyed_leads = list(keyed_by_key.values())
    leads_by_key = {item["key"]: item for item in keyed_leads}
    runnable_packages = {
        item["package"]: item for item in packages if item["state"] == "runnable"
    }
    expected_urls = set(urls)
    if not raw_path:
        return {
            "source_provided": False,
            "boundary_rows": [
                {**item, "status": "unclassified", "rationale": None, "closure_evidence": []}
                for item in keyed_leads
            ],
            "missing_boundary_keys": sorted(leads_by_key),
            "blocking_boundary_keys": [],
            "ci_tests": {},
            "url_rows": [
                {
                    "url": url,
                    "status": "unclassified",
                    "rationale": None,
                    "closure_evidence": [],
                    "decision": None,
                }
                for url in urls
            ],
            "blocking_urls": [],
        }

    path = Path(raw_path)
    value = load_json_object(path)
    target = validated_target(value.get("target"), path)
    if target != expected_target:
        raise ValueError(f"{path}: manual evidence target does not match command-line target")
    declared_head = value.get("head")
    if declared_head != expected_head:
        raise ValueError(f"{path}: manual evidence must bind the exact current head")

    ci_entries = value.get("ci_tests", [])
    if not isinstance(ci_entries, list):
        raise ValueError(f"{path}: ci_tests must be a list")
    ci_tests: dict[str, dict[str, Any]] = {}
    for entry in ci_entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every ci_tests entry must be an object")
        package = required_scope_text(entry, "package", str(path))
        source = f"{path}: CI test {package}"
        if package not in runnable_packages:
            raise ValueError(f"{source} is not a runnable changed Go test package")
        if runnable_packages[package].get("unverified_test_constraints"):
            raise ValueError(
                f"{source}: build-constrained changed tests need explicit platform/tag execution"
            )
        if package in ci_tests:
            raise ValueError(f"{path}: duplicate CI test package {package}")
        status = entry.get("status")
        if status != "passed":
            raise ValueError(f"{source}: status must be passed")
        command = required_scope_text(entry, "command", source)
        matching_candidates = [
            candidate
            for candidate in workflow_candidates
            if candidate["command"] == command
            and any(
                scope_covers_package(
                    scope,
                    package,
                    candidate.get("nested_module_packages", ()),
                )
                for scope in candidate["scopes"]
            )
        ]
        if not matching_candidates:
            raise ValueError(f"{source}: command does not match a workflow candidate for the package")
        candidates = [
            candidate for candidate in matching_candidates if candidate.get("ci_waivable") is True
        ]
        if not candidates:
            raise ValueError(
                f"{source}: workflow candidate is not a control-flow-free direct, uniquely "
                "identified named-step go test"
            )
        job_url = required_scope_text(entry, "job_url", source)
        expected_job_prefix = (
            f"https://github.com/{target['repository']}/actions/runs/"
        )
        if not re.fullmatch(
            rf"{re.escape(expected_job_prefix)}\d+/job/\d+", job_url
        ):
            raise ValueError(f"{source}: job_url must target a current-repository Actions job")
        ci_tests[package] = {
            "package": package,
            "status": status,
            "command": command,
            "job_url": job_url,
            "evidence": required_scope_evidence(entry, source),
            "workflow_candidates": candidates,
        }

    boundary_entries = value.get("boundary_leads", [])
    if not isinstance(boundary_entries, list):
        raise ValueError(f"{path}: boundary_leads must be a list")
    closures: dict[str, dict[str, Any]] = {}
    blocking_boundary_keys: list[str] = []
    for entry in boundary_entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every boundary_leads entry must be an object")
        key = required_scope_text(entry, "key", str(path))
        source = f"{path}: boundary lead {key}"
        if key not in leads_by_key:
            raise ValueError(f"{source} is not present on the exact review surface")
        if key in closures:
            raise ValueError(f"{path}: duplicate boundary lead closure {key}")
        status = entry.get("status")
        if not isinstance(status, str) or status not in BOUNDARY_STATUSES:
            raise ValueError(f"{source}: status must be one of {sorted(BOUNDARY_STATUSES)}")
        decision = validate_decision_evidence(entry, status, target, path)
        closures[key] = {
            "status": status,
            "rationale": required_scope_text(entry, "rationale", source),
            "evidence": required_scope_evidence(entry, source),
            "decision": decision,
        }
        if status in BLOCKING_BOUNDARY_STATUSES:
            blocking_boundary_keys.append(key)

    boundary_rows = [
        {
            **item,
            "status": closures.get(item["key"], {}).get("status", "unclassified"),
            "rationale": closures.get(item["key"], {}).get("rationale"),
            "closure_evidence": closures.get(item["key"], {}).get("evidence", []),
            "decision": closures.get(item["key"], {}).get("decision"),
        }
        for item in keyed_leads
    ]

    url_entries = value.get("external_urls", [])
    if not isinstance(url_entries, list):
        raise ValueError(f"{path}: external_urls must be a list")
    url_closures: dict[str, dict[str, Any]] = {}
    blocking_urls: list[str] = []
    for entry in url_entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every external_urls entry must be an object")
        url = required_scope_text(entry, "url", str(path))
        source = f"{path}: external URL {url}"
        if url not in expected_urls:
            raise ValueError(f"{source} is not present on the exact review surface")
        if url in url_closures:
            raise ValueError(f"{path}: duplicate external URL closure {url}")
        status = entry.get("status")
        if not isinstance(status, str) or status not in URL_STATUSES:
            raise ValueError(f"{source}: status must be one of {sorted(URL_STATUSES)}")
        decision = validate_decision_evidence(entry, status, target, path)
        url_closures[url] = {
            "status": status,
            "rationale": required_scope_text(entry, "rationale", source),
            "evidence": required_scope_evidence(entry, source),
            "decision": decision,
        }
        if status in BLOCKING_URL_STATUSES:
            blocking_urls.append(url)

    url_rows = [
        {
            "url": url,
            "status": url_closures.get(url, {}).get("status", "unclassified"),
            "rationale": url_closures.get(url, {}).get("rationale"),
            "closure_evidence": url_closures.get(url, {}).get("evidence", []),
            "decision": url_closures.get(url, {}).get("decision"),
        }
        for url in urls
    ]
    return {
        "source_provided": True,
        "boundary_rows": boundary_rows,
        "missing_boundary_keys": [
            item["key"] for item in boundary_rows if item["status"] == "unclassified"
        ],
        "blocking_boundary_keys": blocking_boundary_keys,
        "ci_tests": ci_tests,
        "url_rows": url_rows,
        "blocking_urls": blocking_urls,
    }


def boundary_closure_state(closure: dict[str, Any]) -> str:
    if not closure["boundary_rows"]:
        return "not-applicable"
    if not closure["source_provided"]:
        return "not-provided"
    if closure["missing_boundary_keys"]:
        return "incomplete"
    if closure["blocking_boundary_keys"]:
        return "blocked"
    return "complete"


def external_url_closure_state(
    closure: dict[str, Any], url_results: list[dict[str, Any]]
) -> str:
    rows = closure["url_rows"]
    if not rows:
        return "not-applicable"
    checked = {item["url"]: item for item in url_results}
    if closure["blocking_urls"]:
        return "blocked"
    unresolved = [
        item
        for item in rows
        if item["status"] == "unclassified"
        and checked.get(item["url"], {}).get("ok") is not True
    ]
    if any(checked.get(item["url"], {}).get("ok") is False for item in unresolved):
        return "failed"
    if unresolved:
        return "incomplete" if closure["source_provided"] else "not-provided"
    return "complete"


def github_json(url: str, timeout: float) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentcube-review-harness",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise ValueError(f"cannot verify CI evidence at {url}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"cannot verify CI evidence at {url}: expected a JSON object")
    return value


def verify_ci_tests(
    declarations: dict[str, dict[str, Any]],
    expected_head: str,
    target: dict[str, Any],
    timeout: float,
) -> dict[str, dict[str, Any]]:
    verified: dict[str, dict[str, Any]] = {}
    repository = target["repository"]
    job_url_re = re.compile(
        rf"https://github\.com/{re.escape(repository)}/actions/runs/(?P<run>\d+)/job/(?P<job>\d+)"
    )
    for package, declaration in declarations.items():
        match = job_url_re.fullmatch(declaration["job_url"])
        if not match:
            raise ValueError(f"CI test {package}: invalid job URL")
        run_id = int(match.group("run"))
        job_id = int(match.group("job"))
        api_root = f"https://api.github.com/repos/{repository}/actions"
        run = github_json(f"{api_root}/runs/{run_id}", timeout)
        job = github_json(f"{api_root}/jobs/{job_id}", timeout)
        if run.get("head_sha") != expected_head or run.get("conclusion") != "success":
            raise ValueError(
                f"CI test {package}: Actions run must be successful at exact head {expected_head}"
            )
        if run.get("event") not in CI_WAIVER_RUN_EVENTS:
            raise ValueError(
                f"CI test {package}: Actions event is not eligible for exact-head test evidence"
            )
        if job.get("run_id") != run_id or job.get("conclusion") != "success":
            raise ValueError(f"CI test {package}: Actions job is not successful in the declared run")
        run_path = run.get("path")
        workflow_path = run_path.split("@", 1)[0] if isinstance(run_path, str) else None
        actual_job_name = job.get("name")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        matched_candidate: dict[str, Any] | None = None
        matched_step: dict[str, Any] | None = None
        for candidate in declaration["workflow_candidates"]:
            configured_job_name = candidate["job_name"]
            expected_step_number = candidate["step_index"] + 1
            successful_step = next(
                (
                    step
                    for step in steps
                    if isinstance(step, dict)
                    and step.get("name") == candidate["step"]
                    and step.get("number") == expected_step_number
                    and step.get("conclusion") == "success"
                ),
                None,
            )
            if (
                workflow_path == candidate["workflow"]
                and actual_job_name == configured_job_name
                and candidate.get("exact_head_checkout") is True
                and successful_step is not None
            ):
                matched_candidate = candidate
                matched_step = successful_step
                break
        if matched_candidate is None or matched_step is None:
            raise ValueError(
                f"CI test {package}: successful job does not match the workflow job/step candidate"
            )
        verified[package] = {
            **declaration,
            "source": declaration["job_url"],
            "verified_run_id": run_id,
            "verified_job_id": job_id,
            "verified_job_name": actual_job_name,
            "verified_step_name": matched_step["name"],
            "verified_workflow": workflow_path,
        }
    return verified


def close_finding_ledger(
    findings: list[dict[str, Any]],
    closure_paths: Iterable[str],
    expected_head: str,
    expected_target: dict[str, Any],
    no_carry_forward_findings: bool = False,
) -> dict[str, Any]:
    closure_paths = list(closure_paths)
    expected_target = validated_target(expected_target, "command-line target")
    if no_carry_forward_findings and (findings or closure_paths):
        raise ValueError(
            "--no-carry-forward-findings cannot be combined with a finding ledger or closure"
        )
    if closure_paths and not findings:
        raise ValueError("--finding-closure requires a non-empty --finding-ledger")
    findings_by_id = {item["id"]: item for item in findings}
    finding_ids = set(findings_by_id)
    ledger_snapshots = {
        (item["ledger_id"], item["ledger_version"]): item["ledger_digest"]
        for item in findings
    }
    closures: dict[str, dict[str, Any]] = {}
    declared_heads: list[str] = []
    declared_ledgers: list[dict[str, Any]] = []
    declared_targets: list[dict[str, Any]] = []
    sources: list[str] = []
    for raw_path in closure_paths:
        path = Path(raw_path)
        value = load_json_object(path)
        ledger_id = value.get("ledger_id")
        ledger_version = value.get("ledger_version")
        ledger_digest = value.get("ledger_digest")
        target = closure_target(value, path)
        if target != expected_target:
            raise ValueError(
                f"{path}: closure target {target['repository']}#{target['pull_request']} "
                f"does not match command-line target "
                f"{expected_target['repository']}#{expected_target['pull_request']}"
            )
        declared_head = value.get("head")
        entries = value.get("closures")
        if not isinstance(ledger_id, str) or not ledger_id.strip():
            raise ValueError(f"{path}: ledger_id must be a non-empty string")
        if (
            isinstance(ledger_version, bool)
            or not isinstance(ledger_version, int)
            or ledger_version < 1
        ):
            raise ValueError(f"{path}: ledger_version must be a positive integer")
        ledger_key = (ledger_id.strip(), ledger_version)
        if ledger_key not in ledger_snapshots:
            raise ValueError(
                f"{path}: closure ledger {ledger_key[0]} v{ledger_key[1]} "
                "does not match a supplied finding ledger"
            )
        if not isinstance(ledger_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", ledger_digest):
            raise ValueError(f"{path}: ledger_digest must be a lowercase SHA-256 digest")
        if ledger_digest != ledger_snapshots[ledger_key]:
            raise ValueError(
                f"{path}: closure ledger_digest does not match supplied ledger content"
            )
        if not isinstance(declared_head, str) or not re.fullmatch(r"[0-9a-f]{40}", declared_head):
            raise ValueError(f"{path}: head must be an exact commit SHA")
        if not isinstance(entries, list):
            raise ValueError(f"{path}: closures must be a list")
        declared_heads.append(declared_head)
        declared_ledgers.append(
            {"id": ledger_key[0], "version": ledger_key[1], "digest": ledger_digest}
        )
        declared_targets.append(target)
        if any(item != target for item in declared_targets):
            raise ValueError(f"{path}: all closures must target the same pull request")
        sources.append(str(path))
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{path}: every closure must be an object")
            finding_id = entry.get("id")
            status = entry.get("status")
            evidence = entry.get("evidence")
            if not isinstance(finding_id, str) or not finding_id.strip():
                raise ValueError(f"{path}: every closure needs a non-empty string id")
            if finding_id not in finding_ids:
                raise ValueError(f"{path}: closure references unknown finding {finding_id}")
            finding = findings_by_id[finding_id]
            if (finding["ledger_id"], finding["ledger_version"]) != ledger_key:
                raise ValueError(
                    f"{path}: finding {finding_id} belongs to a different ledger version"
                )
            if finding_id in closures:
                raise ValueError(f"duplicate finding closure: {finding_id}")
            if not isinstance(status, str) or status not in FINDING_STATUSES:
                raise ValueError(
                    f"{path}: finding {finding_id} status must be one of {sorted(FINDING_STATUSES)}"
                )
            if not (
                isinstance(evidence, list)
                and evidence
                and all(isinstance(item, str) and item.strip() for item in evidence)
            ):
                raise ValueError(f"{path}: finding {finding_id} needs non-empty closure evidence")
            decision = validate_decision_evidence(entry, status, target, path)
            closures[finding_id] = {
                "status": status,
                "evidence": evidence,
                "decision": decision,
                "source": str(path),
            }
    rows = [
        {
            **finding,
            "status": closures.get(finding["id"], {}).get("status", "unclassified"),
            "evidence": closures.get(finding["id"], {}).get("evidence", []),
            "decision": closures.get(finding["id"], {}).get("decision"),
            "closure_source": closures.get(finding["id"], {}).get("source"),
        }
        for finding in findings
    ]
    missing_ids = [item["id"] for item in rows if item["status"] == "unclassified"]
    head_matches = None if not declared_heads else all(head == expected_head for head in declared_heads)
    return {
        "mode": "none-declared" if no_carry_forward_findings else "ledger" if findings else "unspecified",
        "expected_target": expected_target,
        "source_provided": bool(findings),
        "closure_source_provided": bool(sources),
        "expected_head": expected_head,
        "declared_heads": declared_heads,
        "declared_ledgers": declared_ledgers,
        "declared_targets": declared_targets,
        "head_matches": head_matches,
        "missing_ids": missing_ids,
        "rows": rows,
    }


def finding_closure_state(closure: dict[str, Any]) -> str:
    if closure["mode"] == "none-declared":
        return "none-declared"
    if not closure["source_provided"]:
        return "not-provided"
    if not closure["closure_source_provided"]:
        return "missing-closure"
    if closure["head_matches"] is False:
        return "stale-head"
    if closure["missing_ids"]:
        return "incomplete"
    return "complete"


def finding_readiness_state(closure: dict[str, Any], closure_state: str) -> dict[str, Any]:
    if closure_state == "none-declared":
        return {"state": "not-applicable", "blocking_ids": []}
    if closure_state == "not-provided":
        return {"state": "not-assessed", "blocking_ids": []}
    if closure_state != "complete":
        return {"state": "incomplete", "blocking_ids": closure["missing_ids"]}
    blocking_ids = [
        item["id"]
        for item in closure["rows"]
        if item["status"] in BLOCKING_FINDING_STATUSES
    ]
    return {
        "state": "blocked" if blocking_ids else "ready",
        "blocking_ids": blocking_ids,
    }


def normalize_go_signature(signature: str) -> str:
    signature = re.sub(r"//.*", "", signature)
    signature = re.sub(r"\s+", " ", signature).strip()
    signature = re.sub(r"\s*([,(\[])\s*", r"\1", signature)
    return re.sub(r"\s*([)\]])", r"\1", signature)


def exported_go_function_signatures(content: str) -> dict[str, str]:
    signatures: dict[str, str] = {}
    lines = content.splitlines()
    index = 0
    while index < len(lines):
        first = lines[index]
        match = GO_FUNC_START_RE.match(first)
        if not match:
            index += 1
            continue
        parts = [first]
        parens = first.count("(") - first.count(")")
        brackets = first.count("[") - first.count("]")
        while "{" not in " ".join(parts) or parens > 0 or brackets > 0:
            index += 1
            if index >= len(lines):
                break
            parts.append(lines[index])
            parens += lines[index].count("(") - lines[index].count(")")
            brackets += lines[index].count("[") - lines[index].count("]")
        signature = " ".join(parts).split("{", 1)[0]
        receiver = normalize_go_signature(match.group("receiver") or "")
        receiver_type = receiver.split()[-1] if receiver else ""
        key = f"{receiver_type}.{match.group('name')}" if receiver_type else match.group("name")
        signatures[key] = normalize_go_signature(signature)
        index += 1
    return signatures


def exported_go_api_leads(
    repo: Path, base: str, head: str, files: list[dict[str, str]]
) -> list[dict[str, str]]:
    leads: list[dict[str, str]] = []
    for item in files:
        path = item["path"]
        if not path.startswith("pkg/") or not path.endswith(".go") or path.endswith("_test.go"):
            continue
        before = review_surface.object_text(repo, base, path)
        after = review_surface.object_text(repo, head, path)
        if not before or not after or is_generated(path, after):
            continue
        old = exported_go_function_signatures(before)
        new = exported_go_function_signatures(after)
        for symbol in sorted(old.keys() & new.keys()):
            if old[symbol] != new[symbol]:
                leads.append(
                    {
                        "id": "exported-go-signature-change",
                        "path": path,
                        "symbol": symbol,
                        "evidence": f"{old[symbol]} -> {new[symbol]}",
                    }
                )
        for symbol in sorted(old.keys() - new.keys()):
            leads.append(
                {
                    "id": "exported-go-symbol-removed",
                    "path": path,
                    "symbol": symbol,
                    "evidence": old[symbol],
                }
            )
    return leads


def kubernetes_codegen_alignment_leads(
    repo: Path, head: str, files: list[dict[str, str]]
) -> list[dict[str, str]]:
    changed_paths = {item["path"] for item in files}
    if not {"go.mod", "hack/update-codegen.sh"} & changed_paths:
        return []
    go_mod = review_surface.object_text(repo, head, "go.mod") or ""
    codegen_script = review_surface.object_text(repo, head, "hack/update-codegen.sh") or ""
    modules = {
        match.group(1): {
            "version": match.group(2),
            "family": (int(match.group("major")), int(match.group("minor"))),
        }
        for match in K8S_MODULE_RE.finditer(go_mod)
    }
    codegen_match = CODEGEN_VERSION_RE.search(codegen_script)
    if not modules or not codegen_match:
        return []
    codegen_family = (int(codegen_match.group("major")), int(codegen_match.group("minor")))
    mismatches = [name for name, value in sorted(modules.items()) if value["family"] != codegen_family]
    if not mismatches:
        return []
    versions = ", ".join(f"{name}={modules[name]['version']}" for name in sorted(modules))
    return [
        {
            "id": "kubernetes-codegen-version-skew",
            "path": "go.mod, hack/update-codegen.sh",
            "evidence": f"{versions}; k8s.io/code-generator={codegen_match.group(1)}",
        }
    ]


def boundary_leads(
    added: dict[str, list[str]], deleted: dict[str, list[str]]
) -> tuple[list[dict[str, str]], list[str]]:
    leads: list[dict[str, str]] = []
    urls: list[str] = []
    for path, lines in sorted(added.items()):
        for line in lines:
            for url in URL_RE.findall(line):
                if "releases/download/" in url or re.search(
                    r"\b(?:curl|wget|kubectl|helm)\b", line
                ):
                    urls.append(url.rstrip(".,;"))
            if VERSION_COMPARE_RE.search(line):
                leads.append(
                    {
                        "id": "lexicographic-version-comparison",
                        "path": path,
                        "evidence": line.strip(),
                    }
                )
            if PERSONAL_PATH_RE.search(line):
                leads.append(
                    {"id": "personal-absolute-path", "path": path, "evidence": line.strip()}
                )
    for path, lines in sorted(deleted.items()):
        removed = [line.strip() for line in lines if re.search(r"\.Validate\s*\(", line)]
        added_validation = any(re.search(r"\.Validate\s*\(", line) for line in added.get(path, []))
        for line in removed if not added_validation else []:
            leads.append({"id": "removed-validation-call", "path": path, "evidence": line})
    return leads, list(dict.fromkeys(urls))


def check_urls(urls: Iterable[str], timeout: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for url in urls:
        if any(marker in url for marker in ("${", "{{", "<", ">")):
            results.append({"url": url, "status": "unresolved-variable", "ok": None})
            continue
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "agentcube-review-harness"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                results.append({"url": url, "status": response.status, "ok": 200 <= response.status < 400})
        except urllib.error.HTTPError as error:
            results.append({"url": url, "status": error.code, "ok": False})
        except (urllib.error.URLError, TimeoutError) as error:
            results.append({"url": url, "status": type(error).__name__, "ok": False})
    return results


def direct_go_environment(
    repo: Path, configured_go_binary: str | None
) -> tuple[str, dict[str, str]]:
    if configured_go_binary is None:
        raise ValueError(
            "--run-go-tests requires --go-binary with an explicitly reviewed absolute path"
        )
    requested = Path(configured_go_binary)
    if not requested.is_absolute():
        raise ValueError("--go-binary must be an absolute path")
    try:
        go_binary = requested.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"--go-binary cannot be resolved: {error}") from error
    if not go_binary.is_file() or not os.access(go_binary, os.X_OK):
        raise ValueError("--go-binary must resolve to an executable file")
    try:
        go_binary.relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError("--run-go-tests refuses a Go binary from inside the review worktree")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GO", "CGO_"))
        and key
        not in {
            "AR",
            "BASH_ENV",
            "CC",
            "CGO_ENABLED",
            "CXX",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "ENV",
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
            "PKG_CONFIG",
        }
    }
    environment["GOENV"] = "off"
    environment["GOTOOLCHAIN"] = "local"
    environment["PATH"] = os.pathsep.join(
        dict.fromkeys([str(go_binary.parent), *os.defpath.split(os.pathsep)])
    )
    probe_environment = dict(environment)
    probe_environment["GOWORK"] = "off"
    platform = subprocess.run(
        [str(go_binary), "env", "GOHOSTOS", "GOHOSTARCH"],
        cwd=repo,
        env=probe_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    host = platform.stdout.splitlines()
    if platform.returncode != 0 or host != ["linux", "amd64"]:
        observed = "/".join(host) if host else f"exit {platform.returncode}"
        raise ValueError(
            "--run-go-tests requires a reviewed linux/amd64 Go host; "
            f"observed {observed}"
        )
    environment["GOOS"] = "linux"
    environment["GOARCH"] = "amd64"
    return str(go_binary), environment


def tracked_go_workspaces(repo: Path, head: str) -> set[str]:
    names = git(repo, "ls-tree", "-r", "-z", "--name-only", head).stdout
    return {
        name
        for name in names.split("\0")
        if name and Path(name).name == "go.work"
    }


def governing_go_workspace(
    repo: Path, working_directory: Path, workspace_paths: set[str]
) -> str:
    relative = working_directory.relative_to(repo)
    current = relative
    while True:
        candidate_path = (
            "go.work" if str(current) == "." else f"{current.as_posix()}/go.work"
        )
        if candidate_path in workspace_paths:
            candidate = repo / candidate_path
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError(
                    f"tracked governing workspace is not a regular file: {candidate_path}"
                )
            return str(candidate.resolve())
        if str(current) == ".":
            return "off"
        current = current.parent


def materialize_exact_head(repo: Path, head: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    entries = git(repo, "ls-tree", "-r", "-z", head).stdout
    for entry in entries.split("\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split("\t", 1)
            mode, object_type, object_id = metadata.split()
        except ValueError as error:
            raise ValueError("cannot parse exact-head tree entry") from error
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(
                f"direct test materialization rejects unsupported {mode} {object_type}: {raw_path}"
            )
        relative = PurePosixPath(raw_path)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError(f"unsafe exact-head tree path: {raw_path}")
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", object_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if blob.returncode != 0:
            detail = blob.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"cannot materialize exact-head blob {object_id}: {detail}")
        target.write_bytes(blob.stdout)
        target.chmod(0o755 if mode == "100755" else 0o644)


def require_exact_tree_directory(
    exact_tree: Path, base: Path, raw_path: str, source: str
) -> Path:
    candidate = Path(raw_path)
    unresolved = candidate if candidate.is_absolute() else base / candidate
    normalized = unresolved.resolve(strict=False)
    try:
        normalized.relative_to(exact_tree)
    except ValueError as error:
        raise ValueError(
            f"{source} points outside the materialized exact-head tree: {raw_path}"
        ) from error
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"{source} cannot be resolved: {raw_path}: {error}") from error
    try:
        resolved.relative_to(exact_tree)
    except ValueError as error:
        raise ValueError(
            f"{source} points outside the materialized exact-head tree: {raw_path}"
        ) from error
    if not resolved.is_dir():
        raise ValueError(f"{source} is not a module directory: {raw_path}")
    return resolved


def json_object_stream(text: str, source: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = 0
    values: list[dict[str, Any]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            value, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as error:
            raise ValueError(f"{source} returned invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{source} returned a non-object JSON value")
        values.append(value)
    return values


def validate_go_workspace_paths(
    go_binary: str,
    exact_tree: Path,
    go_workspace: str,
    environment: dict[str, str],
) -> None:
    if go_workspace == "off":
        return
    workspace = Path(go_workspace)
    edit_environment = dict(environment)
    edit_environment["GOWORK"] = "off"
    process = subprocess.run(
        [go_binary, "work", "edit", "-json", go_workspace],
        cwd=workspace.parent,
        env=edit_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ValueError(f"cannot parse governing go.work: {detail}")
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"go work edit returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("go work edit returned a non-object JSON value")
    uses = value.get("Use") or []
    replaces = value.get("Replace") or []
    if not isinstance(uses, list) or not isinstance(replaces, list):
        raise ValueError("go work edit returned invalid Use/Replace collections")
    for item in uses:
        if not isinstance(item, dict) or not isinstance(item.get("DiskPath"), str):
            raise ValueError("go work edit returned an invalid workspace use path")
        require_exact_tree_directory(
            exact_tree, workspace.parent, item["DiskPath"], "go.work use"
        )
    for item in replaces:
        new = item.get("New") if isinstance(item, dict) else None
        if not isinstance(new, dict) or new.get("Version"):
            continue
        local_path = new.get("DiskPath") or new.get("Path")
        if isinstance(local_path, str):
            require_exact_tree_directory(
                exact_tree, workspace.parent, local_path, "go.work replace"
            )


def direct_go_module_mode(working_directory: Path, go_workspace: str) -> str:
    vendor_root = (
        Path(go_workspace).parent if go_workspace != "off" else working_directory
    )
    return "vendor" if (vendor_root / "vendor" / "modules.txt").is_file() else "readonly"


def validate_go_module_graph(
    go_binary: str,
    exact_tree: Path,
    working_directory: Path,
    go_workspace: str,
    module_mode: str,
    environment: dict[str, str],
) -> None:
    validate_go_workspace_paths(go_binary, exact_tree, go_workspace, environment)
    process = subprocess.run(
        [go_binary, "list", f"-mod={module_mode}", "-m", "-json", "all"],
        cwd=working_directory,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ValueError(f"cannot bind direct Go module graph to exact head: {detail}")
    for module in json_object_stream(process.stdout, "go list -m -json all"):
        if module.get("Main") is True and isinstance(module.get("Dir"), str):
            require_exact_tree_directory(
                exact_tree, working_directory, module["Dir"], "main/workspace module"
            )
        replacement = module.get("Replace")
        if (
            isinstance(replacement, dict)
            and not replacement.get("Version")
            and isinstance(replacement.get("Dir"), str)
        ):
            require_exact_tree_directory(
                exact_tree,
                working_directory,
                replacement["Dir"],
                "local module replacement",
            )


def run_go_tests_from_exact_tree(
    repo: Path,
    workspace_paths: set[str],
    coverage: list[dict[str, Any]],
    go_binary: str,
    base_environment: dict[str, str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    validated_modules: set[tuple[str, str, str]] = set()
    for item in coverage:
        if item["state"] != "runnable" or item["ci_covered"]:
            continue
        if item.get("unverified_test_constraints"):
            constraints = "; ".join(
                f"{entry['path']}: {entry['reason']}"
                for entry in item["unverified_test_constraints"]
            )
            results.append(
                {
                    "package": item["package"],
                    "command": "platform-specific go test required",
                    "module_root": item.get("module_root", "."),
                    "go_binary": go_binary,
                    "returncode": 2,
                    "duration_seconds": 0.0,
                    "output_tail": (
                        "Build-constrained changed tests require explicit compatible platform/tag "
                        f"execution: {constraints}"
                    ),
                }
            )
            continue
        started = time.monotonic()
        module_root = item.get("module_root", ".")
        package_path = item["package"][2:] if item["package"].startswith("./") else "."
        relative_package_path = Path(package_path).relative_to(module_root)
        direct_package = (
            "."
            if str(relative_package_path) == "."
            else f"./{relative_package_path.as_posix()}"
        )
        working_directory = repo if module_root == "." else repo / module_root
        go_workspace = governing_go_workspace(repo, working_directory, workspace_paths)
        go_workspace_label = (
            "off"
            if go_workspace == "off"
            else str(Path(go_workspace).relative_to(repo))
        )
        environment = dict(base_environment)
        environment["GOWORK"] = go_workspace
        module_mode = direct_go_module_mode(working_directory, go_workspace)
        module_key = (module_root, go_workspace_label, module_mode)
        if module_key not in validated_modules:
            validate_go_module_graph(
                go_binary,
                repo,
                working_directory,
                go_workspace,
                module_mode,
                environment,
            )
            validated_modules.add(module_key)
        command = [
            go_binary,
            "test",
            f"-mod={module_mode}",
            direct_package,
            "-count=1",
        ]
        process = subprocess.run(
            command,
            cwd=working_directory,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        output = process.stdout
        results.append(
            {
                "package": item["package"],
                "command": shlex.join(command),
                "module_root": module_root,
                "go_binary": go_binary,
                "go_workspace": go_workspace_label,
                "returncode": process.returncode,
                "duration_seconds": round(time.monotonic() - started, 3),
                "output_tail": output[-6000:],
            }
        )
    return results


def run_go_tests(
    repo: Path,
    head: str,
    coverage: list[dict[str, Any]],
    configured_go_binary: str | None = None,
) -> list[dict[str, Any]]:
    repo = repo.resolve()
    expected = git(repo, "rev-parse", head).stdout.strip()
    actual = git(repo, "rev-parse", "HEAD").stdout.strip()
    if expected != actual:
        raise ValueError(
            f"--run-go-tests requires the worktree HEAD ({actual}) to equal --head ({expected})"
        )
    dirty = git(repo, "status", "--porcelain", "--untracked-files=all").stdout.strip()
    if dirty:
        raise ValueError(
            "--run-go-tests requires a clean worktree; use a detached temporary "
            "worktree for exact-head evidence"
        )
    go_binary, base_environment = direct_go_environment(repo, configured_go_binary)
    workspace_paths = tracked_go_workspaces(repo, head)
    with tempfile.TemporaryDirectory(prefix="agentcube-final-head-") as directory:
        exact_tree = Path(directory) / "tree"
        materialize_exact_head(repo, head, exact_tree)
        return run_go_tests_from_exact_tree(
            exact_tree,
            workspace_paths,
            coverage,
            go_binary,
            base_environment,
        )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).resolve()
    surface = review_surface.build_report(repo, args.base, args.head)
    base_sha = surface["base"]["sha"]
    head_sha = surface["head"]["sha"]
    target = {
        "repository": args.target_repository,
        "pull_request": args.target_pull_request,
    }
    handwritten = handwritten_files(repo, head_sha, surface["changed_files"])
    added, deleted = changed_lines(repo, base_sha, head_sha, surface["changed_files"])
    packages = changed_go_test_packages(surface["changed_files"], repo, head_sha)
    workflow_evidence = workflow_test_evidence(repo, head_sha)
    leads, urls = boundary_leads(added, deleted)
    leads.extend(exported_go_api_leads(repo, base_sha, head_sha, surface["changed_files"]))
    leads.extend(kubernetes_codegen_alignment_leads(repo, head_sha, surface["changed_files"]))
    manual_evidence = load_manual_evidence_closure(
        args.scope_closure,
        head_sha,
        target,
        leads,
        packages,
        workflow_evidence,
        urls,
    )
    manual_evidence["ci_tests"] = verify_ci_tests(
        manual_evidence["ci_tests"],
        head_sha,
        target,
        args.ci_timeout,
    )
    boundary_state = boundary_closure_state(manual_evidence)
    coverage = package_coverage(packages, workflow_evidence, manual_evidence["ci_tests"])
    scope_closure = load_scope_closure(
        args.scope_closure,
        handwritten,
        head_sha,
        target,
        base_sha,
        surface["merge_base"],
    )
    scope_state = scope_closure_state(scope_closure)
    acceptance = acceptance_candidates(
        [Path(path) for path in args.acceptance_file], args.acceptance_note
    )
    findings = load_finding_ledger(args.finding_ledger)
    finding_closure = close_finding_ledger(
        findings,
        args.finding_closure,
        head_sha,
        target,
        args.no_carry_forward_findings,
    )
    finding_state = finding_closure_state(finding_closure)
    finding_readiness = finding_readiness_state(finding_closure, finding_state)
    url_results = check_urls(urls, args.url_timeout) if args.check_urls else []
    external_url_state = external_url_closure_state(manual_evidence, url_results)
    test_results = (
        run_go_tests(repo, head_sha, coverage, args.go_binary)
        if args.run_go_tests
        else []
    )
    uncovered = [item["package"] for item in coverage if item["state"] == "runnable" and not item["ci_covered"]]
    return {
        "notice": "Harness output is an evidence ledger, not an automated review conclusion.",
        "surface": surface,
        "acceptance": {
            "source_provided": bool(args.acceptance_file or args.acceptance_note),
            "candidates": acceptance,
        },
        "finding_ledger": finding_closure,
        "handwritten_files": handwritten,
        "scope_closure": scope_closure,
        "manual_evidence_closure": manual_evidence,
        "changed_go_test_coverage": coverage,
        "workflow_go_test_evidence": workflow_evidence,
        "uncovered_changed_go_test_packages": uncovered,
        "boundary_leads": manual_evidence["boundary_rows"],
        "external_urls": urls,
        "url_checks": url_results,
        "go_test_results": test_results,
        "gate": {
            "acceptance_context": "present" if acceptance else "missing",
            "changed_test_ci_coverage": "complete" if not uncovered else "incomplete",
            "changed_test_execution": (
                "not-run"
                if not args.run_go_tests
                else "passed"
                if all(item["returncode"] == 0 for item in test_results)
                else "failed"
            ),
            "external_url_validation": (
                "not-run"
                if not args.check_urls
                else "failed"
                if any(item["ok"] is False for item in url_results)
                else "incomplete"
                if any(item["ok"] is None for item in url_results)
                else "passed"
            ),
            "external_url_closure": external_url_state,
            "finding_ledger_closure": finding_state,
            "finding_readiness": finding_readiness,
            "scope_closure": scope_state,
            "boundary_closure": boundary_state,
            "structural_mergeability": (
                "mergeable" if surface["structurally_mergeable"] else "conflicted"
            ),
            "manual_closure_required": bool(
                not acceptance
                or uncovered
                or leads
                or urls
                or scope_state != "ready"
                or boundary_state not in {"not-applicable", "complete"}
                or external_url_state not in {"not-applicable", "complete"}
                or finding_state not in {"none-declared", "complete"}
            ),
        },
    }


def markdown(report: dict[str, Any]) -> str:
    surface = report["surface"]
    gate = report["gate"]
    lines = [
        "# AgentCube Final-Head Review Ledger",
        "",
        f"> {report['notice']}",
        "",
        f"- Base: `{surface['base']['ref']}` (`{surface['base']['sha']}`)",
        f"- Head: `{surface['head']['ref']}` (`{surface['head']['sha']}`)",
        f"- Target PR: `{report['finding_ledger']['expected_target']['repository']}"
        f"#{report['finding_ledger']['expected_target']['pull_request']}`",
        f"- Changed files: `{surface['changed_file_count']}`",
        f"- Structural mergeability: `{gate['structural_mergeability']}`",
        f"- Acceptance context: `{gate['acceptance_context']}`",
        f"- Changed-test CI coverage: `{gate['changed_test_ci_coverage']}`",
        f"- Changed-test execution: `{gate['changed_test_execution']}`",
        f"- External URL validation: `{gate['external_url_validation']}`",
        f"- External URL closure: `{gate['external_url_closure']}`",
        f"- PR-scope closure: `{gate['scope_closure']}`",
        f"- Boundary-lead closure: `{gate['boundary_closure']}`",
        f"- Carry-forward finding closure: `{gate['finding_ledger_closure']}`",
        f"- Finding readiness: `{gate['finding_readiness']['state']}`",
        "",
        "## Acceptance Contract",
        "",
    ]
    candidates = report["acceptance"]["candidates"]
    lines.extend([f"- [ ] {item}" for item in candidates] or ["- [ ] No acceptance source supplied."])
    lines.extend(["", "## Carry-Forward Finding Ledger", ""])
    finding_rows = report["finding_ledger"]["rows"]
    if not finding_rows:
        if report["finding_ledger"]["mode"] == "none-declared":
            lines.append("- Reviewer explicitly declared no carry-forward findings.")
        else:
            lines.append("- No predecessor/current finding ledger supplied.")
    else:
        lines.append("| ID | Summary | Paths | Current-head classification | Evidence |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in finding_rows:
            paths = ", ".join(f"`{path}`" for path in item["paths"]) or "-"
            evidence = "<br>".join(item["evidence"]) or "[ ] missing"
            lines.append(
                f"| `{item['id']}` | {item['summary']} | {paths} | "
                f"`{item['status']}` | {evidence} |"
            )
        if report["finding_ledger"]["declared_heads"]:
            heads = ", ".join(f"`{head}`" for head in report["finding_ledger"]["declared_heads"])
            ledgers = ", ".join(
                f"`{item['id']}` v{item['version']} (`{item['digest'][:12]}`)"
                for item in report["finding_ledger"]["declared_ledgers"]
            )
            lines.append("")
            lines.append(
                f"Closure ledger(s): {ledgers}; head(s): {heads}; "
                f"expected `{report['finding_ledger']['expected_head']}`."
            )
        if gate["finding_readiness"]["blocking_ids"]:
            blocking = ", ".join(
                f"`{finding_id}`" for finding_id in gate["finding_readiness"]["blocking_ids"]
            )
            lines.append("")
            lines.append(f"Blocking current-head findings: {blocking}.")
    lines.extend(["", "## PR Scope Closure", ""])
    scope_closure = report["scope_closure"]
    if scope_closure["source_provided"]:
        lines.append(
            f"Closure base/head/merge-base: `{scope_closure['declared_base']}` / "
            f"`{scope_closure['declared_head']}` / `{scope_closure['declared_merge_base']}`; "
            f"expected `{scope_closure['expected_base']}` / `{scope_closure['expected_head']}` / "
            f"`{scope_closure['expected_merge_base']}`."
        )
    else:
        lines.append("- [ ] No exact-head scope closure supplied.")
    if scope_closure["missing_paths"]:
        missing = ", ".join(f"`{path}`" for path in scope_closure["missing_paths"])
        lines.append(f"- Missing hand-written paths: {missing}")
    if scope_closure["blocking_items"]:
        blocking = ", ".join(f"`{item}`" for item in scope_closure["blocking_items"])
        lines.append(f"- Blocking scope items: {blocking}")
    lines.extend(
        [
            "",
            "| Status | Path | Group | Acceptance | Disposition | Owning surface | Scope closure |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in scope_closure["rows"]:
        scope = item["scope"]
        if scope is None:
            lines.append(
                f"| `{item['status']}` | `{item['path']}` | - | - | `unclassified` | - | "
                "[ ] acceptance / rationale / evidence |"
            )
            continue
        closure = f"{scope['rationale']}<br>Evidence: {'; '.join(scope['evidence'])}"
        if scope["independently_mergeable"]:
            closure += "<br>Independently mergeable: yes"
        if scope["atomicity"]:
            closure += f"<br>Atomicity: {scope['atomicity']}"
        lines.append(
            f"| `{item['status']}` | `{item['path']}` | {scope['group']} | "
            f"{scope['acceptance']} | `{scope['disposition']}` | "
            f"{scope['owning_surface']} | {closure} |"
        )
        for hunk in scope["hunks"]:
            lines.append(
                f"|  | `# {hunk['label']}` | material hunk | {hunk['acceptance']} | "
                f"`{hunk['disposition']}` | {hunk['owning_surface']} | "
                f"{hunk['rationale']}<br>Evidence: {'; '.join(hunk['evidence'])} |"
            )
    lines.extend(["", "## Changed Go Test Packages", ""])
    if not report["changed_go_test_coverage"]:
        lines.append("- No changed Go test packages.")
    for item in report["changed_go_test_coverage"]:
        state = "covered" if item["ci_covered"] else "not proven by CI"
        lines.append(f"- `{item['package']}`: {state}; state `{item['state']}`")
        for constraint in item.get("unverified_test_constraints", []):
            lines.append(
                f"  - build-constrained changed test: `{constraint['path']}` "
                f"({constraint['reason']}); explicit compatible execution required"
            )
        for candidate in item["workflow_candidates"]:
            candidate_kind = "CI-waivable" if candidate["ci_waivable"] else "lead-only"
            lines.append(
                f"  - workflow candidate ({candidate_kind}): `{candidate['source']}`: "
                f"`{candidate['command']}`"
            )
        if item["ci_closure"]:
            closure = item["ci_closure"]
            lines.append(
                f"  - verified PASS: `{closure['source']}`: `{closure['command']}`; "
                f"evidence: {'; '.join(closure['evidence'])}"
            )
    lines.extend(["", "## Boundary Leads", ""])
    if not report["boundary_leads"]:
        lines.append("- None from deterministic diff checks.")
    for item in report["boundary_leads"]:
        rationale = item["rationale"] or "[ ] missing rationale"
        evidence = "; ".join(item["closure_evidence"]) or "[ ] missing closure evidence"
        lines.append(
            f"- `{item['key']}` (`{item['status']}`) in `{item['path']}`: "
            f"`{item['evidence']}`; {rationale}; closure evidence: {evidence}"
        )
    lines.extend(["", "## External URLs", ""])
    if not report["external_urls"]:
        lines.append("- No added external URLs.")
    checked = {item["url"]: item for item in report["url_checks"]}
    url_rows = {item["url"]: item for item in report["manual_evidence_closure"]["url_rows"]}
    for url in report["external_urls"]:
        check_status = checked.get(url, {}).get("status", "not checked")
        row = url_rows[url]
        closure_status = (
            "auto-verified" if checked.get(url, {}).get("ok") is True else row["status"]
        )
        rationale = row["rationale"] or "[ ] missing rationale"
        evidence = "; ".join(row["closure_evidence"]) or "[ ] missing closure evidence"
        lines.append(
            f"- check `{check_status}` / closure `{closure_status}`: {url}; "
            f"{rationale}; closure evidence: {evidence}"
        )
    lines.extend(["", "## Direct Test Results", ""])
    if not report["go_test_results"]:
        lines.append("- Not run.")
    for item in report["go_test_results"]:
        result = "PASS" if item["returncode"] == 0 else "FAIL"
        lines.append(
            f"- `{result}` `{item['command']}` ({item['duration_seconds']}s, exit {item['returncode']})"
        )
        if item["returncode"] != 0:
            lines.extend(["", "```text", item["output_tail"].rstrip(), "```"])
    lines.extend(
        [
            "",
            "## Closure Rule",
            "",
            "Do not call the final-head review complete until every acceptance item is mapped, the exact-head "
            "PR-scope closure is bound to the exact base/head/merge-base and ready with no "
            "remove/separate/unresolved item, the surface is structurally mergeable, every carry-forward "
            "finding is classified against the exact current head, every changed test package has verified "
            "CI PASS evidence or is run directly, and every boundary lead or external URL is resolved or "
            "explicitly classified.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Checked-out repository root")
    parser.add_argument("--base", required=True, help="Base ref")
    parser.add_argument("--head", default="HEAD", help="Exact head ref")
    parser.add_argument(
        "--target-repository",
        required=True,
        help="Expected pull-request repository in owner/repo form",
    )
    parser.add_argument(
        "--target-pull-request",
        required=True,
        type=int,
        help="Expected pull-request number",
    )
    parser.add_argument(
        "--acceptance-file", action="append", default=[], help="Issue/proposal text file; repeatable"
    )
    parser.add_argument(
        "--acceptance-note", action="append", default=[], help="Explicit acceptance item; repeatable"
    )
    parser.add_argument(
        "--scope-closure",
        help=(
            "Exact base/head/merge-base JSON closure for scope, boundary/URL leads, and CI evidence"
        ),
    )
    finding_mode = parser.add_mutually_exclusive_group(required=True)
    finding_mode.add_argument(
        "--finding-ledger",
        action="append",
        default=[],
        help="Versioned JSON finding ledger to carry forward; repeatable",
    )
    finding_mode.add_argument(
        "--no-carry-forward-findings",
        action="store_true",
        help="Explicitly attest that this review has no predecessor findings to carry forward",
    )
    parser.add_argument(
        "--finding-closure",
        action="append",
        default=[],
        help="Exact-head JSON closure for carried findings; repeatable",
    )
    parser.add_argument(
        "--run-go-tests",
        action="store_true",
        help="Run changed Go test packages without verified exact-head CI PASS closure",
    )
    parser.add_argument(
        "--go-binary",
        help="Reviewed absolute Go binary path required by --run-go-tests",
    )
    parser.add_argument(
        "--ci-timeout", type=float, default=10.0, help="GitHub API timeout for CI evidence"
    )
    parser.add_argument("--check-urls", action="store_true", help="HEAD-check literal added external URLs")
    parser.add_argument("--url-timeout", type=float, default=10.0, help="URL timeout in seconds")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if args.no_carry_forward_findings and args.finding_closure:
        parser.error("--finding-closure cannot be used with --no-carry-forward-findings")
    if args.run_go_tests and not args.go_binary:
        parser.error("--run-go-tests requires --go-binary")
    if args.go_binary and not args.run_go_tests:
        parser.error("--go-binary requires --run-go-tests")

    try:
        report = build_report(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(markdown(report))
    if any(item["returncode"] != 0 for item in report["go_test_results"]):
        return 1
    if report["gate"]["finding_ledger_closure"] not in {"none-declared", "complete"}:
        return 1
    if report["gate"]["finding_readiness"]["state"] == "blocked":
        return 1
    if report["gate"]["scope_closure"] != "ready":
        return 1
    if report["gate"]["acceptance_context"] != "present":
        return 1
    if (
        report["uncovered_changed_go_test_packages"]
        and report["gate"]["changed_test_execution"] != "passed"
    ):
        return 1
    if report["gate"]["external_url_closure"] not in {"not-applicable", "complete"}:
        return 1
    if report["gate"]["boundary_closure"] not in {"not-applicable", "complete"}:
        return 1
    if report["gate"]["structural_mergeability"] != "mergeable":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
