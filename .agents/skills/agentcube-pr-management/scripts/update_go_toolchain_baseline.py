#!/usr/bin/env python3
"""Update AgentCube Go toolchain baseline files.

This is a local automation helper for preparing a focused Go/toolchain PR. It
updates:
- the go.mod go directive
- optional go.mod toolchain directive handling
- Dockerfile golang:<version> builder tags
- GitHub Actions inline go-version entries, converting them to go-version-file
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
GO_VERSION_RE = re.compile(
    r"^([ \t]*)go-version[ \t]*:[ \t]*[\"']?[^\"'\n]+[\"']?[ \t]*$",
    re.MULTILINE,
)
GOLANG_IMAGE_RE = re.compile(
    r"^(FROM(?:\s+--platform=\S+)?\s+golang:)"
    r"([0-9]+\.[0-9]+(?:\.[0-9]+)?)"
    r"([^\s]*)",
    re.MULTILINE,
)
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to update. Defaults to current directory.",
    )
    parser.add_argument(
        "--version",
        help="Target Go version without the leading 'go', for example 1.26.4.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest stable Go release from https://go.dev/dl/?mode=json.",
    )
    parser.add_argument(
        "--toolchain-mode",
        choices=("remove", "align", "keep"),
        default="remove",
        help=(
            "How to handle an existing go.mod toolchain directive. "
            "'remove' matches the current AgentCube baseline."
        ),
    )
    return parser.parse_args()


def latest_stable_go() -> str:
    with urllib.request.urlopen("https://go.dev/dl/?mode=json", timeout=30) as response:
        releases = json.load(response)

    for release in releases:
        if release.get("stable"):
            return str(release["version"]).removeprefix("go")

    raise ValueError("go.dev did not return a stable Go release")


def choose_version(args: argparse.Namespace) -> str:
    if args.latest == bool(args.version):
        raise ValueError("choose exactly one of --latest or --version")

    version = latest_stable_go() if args.latest else args.version
    if not version or not VERSION_RE.match(version):
        raise ValueError(f"invalid Go version: {version!r}")

    return version


def write_if_changed(path: Path, content: str, changed: list[Path]) -> None:
    old = path.read_text()
    if old == content:
        return

    path.write_text(content)
    changed.append(path)


def update_go_mod(repo: Path, version: str, toolchain_mode: str, changed: list[Path]) -> None:
    path = repo / "go.mod"
    content = path.read_text()

    if not GO_DIRECTIVE_RE.search(content):
        raise ValueError("go.mod does not contain a parseable go directive")

    content = GO_DIRECTIVE_RE.sub(f"go {version}", content, count=1)

    if toolchain_mode == "remove":
        content = re.sub(r"\ntoolchain\s+go[0-9]+\.[0-9]+(?:\.[0-9]+)?\s*\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
    elif toolchain_mode == "align":
        if TOOLCHAIN_RE.search(content):
            content = TOOLCHAIN_RE.sub(f"toolchain go{version}", content, count=1)
        else:
            content = content.replace(f"go {version}\n", f"go {version}\n\ntoolchain go{version}\n", 1)

    write_if_changed(path, content, changed)


def update_dockerfiles(repo: Path, version: str, changed: list[Path]) -> None:
    docker_dir = repo / "docker"
    if not docker_dir.is_dir():
        raise ValueError(f"missing docker directory: {docker_dir}")

    found = False
    for path in sorted(docker_dir.glob("Dockerfile*")):
        content = path.read_text()

        def replace(match: re.Match[str]) -> str:
            nonlocal found
            found = True
            prefix, _old_version, suffix = match.groups()
            return f"{prefix}{version}{suffix}"

        updated = GOLANG_IMAGE_RE.sub(replace, content)
        write_if_changed(path, updated, changed)

    if not found:
        raise ValueError("no golang builder images found under docker/Dockerfile*")


def update_workflows(repo: Path, changed: list[Path]) -> None:
    workflows = repo / ".github" / "workflows"
    if not workflows.is_dir():
        raise ValueError(f"missing workflow directory: {workflows}")

    for path in sorted(workflows.glob("*.yml")):
        content = path.read_text()
        updated = GO_VERSION_RE.sub(r"\1go-version-file: go.mod", content)
        write_if_changed(path, updated, changed)


def main() -> int:
    args = parse_args()
    repo = Path(args.repo_root).resolve()

    try:
        version = choose_version(args)
        changed: list[Path] = []
        update_go_mod(repo, version, args.toolchain_mode, changed)
        update_dockerfiles(repo, version, changed)
        update_workflows(repo, changed)
    except Exception as exc:  # noqa: BLE001 - CLI helper should print a compact error.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"target Go version: {version}")
    if changed:
        print("updated files:")
        for path in changed:
            print(f"- {path.relative_to(repo)}")
    else:
        print("no files changed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
