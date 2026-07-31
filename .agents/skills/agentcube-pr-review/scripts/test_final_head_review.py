#!/usr/bin/env python3

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("final_head_review.py")
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

        coverage = FINAL_HEAD_REVIEW.package_coverage(packages, evidence)

        self.assertEqual(evidence[0]["scopes"], ["./pkg/..."])
        self.assertFalse(coverage[0]["ci_covered"])
        self.assertTrue(coverage[1]["ci_covered"])

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
