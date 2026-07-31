#!/usr/bin/env python3
"""Build an evidence ledger for an AgentCube final-head PR review."""

from __future__ import annotations

import argparse
import hashlib
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
FINDING_STATUSES = {
    "fixed",
    "present",
    "not-applicable",
    "duplicate-on-current-pr",
    "accepted-by-maintainer",
}
BLOCKING_FINDING_STATUSES = {"present", "duplicate-on-current-pr"}


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


def closure_target(value: dict[str, Any], path: Path) -> dict[str, Any]:
    return validated_target(value.get("target"), path)


def validate_decision_evidence(
    entry: dict[str, Any], status: str, target: dict[str, Any], path: Path
) -> dict[str, Any] | None:
    decision = entry.get("decision")
    if decision is None and status not in {"duplicate-on-current-pr", "accepted-by-maintainer"}:
        return None
    if not isinstance(decision, dict):
        raise ValueError(f"{path}: finding {entry.get('id')} needs structured decision evidence")
    url = decision.get("url")
    expected_prefix = (
        f"https://github.com/{target['repository']}/pull/{target['pull_request']}"
    )
    comment_url_re = re.compile(
        rf"{re.escape(expected_prefix)}#(?:discussion_r|issuecomment-|pullrequestreview-)\d+"
    )
    if not isinstance(url, str) or not comment_url_re.fullmatch(url):
        raise ValueError(
            f"{path}: finding {entry.get('id')} decision URL must target a current-PR comment"
        )
    if status == "accepted-by-maintainer":
        author = decision.get("author")
        association = decision.get("author_association")
        if not isinstance(author, str) or not author.strip():
            raise ValueError(f"{path}: accepted finding {entry.get('id')} needs decision author")
        if not isinstance(association, str) or association not in {
            "OWNER",
            "MEMBER",
            "COLLABORATOR",
        }:
            raise ValueError(
                f"{path}: accepted finding {entry.get('id')} needs maintainer author_association"
            )
    return decision


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


def run_go_tests(repo: Path, head: str, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    leads.extend(exported_go_api_leads(repo, args.base, args.head, surface["changed_files"]))
    leads.extend(kubernetes_codegen_alignment_leads(repo, args.head, surface["changed_files"]))
    acceptance = acceptance_candidates(
        [Path(path) for path in args.acceptance_file], args.acceptance_note
    )
    findings = load_finding_ledger(args.finding_ledger)
    finding_closure = close_finding_ledger(
        findings,
        args.finding_closure,
        surface["head"]["sha"],
        {
            "repository": args.target_repository,
            "pull_request": args.target_pull_request,
        },
        args.no_carry_forward_findings,
    )
    finding_state = finding_closure_state(finding_closure)
    finding_readiness = finding_readiness_state(finding_closure, finding_state)
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
        "finding_ledger": finding_closure,
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
            "finding_ledger_closure": finding_state,
            "finding_readiness": finding_readiness,
            "manual_closure_required": bool(
                not acceptance
                or uncovered
                or leads
                or urls
                or surface["changed_files"]
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
        f"- Acceptance context: `{gate['acceptance_context']}`",
        f"- Changed-test CI coverage: `{gate['changed_test_ci_coverage']}`",
        f"- Changed-test execution: `{gate['changed_test_execution']}`",
        f"- External URL validation: `{gate['external_url_validation']}`",
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
            "has reviewer-owned rationale/evidence, every carry-forward finding is classified against the "
            "exact current head, every uncovered changed test package is run directly, and every boundary "
            "lead or external URL is resolved or explicitly classified.",
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
        help="Run changed Go test packages not proven by workflow commands",
    )
    parser.add_argument("--check-urls", action="store_true", help="HEAD-check literal added external URLs")
    parser.add_argument("--url-timeout", type=float, default=10.0, help="URL timeout in seconds")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if args.no_carry_forward_findings and args.finding_closure:
        parser.error("--finding-closure cannot be used with --no-carry-forward-findings")

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
    if report["gate"]["finding_ledger_closure"] not in {"none-declared", "complete"}:
        return 1
    if report["gate"]["finding_readiness"]["state"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
