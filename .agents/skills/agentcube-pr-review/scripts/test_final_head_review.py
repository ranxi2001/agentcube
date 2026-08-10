#!/usr/bin/env python3

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("final_head_review.py")
GO_BINARY = shutil.which("go")
assert GO_BINARY is not None
GO_BINARY = str(Path(GO_BINARY).resolve())
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("final_head_review", SCRIPT)
assert SPEC and SPEC.loader
FINAL_HEAD_REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL_HEAD_REVIEW)


class FinalHeadReviewTest(unittest.TestCase):
    TARGET = {"repository": "volcano-sh/agentcube", "pull_request": 446}

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                ".",
                "--base",
                "HEAD",
                "--head",
                "HEAD",
                "--target-repository",
                self.TARGET["repository"],
                "--target-pull-request",
                str(self.TARGET["pull_request"]),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_repo_cli(
        self, repo: Path, base: str, head: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(repo),
                "--base",
                base,
                "--head",
                head,
                "--target-repository",
                self.TARGET["repository"],
                "--target-pull-request",
                str(self.TARGET["pull_request"]),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_git(self, repo: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_cli_requires_explicit_carry_forward_mode(self) -> None:
        result = self.run_cli()

        self.assertEqual(result.returncode, 2)
        self.assertIn("one of the arguments", result.stderr)

    def test_cli_rejects_both_carry_forward_modes(self) -> None:
        result = self.run_cli(
            "--finding-ledger",
            "ledger.json",
            "--no-carry-forward-findings",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowed with argument", result.stderr)

    def test_cli_rejects_closure_when_no_findings_are_declared(self) -> None:
        result = self.run_cli(
            "--no-carry-forward-findings",
            "--finding-closure",
            "closure.json",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be used", result.stderr)

    def test_cli_requires_scope_closure_for_readiness(self) -> None:
        result = self.run_cli(
            "--no-carry-forward-findings",
            "--acceptance-note",
            "Review the exact head.",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("PR-scope closure: `not-provided`", result.stdout)

    def test_cli_accepts_empty_exact_head_scope_for_an_empty_diff(self) -> None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "base": head,
                        "head": head,
                        "merge_base": head,
                        "files": [],
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_cli(
                "--no-carry-forward-findings",
                "--acceptance-note",
                "Review the exact head.",
                "--scope-closure",
                str(closure),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PR-scope closure: `ready`", result.stdout)

    def test_cli_rejects_ready_scope_without_acceptance_contract(self) -> None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "base": head,
                        "head": head,
                        "merge_base": head,
                        "files": [],
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_cli(
                "--no-carry-forward-findings",
                "--scope-closure",
                str(closure),
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Acceptance context: `missing`", result.stdout)

    def test_cli_rejects_unexecuted_unicode_changed_test_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()

            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Scope Test")
            self.run_git(repo, "config", "user.email", "scope@example.com")
            (repo / "go.mod").write_text("module example.com/scope\n\ngo 1.22\n", encoding="utf-8")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            self.run_git(repo, "add", "go.mod", "README.md")
            self.run_git(repo, "commit", "-q", "-m", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            package = repo / "pkg"
            package.mkdir()
            test_path = "pkg/é_test.go"
            (repo / test_path).write_text(
                "package pkg\n\nimport \"testing\"\n\nfunc TestLogic(t *testing.T) {}\n",
                encoding="utf-8",
            )
            self.run_git(repo, "add", test_path)
            self.run_git(repo, "commit", "-q", "-m", "add changed test")
            head = self.run_git(repo, "rev-parse", "HEAD")

            closure = root / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "base": base,
                        "head": head,
                        "merge_base": base,
                        "files": [
                            {
                                "path": test_path,
                                "group": "regression test",
                                "disposition": "keep",
                                "acceptance": "Prove the changed behavior.",
                                "owning_surface": "pkg tests",
                                "independently_mergeable": False,
                                "rationale": "The test guards the feature contract.",
                                "evidence": ["The package contains the focused regression."],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The changed behavior must have a regression test.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )
            executed = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The changed behavior must have a regression test.",
                "--scope-closure",
                str(closure),
                "--run-go-tests",
                "--go-binary",
                GO_BINARY,
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["handwritten_files"][0]["path"], test_path)
        self.assertEqual(report["uncovered_changed_go_test_packages"], ["./pkg"])
        self.assertEqual(report["gate"]["changed_test_execution"], "not-run")
        self.assertEqual(executed.returncode, 0, executed.stderr)
        executed_report = json.loads(executed.stdout)
        self.assertEqual(executed_report["gate"]["changed_test_execution"], "passed")

    def test_generated_detection_requires_a_canonical_header_line(self) -> None:
        self.assertFalse(
            FINAL_HEAD_REVIEW.is_generated(
                "pkg/manual.go",
                'package pkg\n\nconst message = "Code generated output says DO NOT EDIT"\n',
            )
        )
        self.assertTrue(
            FINAL_HEAD_REVIEW.is_generated(
                "pkg/generated.go",
                "// Code generated by tool. DO NOT EDIT.\n\npackage pkg\n",
            )
        )
        self.assertFalse(
            FINAL_HEAD_REVIEW.is_generated(
                "pkg/manual.go",
                "package pkg\n\n// Code generated by tool. DO NOT EDIT.\nfunc manual() {}\n",
            )
        )
        self.assertFalse(
            FINAL_HEAD_REVIEW.is_generated(
                "pkg/manual.go",
                "/* license */ package pkg\n// Code generated by tool. DO NOT EDIT.\n",
            )
        )

    def test_cli_rejects_unchecked_url_from_unicode_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "URL Test")
            self.run_git(repo, "config", "user.email", "url@example.com")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            self.run_git(repo, "add", "README.md")
            self.run_git(repo, "commit", "-q", "-m", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            docs = repo / "docs"
            docs.mkdir()
            changed_path = "docs/升级.md"
            url = "https://example.com/releases/download/v1/tool"
            (repo / changed_path).write_text(f"curl {url}\n", encoding="utf-8")
            self.run_git(repo, "add", changed_path)
            self.run_git(repo, "commit", "-q", "-m", "add install doc")
            head = self.run_git(repo, "rev-parse", "HEAD")

            closure = root / "scope.json"
            closure_value = {
                "schema_version": 1,
                "target": self.TARGET,
                "base": base,
                "head": head,
                "merge_base": base,
                "files": [
                    {
                        "path": changed_path,
                        "group": "installation docs",
                        "disposition": "keep",
                        "acceptance": "Document the supported installation artifact.",
                        "owning_surface": "operator documentation",
                        "independently_mergeable": False,
                        "rationale": "Users execute this documented command.",
                        "evidence": ["The parent contract requires installation docs."],
                    }
                ],
            }
            closure.write_text(
                json.dumps(closure_value, ensure_ascii=False), encoding="utf-8"
            )

            result = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The installation artifact must be documented.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )
            closure_value["external_urls"] = [
                {
                    "url": url,
                    "status": "resolved",
                    "rationale": "The release artifact is published and immutable.",
                    "evidence": ["Exact URL returned HTTP 200 in an exact-head review."],
                }
            ]
            closure.write_text(
                json.dumps(closure_value, ensure_ascii=False), encoding="utf-8"
            )
            resolved = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The installation artifact must be documented.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["external_urls"], [url])
        self.assertEqual(report["gate"]["external_url_validation"], "not-run")
        self.assertEqual(report["gate"]["external_url_closure"], "incomplete")
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertEqual(
            json.loads(resolved.stdout)["gate"]["external_url_closure"], "complete"
        )

    def test_renamed_away_go_test_keeps_old_package_in_ledger(self) -> None:
        packages = FINAL_HEAD_REVIEW.changed_go_test_packages(
            [
                {
                    "status": "R100",
                    "old_path": "pkg/old_test.go",
                    "path": "pkg/old.go",
                },
                {
                    "status": "R090",
                    "old_path": "oldpkg/moved_test.go",
                    "path": "newpkg/moved_test.go",
                },
            ]
        )

        self.assertEqual(
            packages,
            [
                {"package": "./newpkg", "state": "runnable"},
                {"package": "./oldpkg", "state": "runnable"},
                {"package": "./pkg", "state": "runnable"},
            ],
        )

    def test_scope_closure_requires_every_handwritten_path(self) -> None:
        handwritten = [
            {"status": "M", "path": "a.go", "categories": ["go"]},
            {"status": "M", "path": "b.go", "categories": ["go"]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "head": "a" * 40,
                        "files": [
                            {
                                "path": "a.go",
                                "group": "feature",
                                "disposition": "keep",
                                "acceptance": "Implement the accepted behavior.",
                                "owning_surface": "package a",
                                "independently_mergeable": False,
                                "rationale": "The production path is required.",
                                "evidence": ["Issue contract and focused test."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure), handwritten, "a" * 40, self.TARGET
            )

        self.assertEqual(result["missing_paths"], ["b.go"])
        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(result), "incomplete")

    def test_scope_closure_preserves_leading_and_trailing_path_whitespace(self) -> None:
        changed_path = " docs/a.md "
        handwritten = [{"status": "M", "path": changed_path, "categories": ["other"]}]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "head": "a" * 40,
                        "files": [
                            {
                                "path": changed_path,
                                "group": "docs",
                                "disposition": "keep",
                                "acceptance": "Document the behavior.",
                                "owning_surface": "docs",
                                "independently_mergeable": False,
                                "rationale": "The exact path is part of the diff.",
                                "evidence": ["Exact NUL-delimited Git path."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure), handwritten, "a" * 40, self.TARGET
            )

        self.assertEqual(result["rows"][0]["scope"]["path"], changed_path)
        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(result), "ready")

    def test_scope_closure_blocks_remove_separate_and_mixed_hunks(self) -> None:
        handwritten = [
            {"status": "M", "path": "hack/update-codegen.sh", "categories": ["scripts"]},
            {"status": "M", "path": "noop.toml", "categories": ["other"]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "head": "b" * 40,
                        "files": [
                            {
                                "path": "hack/update-codegen.sh",
                                "group": "codegen",
                                "disposition": "mixed",
                                "acceptance": "Align generated clients.",
                                "owning_surface": "code-generation tooling",
                                "independently_mergeable": True,
                                "rationale": "Only the version hunk is required.",
                                "evidence": ["Version-only regeneration is clean."],
                                "hunks": [
                                    {
                                        "label": "version pin",
                                        "disposition": "keep",
                                        "acceptance": "Match Kubernetes v0.36.2.",
                                        "owning_surface": "code-generator pin",
                                        "rationale": "The tool minor must match.",
                                        "evidence": ["go.mod uses v0.36.2."],
                                    },
                                    {
                                        "label": "platform rewrite",
                                        "disposition": "separate",
                                        "acceptance": "No feature requirement.",
                                        "owning_surface": "portability follow-up",
                                        "rationale": "It is independently testable.",
                                        "evidence": ["The original helper still works."],
                                    },
                                ],
                            },
                            {
                                "path": "noop.toml",
                                "group": "formatting",
                                "disposition": "remove",
                                "acceptance": "No acceptance item.",
                                "owning_surface": "none",
                                "independently_mergeable": False,
                                "rationale": "The diff has no semantic effect.",
                                "evidence": ["Whitespace-ignored diff is empty."],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure), handwritten, "b" * 40, self.TARGET
            )

        self.assertEqual(
            result["blocking_items"],
            ["hack/update-codegen.sh#platform rewrite", "noop.toml"],
        )
        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(result), "blocked")

    def test_scope_closure_rejects_unknown_duplicate_and_empty_rationale(self) -> None:
        handwritten = [{"status": "M", "path": "a.go", "categories": ["go"]}]

        def entry(path: str, rationale: str = "Required production path.") -> dict[str, object]:
            return {
                "path": path,
                "group": "feature",
                "disposition": "keep",
                "acceptance": "Implement the contract.",
                "owning_surface": "package a",
                "independently_mergeable": False,
                "rationale": rationale,
                "evidence": ["Focused test."],
            }

        cases = [
            ([entry("unknown.go")], "not a hand-written changed path"),
            ([entry("a.go"), entry("a.go")], "duplicate scope path"),
            ([entry("a.go", "")], "rationale must be a non-empty string"),
        ]
        for entries, expected_error in cases:
            with self.subTest(expected_error=expected_error), tempfile.TemporaryDirectory() as directory:
                closure = Path(directory) / "scope.json"
                closure.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "target": self.TARGET,
                            "head": "c" * 40,
                            "files": entries,
                        }
                    ),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, expected_error):
                    FINAL_HEAD_REVIEW.load_scope_closure(
                        str(closure), handwritten, "c" * 40, self.TARGET
                    )

    def test_scope_closure_rejects_stale_head_and_unexplained_atomic_keep(self) -> None:
        handwritten = [{"status": "M", "path": "a.go", "categories": ["go"]}]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            value = {
                "schema_version": 1,
                "target": self.TARGET,
                "head": "d" * 40,
                "files": [
                    {
                        "path": "a.go",
                        "group": "prerequisite",
                        "disposition": "keep",
                        "acceptance": "Update the shared API.",
                        "owning_surface": "shared package",
                        "independently_mergeable": True,
                        "rationale": "The feature consumes the new API.",
                        "evidence": ["Build dependency."],
                    }
                ],
            }
            closure.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "needs non-empty atomicity"):
                FINAL_HEAD_REVIEW.load_scope_closure(
                    str(closure), handwritten, "e" * 40, self.TARGET
                )

            value["files"][0]["atomicity"] = "An intermediate tree cannot compile."
            closure.write_text(json.dumps(value), encoding="utf-8")
            ready = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure), handwritten, "d" * 40, self.TARGET
            )
            result = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure), handwritten, "e" * 40, self.TARGET
            )

        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(ready), "ready")
        self.assertFalse(result["head_matches"])
        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(result), "stale-head")

    def test_scope_closure_rejects_stale_base_or_merge_base(self) -> None:
        handwritten: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            value = {
                "schema_version": 1,
                "target": self.TARGET,
                "base": "a" * 40,
                "head": "b" * 40,
                "merge_base": "c" * 40,
                "files": [],
            }
            closure.write_text(json.dumps(value), encoding="utf-8")
            stale_base = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure),
                handwritten,
                "b" * 40,
                self.TARGET,
                "d" * 40,
                "c" * 40,
            )
            stale_merge_base = FINAL_HEAD_REVIEW.load_scope_closure(
                str(closure),
                handwritten,
                "b" * 40,
                self.TARGET,
                "a" * 40,
                "d" * 40,
            )

        self.assertEqual(FINAL_HEAD_REVIEW.scope_closure_state(stale_base), "stale-surface")
        self.assertEqual(
            FINAL_HEAD_REVIEW.scope_closure_state(stale_merge_base), "stale-surface"
        )

    def test_mixed_all_keep_cannot_bypass_independent_atomicity(self) -> None:
        handwritten = [{"status": "M", "path": "a.go", "categories": ["go"]}]
        hunk = {
            "disposition": "keep",
            "acceptance": "Preserve the compatibility invariant.",
            "owning_surface": "package a",
            "rationale": "This part is required.",
            "evidence": ["Focused test."],
        }
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "head": "f" * 40,
                        "files": [
                            {
                                "path": "a.go",
                                "group": "shared prerequisite",
                                "disposition": "mixed",
                                "acceptance": "Implement two required compatibility deltas.",
                                "owning_surface": "package a",
                                "independently_mergeable": True,
                                "rationale": "Both hunks are individually required.",
                                "evidence": ["Build and focused test."],
                                "hunks": [
                                    {"label": "first", **hunk},
                                    {"label": "second", **hunk},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "needs non-empty atomicity"):
                FINAL_HEAD_REVIEW.load_scope_closure(
                    str(closure), handwritten, "f" * 40, self.TARGET
                )

    def test_changed_go_packages_are_mapped_to_actual_workflow_scopes(self) -> None:
        packages = FINAL_HEAD_REVIEW.changed_go_test_packages(
            [
                {"status": "A", "path": "cmd/workload-manager/main_test.go"},
                {"status": "M", "path": "pkg/router/router_test.go"},
            ]
        )
        evidence = [
            {
                "source": ".github/workflows/coverage.yml",
                "command": "go test -race -coverpkg=./pkg/... ./pkg/...",
                "scopes": FINAL_HEAD_REVIEW.go_test_scopes(
                    "go test -race -coverpkg=./pkg/... ./pkg/..."
                ),
            }
        ]

        coverage = FINAL_HEAD_REVIEW.package_coverage(
            packages,
            evidence,
            {
                "./pkg/router": {
                    "source": "https://github.com/volcano-sh/agentcube/actions/runs/1",
                    "command": evidence[0]["command"],
                    "evidence": ["Exact-head job passed."],
                }
            },
        )

        self.assertEqual(evidence[0]["scopes"], ["./pkg/..."])
        self.assertEqual(FINAL_HEAD_REVIEW.go_test_scopes('echo "go test ./pkg/..."'), [])
        self.assertEqual(FINAL_HEAD_REVIEW.go_test_scopes("# go test ./pkg/..."), [])
        self.assertEqual(FINAL_HEAD_REVIEW.go_test_scopes("true # go test ./pkg/..."), [])
        self.assertFalse(coverage[0]["ci_covered"])
        self.assertTrue(coverage[1]["ci_covered"])
        self.assertEqual(coverage[1]["workflow_candidates"], evidence)

    def test_only_unconditional_direct_go_test_is_ci_waivable(self) -> None:
        self.assertEqual(
            FINAL_HEAD_REVIEW.unconditional_direct_go_test(
                "go test -race -count=2 -coverprofile=coverage.out ./pkg/..."
            ),
            ("go test -race -count=2 -coverprofile=coverage.out ./pkg/...", ["./pkg/..."]),
        )
        for command in (
            "true || go test ./pkg/...",
            "if false; then go test ./pkg/...; fi",
            "exit 0; go test ./pkg/...",
            "go test ./pkg/... && echo done",
            "GOFLAGS=-mod=readonly go test ./pkg/...",
            "go test -run '^$' ./pkg/...",
            "go test -list . ./pkg/...",
            "go test -c ./pkg/...",
            "go test -count=0 ./pkg/...",
            "go test -short ./pkg/...",
            "go test -skip Integration ./pkg/...",
            "go test -exec true ./pkg/...",
            "go test -tags integration ./pkg/...",
            "go test -n ./pkg/...",
            "go test -overlay overlay.json ./pkg/...",
            "GOMAXPROCS=2 go test ./pkg/...",
            "go test $TEST_FLAGS ./pkg/...",
            "make test",
            "./hack/test.sh",
        ):
            with self.subTest(command=command):
                self.assertIsNone(FINAL_HEAD_REVIEW.unconditional_direct_go_test(command))

    def test_filtered_or_continue_on_error_workflow_is_lead_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q")
            (repo / "go.mod").write_text("module example.com/ci\n\ngo 1.22\n", encoding="utf-8")
            workflow = repo / ".github" / "workflows" / "ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "jobs:\n"
                "  filtered:\n"
                "    name: Filtered tests\n"
                "    steps:\n"
                "      - name: Filtered package tests\n"
                "        run: go test -run '^$' ./pkg/...\n"
                "  tolerated:\n"
                "    name: Tolerated tests\n"
                "    steps:\n"
                "      - name: Tolerated package tests\n"
                "        continue-on-error: true\n"
                "        run: go test ./pkg/...\n"
                "  injected:\n"
                "    name: Injected flags\n"
                "    env:\n"
                "      GOFLAGS: -run=^$\n"
                "    steps:\n"
                "      - name: Injected package tests\n"
                "        run: go test ./pkg/...\n"
                "  container-injected:\n"
                "    name: Container injected flags\n"
                "    container:\n"
                "      image: golang:latest\n"
                "      env:\n"
                "        GOFLAGS: -run=^$\n"
                "    steps:\n"
                "      - name: Container injected package tests\n"
                "        run: go test ./pkg/...\n"
                "  prior-injected:\n"
                "    name: Prior injected flags\n"
                "    steps:\n"
                "      - name: Inject flags\n"
                "        run: echo 'GOFLAGS=-run=^$' >> \"$GITHUB_ENV\"\n"
                "      - name: Prior injected package tests\n"
                "        run: go test ./pkg/...\n"
                "  wrong-directory:\n"
                "    name: Wrong directory\n"
                "    defaults:\n"
                "      run:\n"
                "        working-directory: submodule\n"
                "    steps:\n"
                "      - name: Wrong-directory package tests\n"
                "        run: go test ./pkg/...\n"
                "  default-checkout:\n"
                "    name: Default checkout\n"
                "    runs-on: ubuntu-24.04\n"
                "    steps:\n"
                "      - name: Default checkout source\n"
                "        uses: actions/checkout@1111111111111111111111111111111111111111\n"
                "      - name: Default-checkout package tests\n"
                "        run: go test ./pkg/...\n"
                "  dirty-checkout:\n"
                "    name: Dirty checkout\n"
                "    runs-on: ubuntu-24.04\n"
                "    steps:\n"
                "      - name: Dirty checkout source\n"
                "        uses: actions/checkout@1111111111111111111111111111111111111111\n"
                "        with:\n"
                "          ref: ${{ github.event.pull_request.head.sha }}\n"
                "          clean: false\n"
                "      - name: Dirty-checkout package tests\n"
                "        run: go test ./pkg/...\n"
                "  self-hosted:\n"
                "    name: Self-hosted tests\n"
                "    runs-on: self-hosted\n"
                "    steps:\n"
                "      - name: Self-hosted checkout\n"
                "        uses: actions/checkout@1111111111111111111111111111111111111111\n"
                "        with:\n"
                "          ref: ${{ github.event.pull_request.head.sha }}\n"
                "      - name: Self-hosted package tests\n"
                "        run: go test ./pkg/...\n"
                "  complete:\n"
                "    name: Complete tests\n"
                "    runs-on: ubuntu-24.04\n"
                "    steps:\n"
                "      - name: Checkout\n"
                "        uses: actions/checkout@1111111111111111111111111111111111111111\n"
                "        with:\n"
                "          ref: ${{ github.event.pull_request.head.sha }}\n"
                "      - name: Complete package tests\n"
                "        continue-on-error: false\n"
                "        run: go test -race -count=1 ./pkg/...\n",
                encoding="utf-8",
            )
            self.run_git(repo, "add", ".github/workflows/ci.yml", "go.mod")
            self.run_git(repo, "-c", "user.name=CI Test", "-c", "user.email=ci@example.com", "commit", "-q", "-m", "workflow")
            head = self.run_git(repo, "rev-parse", "HEAD")

            evidence = FINAL_HEAD_REVIEW.workflow_test_evidence(repo, head)

        by_step = {item["step"]: item for item in evidence}
        self.assertFalse(by_step["Filtered package tests"]["ci_waivable"])
        self.assertFalse(by_step["Tolerated package tests"]["ci_waivable"])
        self.assertFalse(by_step["Injected package tests"]["ci_waivable"])
        self.assertFalse(by_step["Container injected package tests"]["ci_waivable"])
        self.assertFalse(by_step["Prior injected package tests"]["ci_waivable"])
        self.assertFalse(by_step["Wrong-directory package tests"]["ci_waivable"])
        self.assertFalse(by_step["Default-checkout package tests"]["ci_waivable"])
        self.assertFalse(by_step["Dirty-checkout package tests"]["ci_waivable"])
        self.assertFalse(by_step["Self-hosted package tests"]["ci_waivable"])
        self.assertTrue(by_step["Complete package tests"]["ci_waivable"])

    def test_root_workflow_scope_excludes_nested_go_module_and_direct_run_uses_module_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Module Boundary Test")
            self.run_git(repo, "config", "user.email", "module@example.com")
            (repo / "go.mod").write_text("module example.com/root\n\ngo 1.22\n", encoding="utf-8")
            root_package = repo / "pkg"
            root_package.mkdir()
            (root_package / "root_test.go").write_text(
                "package pkg\n\nimport \"testing\"\n\nfunc TestRoot(t *testing.T) {}\n",
                encoding="utf-8",
            )
            nested_package = repo / "nested" / "pkg"
            nested_package.mkdir(parents=True)
            (repo / "nested" / "go.mod").write_text(
                "module example.com/nested\n\ngo 1.22\n", encoding="utf-8"
            )
            (nested_package / "nested_test.go").write_text(
                "package pkg\n\nimport \"testing\"\n\nfunc TestNested(t *testing.T) {}\n",
                encoding="utf-8",
            )
            workflow = repo / ".github" / "workflows" / "ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "jobs:\n"
                "  test:\n"
                "    name: Root module tests\n"
                "    runs-on: ubuntu-24.04\n"
                "    steps:\n"
                "      - name: Checkout\n"
                "        uses: actions/checkout@1111111111111111111111111111111111111111\n"
                "        with:\n"
                "          ref: ${{ github.event.pull_request.head.sha }}\n"
                "      - name: Run root tests\n"
                "        run: go test ./...\n",
                encoding="utf-8",
            )
            self.run_git(repo, "add", ".")
            self.run_git(repo, "commit", "-q", "-m", "nested modules")
            head = self.run_git(repo, "rev-parse", "HEAD")

            evidence = FINAL_HEAD_REVIEW.workflow_test_evidence(repo, head)
            coverage = FINAL_HEAD_REVIEW.package_coverage(
                [
                    {"package": "./pkg", "state": "runnable", "module_root": "."},
                    {
                        "package": "./nested/pkg",
                        "state": "runnable",
                        "module_root": "nested",
                    },
                ],
                evidence,
            )
            direct = FINAL_HEAD_REVIEW.run_go_tests(
                repo, head, [coverage[1]], GO_BINARY
            )

        self.assertTrue(evidence[0]["ci_waivable"])
        self.assertEqual(evidence[0]["nested_module_packages"], ["./nested"])
        self.assertEqual(len(coverage[0]["workflow_candidates"]), 1)
        self.assertEqual(coverage[1]["workflow_candidates"], [])
        self.assertEqual(direct[0]["returncode"], 0, direct[0]["output_tail"])
        self.assertEqual(direct[0]["module_root"], "nested")
        self.assertTrue(
            direct[0]["command"].endswith("/go test -mod=readonly ./pkg -count=1")
        )

    def test_go_wildcard_excludes_ignored_directories_but_exact_scope_covers(self) -> None:
        for package in (
            "./pkg/testdata/hidden",
            "./pkg/vendor/example.com/hidden",
            "./pkg/_hidden",
            "./pkg/.hidden",
        ):
            with self.subTest(package=package):
                self.assertFalse(FINAL_HEAD_REVIEW.scope_covers_package("./...", package))
                self.assertFalse(FINAL_HEAD_REVIEW.scope_covers_package("./pkg/...", package))
                self.assertTrue(FINAL_HEAD_REVIEW.scope_covers_package(package, package))
        self.assertTrue(
            FINAL_HEAD_REVIEW.scope_covers_package(
                "./pkg/_hidden/...", "./pkg/_hidden/child"
            )
        )

    def test_direct_run_sanitizes_goenv_and_build_constraints_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Direct Go Test")
            self.run_git(repo, "config", "user.email", "direct@example.com")
            (repo / "go.mod").write_text("module example.com/direct\n\ngo 1.22\n", encoding="utf-8")
            package = repo / "pkg"
            package.mkdir()
            (package / "fail_test.go").write_text(
                "package pkg\n\nimport \"testing\"\n\nfunc TestFail(t *testing.T) { t.Fatal(\"must run\") }\n",
                encoding="utf-8",
            )
            platform = repo / "platform"
            platform.mkdir()
            (platform / "x_windows_test.go").write_text(
                "package platform\n\nimport \"testing\"\n\nfunc TestWindows(t *testing.T) { t.Fatal(\"must run on Windows\") }\n",
                encoding="utf-8",
            )
            tagged = repo / "tagged"
            tagged.mkdir()
            constrained_sources = {
                "space_test.go": " //go:build integration\n",
                "tab_test.go": "\t//go:build integration\n",
                "bom_test.go": "\ufeff//go:build integration\n",
                "vertical_tab_test.go": "\v//go:build integration\n",
                "form_feed_test.go": "\f//go:build integration\n",
                "nbsp_test.go": "\u00a0//go:build integration\n",
            }
            for name, directive in constrained_sources.items():
                (tagged / name).write_text(
                    f"{directive}\npackage tagged\n\nimport \"testing\"\n\n"
                    "func TestIntegration(t *testing.T) {}\n",
                    encoding="utf-8",
                )
            self.run_git(repo, "add", ".")
            self.run_git(repo, "commit", "-q", "-m", "constrained tests")
            head = self.run_git(repo, "rev-parse", "HEAD")
            packages = FINAL_HEAD_REVIEW.changed_go_test_packages(
                [
                    {"status": "A", "path": "pkg/fail_test.go"},
                    {"status": "A", "path": "platform/x_windows_test.go"},
                    *[
                        {"status": "A", "path": f"tagged/{name}"}
                        for name in constrained_sources
                    ],
                ],
                repo,
                head,
            )
            evidence = [
                {
                    "source": ".github/workflows/ci.yml",
                    "command": "go test ./...",
                    "scopes": ["./..."],
                    "nested_module_packages": [],
                }
            ]
            coverage = FINAL_HEAD_REVIEW.package_coverage(packages, evidence)
            goenv = root / "goenv"
            goenv.write_text("GOFLAGS=-run=^$\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GOENV": str(goenv)}, clear=False):
                failing_result = FINAL_HEAD_REVIEW.run_go_tests(
                    repo, head, [coverage[0]], GO_BINARY
                )
                constrained_results = FINAL_HEAD_REVIEW.run_go_tests(
                    repo, head, coverage[1:], GO_BINARY
                )

        self.assertEqual(failing_result[0]["returncode"], 1)
        self.assertIn("must run", failing_result[0]["output_tail"])
        self.assertEqual(coverage[1]["workflow_candidates"], [])
        self.assertEqual(coverage[2]["workflow_candidates"], [])
        self.assertEqual([item["returncode"] for item in constrained_results], [2, 2])
        self.assertIn("GOOS suffix windows", constrained_results[0]["output_tail"])
        self.assertIn("source build constraint", constrained_results[1]["output_tail"])

    def test_direct_run_requires_explicit_binary_and_uses_tracked_go_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Workspace Test")
            self.run_git(repo, "config", "user.email", "workspace@example.com")
            for module in ("app", "lib", "oldlib"):
                (repo / module).mkdir()
            (repo / "lib" / "go.mod").write_text(
                "module example.com/lib\n\ngo 1.22\n", encoding="utf-8"
            )
            (repo / "lib" / "value.go").write_text(
                'package lib\n\nfunc Value() string { return "workspace" }\n',
                encoding="utf-8",
            )
            (repo / "oldlib" / "go.mod").write_text(
                "module example.com/lib\n\ngo 1.22\n", encoding="utf-8"
            )
            (repo / "oldlib" / "value.go").write_text(
                'package lib\n\nfunc Value() string { return "fallback" }\n',
                encoding="utf-8",
            )
            (repo / "app" / "go.mod").write_text(
                "module example.com/app\n\ngo 1.22\n\n"
                "require example.com/lib v0.0.0\n"
                "replace example.com/lib => ../oldlib\n",
                encoding="utf-8",
            )
            (repo / "app" / "app_test.go").write_text(
                'package app\n\nimport (\n\t"testing"\n\t"example.com/lib"\n)\n\n'
                "func TestWorkspaceSource(t *testing.T) {\n"
                '\tif got := lib.Value(); got != "fallback" { t.Fatalf("used %s", got) }\n'
                "}\n",
                encoding="utf-8",
            )
            (repo / "go.work").write_text(
                "go 1.22\n\nuse (\n\t./app\n\t./lib\n)\n", encoding="utf-8"
            )
            self.run_git(repo, "add", ".")
            self.run_git(repo, "commit", "-q", "-m", "workspace")
            head = self.run_git(repo, "rev-parse", "HEAD")
            coverage = [
                {
                    "package": "./app",
                    "state": "runnable",
                    "ci_covered": False,
                    "module_root": "app",
                    "unverified_test_constraints": [],
                }
            ]
            fake = root / "fake-go"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(root)}, clear=False):
                with self.assertRaisesRegex(ValueError, "requires --go-binary"):
                    FINAL_HEAD_REVIEW.direct_go_environment(repo, None)
            unsupported = root / "darwin-go"
            unsupported.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = env ]; then\n"
                "  printf 'darwin\\narm64\\n'\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            unsupported.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "requires a reviewed linux/amd64"):
                FINAL_HEAD_REVIEW.direct_go_environment(repo, str(unsupported))
            result = FINAL_HEAD_REVIEW.run_go_tests(
                repo, head, coverage, GO_BINARY
            )

        self.assertEqual(result[0]["returncode"], 1)
        self.assertIn("used workspace", result[0]["output_tail"])
        self.assertEqual(result[0]["go_workspace"], "go.work")

    def test_direct_run_materializes_head_without_ignored_go_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Ignored Test")
            self.run_git(repo, "config", "user.email", "ignored@example.com")
            (repo / ".gitignore").write_text("pkg/local_test.go\n", encoding="utf-8")
            (repo / "go.mod").write_text(
                "module example.com/ignored\n\ngo 1.22\n", encoding="utf-8"
            )
            package = repo / "pkg"
            package.mkdir()
            (package / "fail_test.go").write_text(
                "package pkg\n\nimport \"testing\"\n\n"
                "func TestTrackedFailure(t *testing.T) { t.Fatal(\"tracked failure\") }\n",
                encoding="utf-8",
            )
            self.run_git(repo, "add", ".")
            self.run_git(repo, "commit", "-q", "-m", "tracked failure")
            head = self.run_git(repo, "rev-parse", "HEAD")
            (package / "local_test.go").write_text(
                "package pkg\n\nimport (\n\t\"os\"\n\t\"testing\"\n)\n\n"
                "func TestMain(m *testing.M) { os.Exit(0) }\n",
                encoding="utf-8",
            )
            self.assertEqual(self.run_git(repo, "status", "--porcelain"), "")
            coverage = [
                {
                    "package": "./pkg",
                    "state": "runnable",
                    "ci_covered": False,
                    "module_root": ".",
                    "unverified_test_constraints": [],
                }
            ]
            result = FINAL_HEAD_REVIEW.run_go_tests(
                repo, head, coverage, GO_BINARY
            )

        self.assertEqual(result[0]["returncode"], 1)
        self.assertIn("tracked failure", result[0]["output_tail"])

    def test_direct_run_rejects_workspace_module_outside_exact_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            external.mkdir()
            (external / "go.mod").write_text(
                "module example.com/external\n\ngo 1.22\n", encoding="utf-8"
            )
            (external / "value.go").write_text(
                'package external\n\nfunc Value() string { return "outside" }\n',
                encoding="utf-8",
            )
            repo = root / "repo"
            app = repo / "app"
            app.mkdir(parents=True)
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "External Workspace Test")
            self.run_git(repo, "config", "user.email", "external@example.com")
            (app / "go.mod").write_text(
                "module example.com/app\n\ngo 1.22\n\n"
                "require example.com/external v0.0.0\n",
                encoding="utf-8",
            )
            (app / "app_test.go").write_text(
                'package app\n\nimport (\n\t"testing"\n\t"example.com/external"\n)\n\n'
                "func TestExternal(t *testing.T) {\n"
                '\tif external.Value() != "outside" { t.Fatal("wrong value") }\n'
                "}\n",
                encoding="utf-8",
            )
            (repo / "go.work").write_text(
                "go 1.22\n\nuse (\n\t./app\n\t../external\n)\n", encoding="utf-8"
            )
            self.run_git(repo, "add", ".")
            self.run_git(repo, "commit", "-q", "-m", "external workspace")
            head = self.run_git(repo, "rev-parse", "HEAD")
            coverage = [
                {
                    "package": "./app",
                    "state": "runnable",
                    "ci_covered": False,
                    "module_root": "app",
                    "unverified_test_constraints": [],
                }
            ]
            with self.assertRaisesRegex(ValueError, "outside the materialized exact-head tree"):
                FINAL_HEAD_REVIEW.run_go_tests(repo, head, coverage, GO_BINARY)

    def test_disabled_or_control_flow_workflow_cannot_claim_ci_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "CI Evidence Test")
            self.run_git(repo, "config", "user.email", "ci@example.com")
            (repo / "go.mod").write_text("module example.com/ci\n\ngo 1.22\n", encoding="utf-8")
            self.run_git(repo, "add", "go.mod")
            self.run_git(repo, "commit", "-q", "-m", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            workflow = repo / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "ci.yml").write_text(
                "jobs:\n"
                "  disabled:\n"
                "    if: false\n"
                "    steps:\n"
                "      - run: echo \"go test ./pkg/...\"\n"
                "  deceptive:\n"
                "    name: Deceptive test\n"
                "    steps:\n"
                "      - name: Claimed package test\n"
                "        run: true || go test ./pkg/...\n",
                encoding="utf-8",
            )
            package = repo / "pkg"
            package.mkdir()
            (package / "x_test.go").write_text(
                "package pkg\n\nimport \"testing\"\n\nfunc TestX(t *testing.T) {}\n",
                encoding="utf-8",
            )
            self.run_git(repo, "add", ".github/workflows/ci.yml", "pkg/x_test.go")
            self.run_git(repo, "commit", "-q", "-m", "add disabled test text")
            head = self.run_git(repo, "rev-parse", "HEAD")

            def scope(path: str, group: str) -> dict[str, object]:
                return {
                    "path": path,
                    "group": group,
                    "disposition": "keep",
                    "acceptance": "Exercise the changed behavior.",
                    "owning_surface": group,
                    "independently_mergeable": False,
                    "rationale": "The file belongs to the claimed test change.",
                    "evidence": ["Exact diff inspection."],
                }

            closure = root / "scope.json"
            closure_value = {
                "schema_version": 1,
                "target": self.TARGET,
                "base": base,
                "head": head,
                "merge_base": base,
                "files": [
                    scope(".github/workflows/ci.yml", "CI workflow"),
                    scope("pkg/x_test.go", "package test"),
                ],
            }
            closure.write_text(
                json.dumps(closure_value),
                encoding="utf-8",
            )

            result = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The changed behavior must be tested.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )
            closure_value["ci_tests"] = [
                {
                    "package": "./pkg",
                    "status": "passed",
                    "command": "true || go test ./pkg/...",
                    "job_url": (
                        "https://github.com/volcano-sh/agentcube/actions/runs/123/job/456"
                    ),
                    "evidence": ["The enclosing step was green."],
                }
            ]
            closure.write_text(json.dumps(closure_value), encoding="utf-8")
            claimed = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "The changed behavior must be tested.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        package_row = report["changed_go_test_coverage"][0]
        self.assertFalse(package_row["ci_covered"])
        self.assertEqual(len(package_row["workflow_candidates"]), 1)
        self.assertFalse(package_row["workflow_candidates"][0]["ci_waivable"])
        self.assertEqual(report["uncovered_changed_go_test_packages"], ["./pkg"])
        self.assertEqual(claimed.returncode, 2)
        self.assertIn("not a control-flow-free direct", claimed.stderr)

    def test_ci_closure_rejects_free_text_and_verifies_exact_job_step(self) -> None:
        command = "go test ./pkg/..."
        candidate = {
            "workflow": ".github/workflows/ci.yml",
            "job": "test",
            "job_name": "Go tests",
            "step": "Run package tests",
            "step_index": 1,
            "source": ".github/workflows/ci.yml:test:Run package tests",
            "command": command,
            "scopes": ["./pkg/..."],
            "ci_waivable": True,
            "exact_head_checkout": True,
            "nested_module_packages": [],
        }
        value = {
            "schema_version": 1,
            "target": self.TARGET,
            "head": "a" * 40,
            "ci_tests": [
                {
                    "package": "./pkg",
                    "status": "passed",
                    "command": command,
                    "source": "trust me",
                    "evidence": ["Claimed pass."],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job_url must be a non-empty string"):
                FINAL_HEAD_REVIEW.load_manual_evidence_closure(
                    str(closure),
                    "a" * 40,
                    self.TARGET,
                    [],
                    [{"package": "./pkg", "state": "runnable"}],
                    [candidate],
                    [],
                )

            value["ci_tests"][0]["job_url"] = (
                "https://github.com/volcano-sh/agentcube/actions/runs/123/job/456"
            )
            closure.write_text(json.dumps(value), encoding="utf-8")
            declared = FINAL_HEAD_REVIEW.load_manual_evidence_closure(
                str(closure),
                "a" * 40,
                self.TARGET,
                [],
                [{"package": "./pkg", "state": "runnable"}],
                [candidate],
                [],
            )["ci_tests"]
            with mock.patch.object(
                FINAL_HEAD_REVIEW,
                "github_json",
                side_effect=[
                    {
                        "head_sha": "a" * 40,
                        "conclusion": "success",
                        "event": "push",
                        "path": ".github/workflows/ci.yml",
                    },
                    {
                        "run_id": 123,
                        "conclusion": "success",
                        "name": "Go tests",
                        "steps": [
                            {
                                "name": "Run package tests",
                                "number": 2,
                                "conclusion": "skipped",
                            },
                            {
                                "name": "Run package tests",
                                "number": 3,
                                "conclusion": "success",
                            },
                        ],
                    },
                ],
            ):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    FINAL_HEAD_REVIEW.verify_ci_tests(
                        declared, "a" * 40, self.TARGET, 1.0
                    )
            with mock.patch.object(
                FINAL_HEAD_REVIEW,
                "github_json",
                side_effect=[
                    {
                        "head_sha": "a" * 40,
                        "conclusion": "success",
                        "event": "pull_request",
                        "path": ".github/workflows/ci.yml@refs/pull/446/merge",
                    },
                    {
                        "run_id": 123,
                        "conclusion": "success",
                        "name": "Go tests",
                        "steps": [
                            {
                                "name": "Run package tests",
                                "number": 2,
                                "conclusion": "success",
                            }
                        ],
                    },
                ],
            ):
                with self.assertRaisesRegex(ValueError, "event is not eligible"):
                    FINAL_HEAD_REVIEW.verify_ci_tests(
                        declared, "a" * 40, self.TARGET, 1.0
                    )
            with mock.patch.object(
                FINAL_HEAD_REVIEW,
                "github_json",
                side_effect=[
                    {
                        "head_sha": "a" * 40,
                        "conclusion": "success",
                        "event": "push",
                        "path": ".github/workflows/ci.yml@refs/pull/446/merge",
                    },
                    {
                        "run_id": 123,
                        "conclusion": "success",
                        "name": "Go tests",
                        "steps": [
                            {
                                "name": "Run package tests",
                                "number": 2,
                                "conclusion": "success",
                            }
                        ],
                    },
                ],
            ):
                verified = FINAL_HEAD_REVIEW.verify_ci_tests(
                    declared, "a" * 40, self.TARGET, 1.0
                )

        self.assertEqual(verified["./pkg"]["verified_run_id"], 123)
        self.assertEqual(verified["./pkg"]["verified_step_name"], "Run package tests")

    def test_unclassified_boundary_lead_blocks_until_exact_surface_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Boundary Test")
            self.run_git(repo, "config", "user.email", "boundary@example.com")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            self.run_git(repo, "add", "README.md")
            self.run_git(repo, "commit", "-q", "-m", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            changed_path = "scripts/version.sh"
            script = repo / changed_path
            script.parent.mkdir()
            evidence = 'if [[ "${VERSION}" < "v0.5.0" ]]; then'
            script.write_text(f"{evidence}\n  exit 1\nfi\n", encoding="utf-8")
            self.run_git(repo, "add", changed_path)
            self.run_git(repo, "commit", "-q", "-m", "add version gate")
            head = self.run_git(repo, "rev-parse", "HEAD")
            lead = {
                "id": "lexicographic-version-comparison",
                "path": changed_path,
                "evidence": evidence,
            }
            lead_key = FINAL_HEAD_REVIEW.boundary_lead_key(lead)
            closure_value = {
                "schema_version": 1,
                "target": self.TARGET,
                "base": base,
                "head": head,
                "merge_base": base,
                "files": [
                    {
                        "path": changed_path,
                        "group": "version compatibility",
                        "disposition": "keep",
                        "acceptance": "Reject unsupported versions.",
                        "owning_surface": "upgrade script",
                        "independently_mergeable": False,
                        "rationale": "The upgrade contract needs a version gate.",
                        "evidence": ["Acceptance contract."],
                    }
                ],
            }
            closure = root / "scope.json"
            closure.write_text(json.dumps(closure_value), encoding="utf-8")
            arguments = (
                "--no-carry-forward-findings",
                "--acceptance-note",
                "Unsupported versions must be rejected.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )

            missing = self.run_repo_cli(repo, base, head, *arguments)
            closure_value["boundary_leads"] = [
                {
                    "key": lead_key,
                    "status": "resolved",
                    "rationale": "The accepted inputs use zero-padded versions.",
                    "evidence": ["Focused boundary test covers v0.04 and v0.05."],
                }
            ]
            closure.write_text(json.dumps(closure_value), encoding="utf-8")
            resolved = self.run_repo_cli(repo, base, head, *arguments)

        self.assertEqual(missing.returncode, 1, missing.stderr)
        missing_report = json.loads(missing.stdout)
        self.assertEqual(missing_report["gate"]["boundary_closure"], "incomplete")
        self.assertEqual(missing_report["boundary_leads"][0]["key"], lead_key)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertEqual(json.loads(resolved.stdout)["gate"]["boundary_closure"], "complete")

    def test_structural_merge_conflict_blocks_ready_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.run_git(repo, "init", "-q")
            self.run_git(repo, "config", "user.name", "Conflict Test")
            self.run_git(repo, "config", "user.email", "conflict@example.com")
            changed_path = "config.txt"
            (repo / changed_path).write_text("value=base\n", encoding="utf-8")
            self.run_git(repo, "add", changed_path)
            self.run_git(repo, "commit", "-q", "-m", "common base")
            merge_base = self.run_git(repo, "rev-parse", "HEAD")

            self.run_git(repo, "checkout", "-q", "-b", "feature")
            (repo / changed_path).write_text("value=feature\n", encoding="utf-8")
            self.run_git(repo, "commit", "-q", "-am", "feature side")
            head = self.run_git(repo, "rev-parse", "HEAD")
            self.run_git(repo, "checkout", "-q", "-b", "target", merge_base)
            (repo / changed_path).write_text("value=target\n", encoding="utf-8")
            self.run_git(repo, "commit", "-q", "-am", "target side")
            base = self.run_git(repo, "rev-parse", "HEAD")

            closure = root / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "base": base,
                        "head": head,
                        "merge_base": merge_base,
                        "files": [
                            {
                                "path": changed_path,
                                "group": "feature configuration",
                                "disposition": "keep",
                                "acceptance": "Set the feature value.",
                                "owning_surface": "configuration",
                                "independently_mergeable": False,
                                "rationale": "The accepted feature changes this value.",
                                "evidence": ["Exact feature-side diff."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_repo_cli(
                repo,
                base,
                head,
                "--no-carry-forward-findings",
                "--acceptance-note",
                "Set the feature value.",
                "--scope-closure",
                str(closure),
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["surface"]["structurally_mergeable"])
        self.assertEqual(report["gate"]["structural_mergeability"], "conflicted")

    def test_make_test_is_resolved_but_docker_build_is_not_assumed_to_test(self) -> None:
        targets = FINAL_HEAD_REVIEW.parse_makefile(
            "test:\n\tgo test -v ./...\n\n"
            "docker-build:\n\tdocker build .\n"
        )

        self.assertEqual(
            FINAL_HEAD_REVIEW.resolve_make_go_tests("test", targets),
            [("go test -v ./...", ["./..."])],
        )
        self.assertEqual(FINAL_HEAD_REVIEW.resolve_make_go_tests("docker-build", targets), [])

    def test_make_e2e_shell_script_is_discoverable(self) -> None:
        targets = FINAL_HEAD_REVIEW.parse_makefile(
            "e2e:\n\t./test/e2e/run_e2e.sh\n"
        )

        recipes = FINAL_HEAD_REVIEW.resolve_make_recipes("e2e", targets)

        self.assertEqual(recipes, ["./test/e2e/run_e2e.sh"])
        self.assertEqual(
            FINAL_HEAD_REVIEW.shell_script_paths(recipes[0]),
            ["test/e2e/run_e2e.sh"],
        )

    def test_boundary_checks_find_pr446_classes(self) -> None:
        added = {
            "test/e2e/run_e2e.sh": ['if [[ "${VERSION}" < "v0.5.0" ]]; then'],
            "docs/getting-started.md": [
                "wget https://github.com/example/project/releases/download/v0.5.3/migrate.sh"
            ],
            "hack/update-codegen.sh": ["export PATH=/home/alice/go/bin:$PATH"],
        }
        deleted = {"pkg/workloadmanager/handlers.go": ["if err := request.Validate(); err != nil {"]}

        leads, urls = FINAL_HEAD_REVIEW.boundary_leads(added, deleted)

        self.assertEqual(
            {item["id"] for item in leads},
            {
                "lexicographic-version-comparison",
                "personal-absolute-path",
                "removed-validation-call",
            },
        )
        self.assertEqual(
            urls,
            ["https://github.com/example/project/releases/download/v0.5.3/migrate.sh"],
        )

    def test_present_boundary_closure_remains_blocking(self) -> None:
        lead = {
            "id": "removed-validation-call",
            "path": "pkg/handler.go",
            "evidence": "if err := request.Validate(); err != nil {",
        }
        lead_key = FINAL_HEAD_REVIEW.boundary_lead_key(lead)
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "scope.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": self.TARGET,
                        "head": "a" * 40,
                        "boundary_leads": [
                            {
                                "key": lead_key,
                                "status": "present",
                                "rationale": "The replacement path does not validate input.",
                                "evidence": ["Production call-chain inspection."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = FINAL_HEAD_REVIEW.load_manual_evidence_closure(
                str(closure), "a" * 40, self.TARGET, [lead], [], [], []
            )

        self.assertEqual(result["blocking_boundary_keys"], [lead_key])
        self.assertEqual(FINAL_HEAD_REVIEW.boundary_closure_state(result), "blocked")

    def test_changed_lines_uses_canonical_path_not_quoted_patch_header(self) -> None:
        changed_path = "docs/a\tb\nc.md"
        patch = (
            'diff --git "a/docs/a\\tb\\nc.md" "b/docs/a\\tb\\nc.md"\n'
            "new file mode 100644\n"
            "--- /dev/null\n"
            '+++ "b/docs/a\\tb\\nc.md"\n'
            "@@ -0,0 +1 @@\n"
            "+curl https://example.com/tool\n"
        )
        completed = FINAL_HEAD_REVIEW.subprocess.CompletedProcess
        with mock.patch.object(
            FINAL_HEAD_REVIEW,
            "git",
            return_value=completed([], 0, stdout=patch, stderr=""),
        ):
            added, deleted = FINAL_HEAD_REVIEW.changed_lines(
                Path("."),
                "base",
                "head",
                [{"status": "A", "path": changed_path}],
            )

        self.assertEqual(added, {changed_path: ["curl https://example.com/tool"]})
        self.assertEqual(deleted, {})

    def test_variable_urls_require_manual_resolution_without_becoming_false_404s(self) -> None:
        results = FINAL_HEAD_REVIEW.check_urls(
            ["https://example.com/releases/${VERSION}/asset.yaml"], timeout=0.1
        )

        self.assertEqual(
            results,
            [
                {
                    "url": "https://example.com/releases/${VERSION}/asset.yaml",
                    "status": "unresolved-variable",
                    "ok": None,
                }
            ],
        )

    def test_acceptance_candidates_require_explicit_contract_language(self) -> None:
        candidates = FINAL_HEAD_REVIEW.acceptance_candidates(
            [],
            [
                "Existing v0.4.6 SandboxClaims must have a tested upgrade path.",
                "",
            ],
        )

        self.assertEqual(
            candidates,
            ["Existing v0.4.6 SandboxClaims must have a tested upgrade path."],
        )

    def test_finding_ledger_requires_exact_head_closure_for_every_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "ledger.json"
            closure = root / "closure.json"
            ledger.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "agent-sandbox-upgrade",
                        "ledger_version": 2,
                        "findings": [
                            {
                                "id": "public-api-signature",
                                "summary": "Preserve the exported Resource signature.",
                                "provenance": ["PR #442 local review"],
                                "paths": ["pkg/apis/runtime/v1alpha1/register.go"],
                            },
                            {
                                "id": "codegen-version",
                                "summary": "Align Kubernetes libraries and code-generator.",
                                "provenance": ["PR #442 local review"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ledger_digest = FINAL_HEAD_REVIEW.json_object_digest(
                json.loads(ledger.read_text(encoding="utf-8"))
            )
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "agent-sandbox-upgrade",
                        "ledger_version": 2,
                        "ledger_digest": ledger_digest,
                        "target": {
                            "repository": "volcano-sh/agentcube",
                            "pull_request": 446,
                        },
                        "head": "a" * 40,
                        "closures": [
                            {
                                "id": "public-api-signature",
                                "status": "fixed",
                                "evidence": ["Resource still returns GroupVersionResource."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            findings = FINAL_HEAD_REVIEW.load_finding_ledger([str(ledger)])
            result = FINAL_HEAD_REVIEW.close_finding_ledger(
                findings, [str(closure)], "a" * 40, self.TARGET
            )

            self.assertEqual(result["missing_ids"], ["codegen-version"])
            self.assertEqual(FINAL_HEAD_REVIEW.finding_closure_state(result), "incomplete")
            result["missing_ids"] = []
            self.assertEqual(FINAL_HEAD_REVIEW.finding_closure_state(result), "complete")
            result["head_matches"] = False
            self.assertEqual(FINAL_HEAD_REVIEW.finding_closure_state(result), "stale-head")

    def test_empty_finding_ledger_cannot_bypass_closure_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "empty-ledger",
                        "ledger_version": 1,
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "findings must not be empty"):
                FINAL_HEAD_REVIEW.load_finding_ledger([str(ledger)])

    def test_boolean_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "schema_version": True,
                        "ledger_id": "upgrade",
                        "ledger_version": 1,
                        "findings": [{"id": "finding-a"}],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
                FINAL_HEAD_REVIEW.load_finding_ledger([str(ledger)])

    def test_closure_without_finding_ledger_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a non-empty"):
            FINAL_HEAD_REVIEW.close_finding_ledger(
                [], ["closure.json"], "a" * 40, self.TARGET
            )

    def test_explicit_no_carry_mode_is_preserved_in_result(self) -> None:
        result = FINAL_HEAD_REVIEW.close_finding_ledger(
            [], [], "a" * 40, self.TARGET, no_carry_forward_findings=True
        )

        self.assertEqual(result["mode"], "none-declared")
        closure_state = FINAL_HEAD_REVIEW.finding_closure_state(result)
        self.assertEqual(closure_state, "none-declared")
        self.assertEqual(
            FINAL_HEAD_REVIEW.finding_readiness_state(result, closure_state),
            {"state": "not-applicable", "blocking_ids": []},
        )

    def test_unspecified_carry_mode_remains_unassessed(self) -> None:
        result = FINAL_HEAD_REVIEW.close_finding_ledger(
            [], [], "a" * 40, self.TARGET
        )

        self.assertEqual(result["mode"], "unspecified")
        closure_state = FINAL_HEAD_REVIEW.finding_closure_state(result)
        self.assertEqual(closure_state, "not-provided")
        self.assertEqual(
            FINAL_HEAD_REVIEW.finding_readiness_state(result, closure_state),
            {"state": "not-assessed", "blocking_ids": []},
        )

    def test_non_string_closure_status_is_rejected_without_traceback(self) -> None:
        findings = [
            {
                "id": "finding-a",
                "summary": "Keep the contract.",
                "provenance": ["review"],
                "paths": [],
                "ledger_id": "upgrade",
                "ledger_version": 1,
                "ledger_digest": "b" * 64,
                "ledger_source": "ledger.json",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "closure.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "upgrade",
                        "ledger_version": 1,
                        "ledger_digest": "b" * 64,
                        "target": {
                            "repository": "volcano-sh/agentcube",
                            "pull_request": 446,
                        },
                        "head": "a" * 40,
                        "closures": [
                            {
                                "id": "finding-a",
                                "status": ["fixed"],
                                "evidence": ["code evidence"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "status must be one of"):
                FINAL_HEAD_REVIEW.close_finding_ledger(
                    findings, [str(closure)], "a" * 40, self.TARGET
                )

    def test_closure_must_match_finding_ledger_version(self) -> None:
        findings = [
            {
                "id": "finding-a",
                "summary": "Keep the contract.",
                "provenance": ["review"],
                "paths": [],
                "ledger_id": "upgrade",
                "ledger_version": 2,
                "ledger_digest": "b" * 64,
                "ledger_source": "ledger.json",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "closure.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "upgrade",
                        "ledger_version": 1,
                        "ledger_digest": "b" * 64,
                        "target": {
                            "repository": "volcano-sh/agentcube",
                            "pull_request": 446,
                        },
                        "head": "a" * 40,
                        "closures": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match"):
                FINAL_HEAD_REVIEW.close_finding_ledger(
                    findings, [str(closure)], "a" * 40, self.TARGET
                )

    def test_closure_must_match_canonical_ledger_digest(self) -> None:
        findings = [
            {
                "id": "finding-a",
                "summary": "Keep the contract.",
                "provenance": ["review"],
                "paths": [],
                "ledger_id": "upgrade",
                "ledger_version": 2,
                "ledger_digest": "a" * 64,
                "ledger_source": "ledger.json",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "closure.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "upgrade",
                        "ledger_version": 2,
                        "ledger_digest": "b" * 64,
                        "target": {
                            "repository": "volcano-sh/agentcube",
                            "pull_request": 446,
                        },
                        "head": "a" * 40,
                        "closures": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError, "does not match supplied ledger content"
            ):
                FINAL_HEAD_REVIEW.close_finding_ledger(
                    findings, [str(closure)], "a" * 40, self.TARGET
                )

    def test_closure_target_must_match_command_line_target(self) -> None:
        findings = [
            {
                "id": "finding-a",
                "summary": "Keep the contract.",
                "provenance": ["review"],
                "paths": [],
                "ledger_id": "upgrade",
                "ledger_version": 1,
                "ledger_digest": "b" * 64,
                "ledger_source": "ledger.json",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            closure = Path(directory) / "closure.json"
            closure.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ledger_id": "upgrade",
                        "ledger_version": 1,
                        "ledger_digest": "b" * 64,
                        "target": {
                            "repository": "volcano-sh/agentcube",
                            "pull_request": 442,
                        },
                        "head": "a" * 40,
                        "closures": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match command-line target"):
                FINAL_HEAD_REVIEW.close_finding_ledger(
                    findings, [str(closure)], "a" * 40, self.TARGET
                )

    def test_decision_statuses_require_current_pr_and_maintainer_evidence(self) -> None:
        target = {"repository": "volcano-sh/agentcube", "pull_request": 446}
        with self.assertRaisesRegex(ValueError, "structured decision evidence"):
            FINAL_HEAD_REVIEW.validate_decision_evidence(
                {"id": "duplicate"},
                "duplicate-on-current-pr",
                target,
                Path("closure.json"),
            )
        with self.assertRaisesRegex(ValueError, "maintainer author_association"):
            FINAL_HEAD_REVIEW.validate_decision_evidence(
                {
                    "id": "accepted",
                    "decision": {
                        "url": "https://github.com/volcano-sh/agentcube/pull/446#issuecomment-1",
                        "author": "reviewer",
                        "author_association": "CONTRIBUTOR",
                    },
                },
                "accepted-by-maintainer",
                target,
                Path("closure.json"),
            )
        with self.assertRaisesRegex(ValueError, "maintainer author_association"):
            FINAL_HEAD_REVIEW.validate_decision_evidence(
                {
                    "id": "accepted",
                    "decision": {
                        "url": "https://github.com/volcano-sh/agentcube/pull/446#issuecomment-1",
                        "author": "reviewer",
                        "author_association": ["MEMBER"],
                    },
                },
                "accepted-by-maintainer",
                target,
                Path("closure.json"),
            )

    def test_run_go_tests_rejects_dirty_exact_head_worktree(self) -> None:
        completed = FINAL_HEAD_REVIEW.subprocess.CompletedProcess
        with mock.patch.object(
            FINAL_HEAD_REVIEW,
            "git",
            side_effect=[
                completed([], 0, stdout="a" * 40, stderr=""),
                completed([], 0, stdout="a" * 40, stderr=""),
                completed([], 0, stdout=" M cmd/workload-manager/main_test.go\n", stderr=""),
            ],
        ):
            with self.assertRaisesRegex(ValueError, "requires a clean worktree"):
                FINAL_HEAD_REVIEW.run_go_tests(Path("."), "HEAD", [])

    def test_present_or_duplicate_findings_block_review_readiness(self) -> None:
        closure = {
            "missing_ids": [],
            "rows": [
                {"id": "fixed", "status": "fixed"},
                {"id": "present", "status": "present"},
                {"id": "duplicate", "status": "duplicate-on-current-pr"},
                {"id": "accepted", "status": "accepted-by-maintainer"},
            ],
        }

        readiness = FINAL_HEAD_REVIEW.finding_readiness_state(closure, "complete")

        self.assertEqual(readiness["state"], "blocked")
        self.assertEqual(readiness["blocking_ids"], ["present", "duplicate"])
        closure["rows"][1]["status"] = "fixed"
        closure["rows"][2]["status"] = "not-applicable"
        self.assertEqual(
            FINAL_HEAD_REVIEW.finding_readiness_state(closure, "complete"),
            {"state": "ready", "blocking_ids": []},
        )

    def test_exported_go_signatures_make_return_type_changes_visible(self) -> None:
        before = FINAL_HEAD_REVIEW.exported_go_function_signatures(
            "package api\n\nfunc Resource(name string) schema.GroupVersionResource { return value }\n"
        )
        after = FINAL_HEAD_REVIEW.exported_go_function_signatures(
            "package api\n\nfunc Resource(name string) schema.GroupResource { return value }\n"
        )

        self.assertEqual(before["Resource"], "func Resource(name string) schema.GroupVersionResource")
        self.assertNotEqual(before["Resource"], after["Resource"])

    def test_kubernetes_codegen_minor_skew_is_a_boundary_lead(self) -> None:
        contents = {
            "go.mod": (
                "module example\nrequire (\n"
                "k8s.io/api v0.36.2\n"
                "k8s.io/apimachinery v0.36.2\n"
                "k8s.io/client-go v0.36.2\n)\n"
            ),
            "hack/update-codegen.sh": 'CODEGEN_VERSION="v0.35.4"\n',
        }
        with mock.patch.object(
            FINAL_HEAD_REVIEW.review_surface,
            "object_text",
            side_effect=lambda _repo, _head, path: contents.get(path),
        ):
            leads = FINAL_HEAD_REVIEW.kubernetes_codegen_alignment_leads(
                Path("."),
                "HEAD",
                [
                    {"status": "M", "path": "go.mod"},
                    {"status": "M", "path": "hack/update-codegen.sh"},
                ],
            )

        self.assertEqual([item["id"] for item in leads], ["kubernetes-codegen-version-skew"])
        self.assertIn("k8s.io/code-generator=v0.35.4", leads[0]["evidence"])


if __name__ == "__main__":
    unittest.main()
