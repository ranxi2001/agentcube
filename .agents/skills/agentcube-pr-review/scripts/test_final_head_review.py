#!/usr/bin/env python3

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("final_head_review.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("final_head_review", SCRIPT)
assert SPEC and SPEC.loader
FINAL_HEAD_REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL_HEAD_REVIEW)


class FinalHeadReviewTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
