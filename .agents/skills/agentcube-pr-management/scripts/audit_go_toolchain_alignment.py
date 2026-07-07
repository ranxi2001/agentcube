#!/usr/bin/env python3
"""Audit AgentCube Go toolchain version alignment.

Checks:
- go.mod go directive
- optional go.mod toolchain directive
- Dockerfile golang:<version> builder image tags
- GitHub Actions setup-go entries using go-version-file: go.mod
- optionally latest stable Go release from go.dev
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path


GO_DIRECTIVE_RE = re.compile(r"^go[ \t]+([0-9]+\.[0-9]+(?:\.[0-9]+)?)[ \t]*$", re.MULTILINE)
TOOLCHAIN_RE = re.compile(r"^toolchain[ \t]+go([0-9]+\.[0-9]+(?:\.[0-9]+)?)[ \t]*$", re.MULTILINE)
GOLANG_IMAGE_RE = re.compile(
    r"^FROM(?:\s+--platform=\S+)?\s+golang:([0-9]+\.[0-9]+(?:\.[0-9]+)?)([^\s]*)",
    re.MULTILINE,
)
SETUP_GO_RE = re.compile(r"uses:\s*actions/setup-go@")
GO_VERSION_RE = re.compile(r"\bgo-version[ \t]*:")
GO_VERSION_FILE_RE = re.compile(r"\bgo-version-file[ \t]*:[ \t]*go\.mod\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to audit. Defaults to current directory.",
    )
    parser.add_argument(
        "--check-latest",
        action="store_true",
        help="Fetch https://go.dev/dl/?mode=json and report the latest stable Go release.",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def read_go_mod(repo: Path) -> tuple[str, str | None]:
    go_mod = repo / "go.mod"
    content = go_mod.read_text()

    match = GO_DIRECTIVE_RE.search(content)
    if not match:
        raise ValueError("go.mod does not contain a parseable go directive")

    toolchain_match = TOOLCHAIN_RE.search(content)
    return match.group(1), toolchain_match.group(1) if toolchain_match else None


def audit_dockerfiles(repo: Path, go_version: str) -> list[str]:
    errors: list[str] = []
    docker_dir = repo / "docker"

    if not docker_dir.is_dir():
        return [f"missing docker directory: {docker_dir}"]

    found = []
    for path in sorted(docker_dir.glob("Dockerfile*")):
        content = path.read_text()
        for match in GOLANG_IMAGE_RE.finditer(content):
            version, suffix = match.groups()
            rel = path.relative_to(repo)
            found.append((rel, version, suffix))
            print(f"Docker builder: {rel}: golang:{version}{suffix}")
            if version != go_version:
                errors.append(f"{rel} uses golang:{version}{suffix}, expected Go {go_version}")

    if not found:
        errors.append("no golang builder images found under docker/Dockerfile*")

    return errors


def audit_workflows(repo: Path) -> list[str]:
    errors: list[str] = []
    workflows = repo / ".github" / "workflows"

    if not workflows.is_dir():
        return [f"missing workflow directory: {workflows}"]

    for path in sorted(workflows.glob("*.yml")):
        content = path.read_text()
        if not SETUP_GO_RE.search(content):
            continue

        rel = path.relative_to(repo)
        has_file = bool(GO_VERSION_FILE_RE.search(content))
        has_inline = bool(GO_VERSION_RE.search(content))
        print(f"setup-go workflow: {rel}: go-version-file={has_file} inline-go-version={has_inline}")

        if not has_file:
            errors.append(f"{rel} uses actions/setup-go without go-version-file: go.mod")
        if has_inline:
            errors.append(f"{rel} has inline go-version; prefer go-version-file: go.mod")

    return errors


def latest_stable_go() -> str:
    with urllib.request.urlopen("https://go.dev/dl/?mode=json", timeout=30) as response:
        releases = json.load(response)

    for release in releases:
        if release.get("stable"):
            version = str(release["version"])
            return version.removeprefix("go")

    raise ValueError("go.dev did not return a stable Go release")


def main() -> int:
    args = parse_args()
    repo = Path(args.repo_root).resolve()

    errors: list[str] = []
    go_version, toolchain_version = read_go_mod(repo)

    print(f"go.mod go directive: {go_version}")
    if toolchain_version:
        print(f"go.mod toolchain directive: {toolchain_version}")
        if toolchain_version != go_version:
            errors.append(f"go.mod toolchain {toolchain_version} differs from go directive {go_version}")
    else:
        print("go.mod toolchain directive: <none>")

    errors.extend(audit_dockerfiles(repo, go_version))
    errors.extend(audit_workflows(repo))

    if args.check_latest:
        latest = latest_stable_go()
        print(f"latest stable Go release: {latest}")
        if latest != go_version:
            print(f"NOTICE: project Go {go_version} differs from latest stable Go {latest}")

    if errors:
        for error in errors:
            fail(error)
        return 1

    print("Go toolchain alignment: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
