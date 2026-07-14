#!/usr/bin/env python3
"""Produce deterministic AgentCube diff facts and heuristic review leads."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


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


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def object_text(repo: Path, ref: str, path: str) -> str | None:
    result = git(repo, "show", f"{ref}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def parse_changed_files(raw: str) -> list[dict[str, str]]:
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


def dependency_runtime_versions(repo: Path, head: str) -> dict[str, str | None]:
    go_mod = object_text(repo, head, "go.mod") or ""
    e2e_script = object_text(repo, head, "test/e2e/run_e2e.sh") or ""
    return extract_agent_sandbox_versions(go_mod, e2e_script)


def build_report(repo: Path, base: str, head: str) -> dict[str, Any]:
    base_sha = git(repo, "rev-parse", base).stdout.strip()
    head_sha = git(repo, "rev-parse", head).stdout.strip()
    merge_base = git(repo, "merge-base", base, head).stdout.strip()
    base_is_ancestor = git(repo, "merge-base", "--is-ancestor", base, head, check=False).returncode == 0

    merge_result = git(repo, "merge-tree", "--write-tree", base, head, check=False)
    structurally_mergeable = merge_result.returncode == 0

    raw_files = git(repo, "diff", "--name-status", f"{base}...{head}").stdout
    files = parse_changed_files(raw_files)
    category_map: dict[str, list[str]] = {}
    for item in files:
        for category in categories_for(item["path"]):
            category_map.setdefault(category, []).append(item["path"])

    leads: list[dict[str, str]] = []
    versions = dependency_runtime_versions(repo, head)
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
        "review_leads": leads,
        "diff_stat": git(repo, "diff", "--stat", f"{base}...{head}").stdout.rstrip(),
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
