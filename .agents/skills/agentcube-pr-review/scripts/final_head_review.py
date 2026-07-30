#!/usr/bin/env python3
"""Build an evidence ledger for an AgentCube final-head PR review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import review_surface


GENERATED_PREFIXES = (
    "client-go/",
    "manifests/charts/base/crds/",
)
GENERATED_FILENAMES = {"go.sum", "package-lock.json", "pnpm-lock.yaml", "uv.lock"}
URL_RE = re.compile(r"https?://[^\s<>()\[\]`\"']+")
GO_SCOPE_RE = re.compile(
    r"(?<![=\w])(\./(?:\.\.\.|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*(?:/\.\.\.)?))"
    r"(?=$|[\s'\";|&])"
)
VERSION_COMPARE_RE = re.compile(
    r"\[\[[^\n]*(?:VERSION|version|v[0-9]+\.)[^\n]*\s(?:<|>)\s[^\n]*\]\]"
)
PERSONAL_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|home)[\\/]|/(?:Users|home)/[^/$\s]+/)")
ACCEPTANCE_RE = re.compile(
    r"(?:\[[ xX]\]|\bmust\b|\brequired\b|\bshould\b|\bupgrade\b|\bmigrat\w*\b|"
    r"\bpreserv\w*\b|\bcompatib\w*\b)",
    re.IGNORECASE,
)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return review_surface.git(repo, *args, check=check)


def changed_lines(repo: Path, base: str, head: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return added and deleted diff lines grouped by the new-side path."""
    result = git(repo, "diff", "--no-ext-diff", "--unified=0", f"{base}...{head}")
    added: dict[str, list[str]] = defaultdict(list)
    deleted: dict[str, list[str]] = defaultdict(list)
    path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ "):
            marker = line[4:]
            path = marker[2:] if marker.startswith("b/") else None
        elif path and line.startswith("+") and not line.startswith("+++"):
            added[path].append(line[1:])
        elif path and line.startswith("-") and not line.startswith("---"):
            deleted[path].append(line[1:])
    return dict(added), dict(deleted)


def is_generated(path: str, content: str | None) -> bool:
    if path.startswith(GENERATED_PREFIXES):
        return True
    if Path(path).name in GENERATED_FILENAMES:
        return True
    if Path(path).name.startswith("zz_generated."):
        return True
    return bool(content and "Code generated" in content[:500] and "DO NOT EDIT" in content[:500])


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


def changed_go_test_packages(files: list[dict[str, str]]) -> list[dict[str, str]]:
    packages: dict[str, dict[str, str]] = {}
    for item in files:
        path = item["path"]
        if not path.endswith("_test.go"):
            continue
        directory = str(Path(path).parent)
        package = "." if directory == "." else f"./{directory}"
        state = "deleted" if item["status"].startswith("D") else "runnable"
        packages[package] = {"package": package, "state": state}
    return [packages[key] for key in sorted(packages)]


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
    match = re.search(r"\bgo\s+test\b(?P<args>.*)", command)
    if not match:
        return []
    return sorted(set(GO_SCOPE_RE.findall(match.group("args"))))


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
    for name in sorted(path for path in names if path.endswith((".yml", ".yaml"))):
        content = review_surface.object_text(repo, head, name) or ""
        for line in logical_lines(content):
            scopes = go_test_scopes(line)
            if scopes:
                evidence.append({"source": name, "command": line, "scopes": scopes})
            for target in re.findall(r"\bmake\s+([A-Za-z0-9_.-]+)", line):
                for recipe in resolve_make_recipes(target, targets):
                    make_scopes = go_test_scopes(recipe)
                    if make_scopes:
                        evidence.append(
                            {
                                "source": f"{name} -> Makefile:{target}",
                                "command": recipe,
                                "scopes": make_scopes,
                            }
                        )
                    for script in shell_script_paths(recipe):
                        script_content = review_surface.object_text(repo, head, script) or ""
                        for script_line in logical_lines(script_content):
                            script_scopes = go_test_scopes(script_line)
                            if script_scopes:
                                evidence.append(
                                    {
                                        "source": f"{name} -> Makefile:{target} -> {script}",
                                        "command": script_line,
                                        "scopes": script_scopes,
                                    }
                                )
    unique: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    for item in evidence:
        key = (item["source"], item["command"], tuple(item["scopes"]))
        unique[key] = item
    return [unique[key] for key in sorted(unique)]


def scope_covers_package(scope: str, package: str) -> bool:
    if scope == "./...":
        return True
    if scope.endswith("/..."):
        prefix = scope[:-4].rstrip("/")
        return package == prefix or package.startswith(f"{prefix}/")
    return scope == package


def package_coverage(
    packages: list[dict[str, str]], evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for item in packages:
        matches = [
            entry
            for entry in evidence
            if item["state"] == "runnable"
            and any(scope_covers_package(scope, item["package"]) for scope in entry["scopes"])
        ]
        coverage.append({**item, "ci_covered": bool(matches), "evidence": matches})
    return coverage


def acceptance_candidates(files: Iterable[Path], notes: Iterable[str]) -> list[str]:
    candidates = [note.strip() for note in notes if note.strip()]
    for path in files:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and ACCEPTANCE_RE.search(line):
                candidates.append(line)
    return list(dict.fromkeys(candidates))


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


def run_go_tests(repo: Path, head: str, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = git(repo, "rev-parse", head).stdout.strip()
    actual = git(repo, "rev-parse", "HEAD").stdout.strip()
    if expected != actual:
        raise ValueError(
            f"--run-go-tests requires the worktree HEAD ({actual}) to equal --head ({expected})"
        )
    results: list[dict[str, Any]] = []
    for item in coverage:
        if item["state"] != "runnable" or item["ci_covered"]:
            continue
        started = time.monotonic()
        command = ["go", "test", item["package"], "-count=1"]
        process = subprocess.run(
            command,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        output = process.stdout
        results.append(
            {
                "package": item["package"],
                "command": " ".join(command),
                "returncode": process.returncode,
                "duration_seconds": round(time.monotonic() - started, 3),
                "output_tail": output[-6000:],
            }
        )
    return results


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).resolve()
    surface = review_surface.build_report(repo, args.base, args.head)
    added, deleted = changed_lines(repo, args.base, args.head)
    packages = changed_go_test_packages(surface["changed_files"])
    workflow_evidence = workflow_test_evidence(repo, args.head)
    coverage = package_coverage(packages, workflow_evidence)
    leads, urls = boundary_leads(added, deleted)
    acceptance = acceptance_candidates(
        [Path(path) for path in args.acceptance_file], args.acceptance_note
    )
    url_results = check_urls(urls, args.url_timeout) if args.check_urls else []
    test_results = run_go_tests(repo, args.head, coverage) if args.run_go_tests else []
    uncovered = [item["package"] for item in coverage if item["state"] == "runnable" and not item["ci_covered"]]
    return {
        "notice": "Harness output is an evidence ledger, not an automated review conclusion.",
        "surface": surface,
        "acceptance": {
            "source_provided": bool(args.acceptance_file or args.acceptance_note),
            "candidates": acceptance,
        },
        "handwritten_files": handwritten_files(repo, args.head, surface["changed_files"]),
        "changed_go_test_coverage": coverage,
        "workflow_go_test_evidence": workflow_evidence,
        "uncovered_changed_go_test_packages": uncovered,
        "boundary_leads": leads,
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
            "manual_closure_required": bool(
                not acceptance or uncovered or leads or urls or surface["changed_files"]
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
        f"- Changed files: `{surface['changed_file_count']}`",
        f"- Acceptance context: `{gate['acceptance_context']}`",
        f"- Changed-test CI coverage: `{gate['changed_test_ci_coverage']}`",
        f"- Changed-test execution: `{gate['changed_test_execution']}`",
        f"- External URL validation: `{gate['external_url_validation']}`",
        "",
        "## Acceptance Contract",
        "",
    ]
    candidates = report["acceptance"]["candidates"]
    lines.extend([f"- [ ] {item}" for item in candidates] or ["- [ ] No acceptance source supplied."])
    lines.extend(["", "## Hand-Written File Ledger", ""])
    lines.append("| Status | Path | Categories | Reviewer closure |")
    lines.append("| --- | --- | --- | --- |")
    for item in report["handwritten_files"]:
        lines.append(
            f"| `{item['status']}` | `{item['path']}` | "
            f"{', '.join(item['categories'])} | [ ] rationale / contract / evidence |"
        )
    lines.extend(["", "## Changed Go Test Packages", ""])
    if not report["changed_go_test_coverage"]:
        lines.append("- No changed Go test packages.")
    for item in report["changed_go_test_coverage"]:
        state = "covered" if item["ci_covered"] else "not proven by CI"
        lines.append(f"- `{item['package']}`: {state}; state `{item['state']}`")
        for evidence in item["evidence"]:
            lines.append(f"  - `{evidence['source']}`: `{evidence['command']}`")
    lines.extend(["", "## Boundary Leads", ""])
    if not report["boundary_leads"]:
        lines.append("- None from deterministic diff checks.")
    for item in report["boundary_leads"]:
        lines.append(f"- `{item['id']}` in `{item['path']}`: `{item['evidence']}`")
    lines.extend(["", "## External URLs", ""])
    if not report["external_urls"]:
        lines.append("- No added external URLs.")
    checked = {item["url"]: item for item in report["url_checks"]}
    for url in report["external_urls"]:
        status = checked.get(url, {}).get("status", "not checked")
        lines.append(f"- `{status}`: {url}")
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
            "Do not call the final-head review complete until every acceptance item and hand-written file "
            "has reviewer-owned rationale/evidence, every uncovered changed test package is run directly, "
            "and every boundary lead or external URL is resolved or explicitly classified.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Checked-out repository root")
    parser.add_argument("--base", required=True, help="Base ref")
    parser.add_argument("--head", default="HEAD", help="Exact head ref")
    parser.add_argument(
        "--acceptance-file", action="append", default=[], help="Issue/proposal text file; repeatable"
    )
    parser.add_argument(
        "--acceptance-note", action="append", default=[], help="Explicit acceptance item; repeatable"
    )
    parser.add_argument(
        "--run-go-tests",
        action="store_true",
        help="Run changed Go test packages not proven by workflow commands",
    )
    parser.add_argument("--check-urls", action="store_true", help="HEAD-check literal added external URLs")
    parser.add_argument("--url-timeout", type=float, default=10.0, help="URL timeout in seconds")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

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
    if args.check_urls and any(item["ok"] is False for item in report["url_checks"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
