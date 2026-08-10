#!/usr/bin/env python3

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("review_surface.py")
SPEC = importlib.util.spec_from_file_location("review_surface", SCRIPT)
assert SPEC and SPEC.loader
REVIEW_SURFACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW_SURFACE)


class ReviewSurfaceTest(unittest.TestCase):
    def test_build_report_freezes_refs_to_shas_before_reading_surface(self) -> None:
        base_ref = "moving-base"
        head_ref = "moving-head"
        base_sha = "a" * 40
        head_sha = "b" * 40
        calls: list[tuple[str, ...]] = []

        def fake_git(
            _repo: Path, *arguments: str, check: bool = True
        ) -> subprocess.CompletedProcess[str]:
            calls.append(arguments)
            if arguments == ("rev-parse", base_ref):
                output = f"{base_sha}\n"
            elif arguments == ("rev-parse", head_ref):
                output = f"{head_sha}\n"
            elif arguments[:1] == ("merge-base",) and "--is-ancestor" not in arguments:
                output = f"{base_sha}\n"
            else:
                output = ""
            return subprocess.CompletedProcess([], 0, stdout=output, stderr="")

        with (
            mock.patch.object(REVIEW_SURFACE, "git", side_effect=fake_git),
            mock.patch.object(
                REVIEW_SURFACE,
                "dependency_runtime_versions",
                return_value={"go_dependency": None, "e2e_default": None},
            ),
            mock.patch.object(
                REVIEW_SURFACE,
                "codeinterpreter_e2e_coverage",
                return_value={
                    "default_mtls_enabled": False,
                    "workflow_disables_mtls": False,
                    "warm_pool_skips_when_mtls": False,
                    "warm_pool_skipped_by_default": False,
                },
            ),
        ):
            report = REVIEW_SURFACE.build_report(Path("."), base_ref, head_ref)

        self.assertEqual(report["base"]["sha"], base_sha)
        self.assertEqual(report["head"]["sha"], head_sha)
        for arguments in calls[2:]:
            self.assertNotIn(base_ref, arguments)
            self.assertNotIn(head_ref, arguments)

    def test_nul_changed_file_parser_preserves_unicode_tabs_and_renames(self) -> None:
        files = REVIEW_SURFACE.parse_changed_files(
            "M\0pkg/é_test.go\0R100\0old\tname.go\0new\nname.go\0"
        )

        self.assertEqual(
            files,
            [
                {"status": "M", "path": "pkg/é_test.go"},
                {
                    "status": "R100",
                    "old_path": "old\tname.go",
                    "path": "new\nname.go",
                },
            ],
        )

    def test_nul_changed_file_parser_rejects_truncated_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete NUL-delimited"):
            REVIEW_SURFACE.parse_changed_files("R100\0old.go\0")

    def test_extracts_agent_sandbox_dependency_and_runtime_versions(self) -> None:
        versions = REVIEW_SURFACE.extract_agent_sandbox_versions(
            "require sigs.k8s.io/agent-sandbox v0.4.6\n",
            "AGENT_SANDBOX_VERSION=${AGENT_SANDBOX_VERSION:-v0.1.1}\n",
        )

        self.assertEqual(
            versions,
            {"go_dependency": "0.4.6", "e2e_default": "0.1.1"},
        )

    def test_missing_runtime_default_is_not_invented(self) -> None:
        versions = REVIEW_SURFACE.extract_agent_sandbox_versions(
            "require sigs.k8s.io/agent-sandbox v0.4.6\n",
            "AGENT_SANDBOX_VERSION=${AGENT_SANDBOX_VERSION}\n",
        )

        self.assertEqual(
            versions,
            {"go_dependency": "0.4.6", "e2e_default": None},
        )

    def test_detects_warm_pool_test_skipped_by_default_mtls(self) -> None:
        coverage = REVIEW_SURFACE.extract_codeinterpreter_e2e_coverage(
            "if true; then\n  MTLS_ENABLED=true\nfi\n",
            "run: make e2e\n",
            "func TestCodeInterpreterWarmPool(t *testing.T) {\n\tskipIfMTLS(t)\n}\n",
        )

        self.assertTrue(coverage["warm_pool_skipped_by_default"])

    def test_workflow_override_enables_warm_pool_test(self) -> None:
        coverage = REVIEW_SURFACE.extract_codeinterpreter_e2e_coverage(
            "if true; then\n  MTLS_ENABLED=true\nfi\n",
            'env:\n  MTLS_ENABLED: "false"\nrun: make e2e\n',
            "func TestCodeInterpreterWarmPool(t *testing.T) {\n\tskipIfMTLS(t)\n}\n",
        )

        self.assertFalse(coverage["warm_pool_skipped_by_default"])

    def test_matrix_false_path_enables_warm_pool_test(self) -> None:
        coverage = REVIEW_SURFACE.extract_codeinterpreter_e2e_coverage(
            "MTLS_ENABLED=true\n",
            """strategy:
  matrix:
    include:
      - mtls_enabled: \"true\"
      - mtls_enabled: \"false\"
steps:
  - env:
      MTLS_ENABLED: ${{ matrix.mtls_enabled }}
    run: make e2e
""",
            "func TestCodeInterpreterWarmPool(t *testing.T) {\n\tskipIfMTLS(t)\n}\n",
        )

        self.assertTrue(coverage["workflow_disables_mtls"])
        self.assertFalse(coverage["warm_pool_skipped_by_default"])

    def test_unreferenced_matrix_false_does_not_invent_mtls_path(self) -> None:
        coverage = REVIEW_SURFACE.extract_codeinterpreter_e2e_coverage(
            "MTLS_ENABLED=true\n",
            """strategy:
  matrix:
    include:
      - require_codeinterpreter: \"false\"
steps:
  - env:
      MTLS_ENABLED: ${{ matrix.mtls_enabled }}
    run: make e2e
""",
            "func TestCodeInterpreterWarmPool(t *testing.T) {\n\tskipIfMTLS(t)\n}\n",
        )

        self.assertFalse(coverage["workflow_disables_mtls"])
        self.assertTrue(coverage["warm_pool_skipped_by_default"])

    def test_matrix_values_are_scoped_to_the_e2e_job(self) -> None:
        workflow = """jobs:
  e2e:
    strategy:
      matrix:
        mtls_enabled: [\"true\"]
    steps:
      - env:
          MTLS_ENABLED: ${{ matrix.mtls_enabled }}
        run: make e2e
  unrelated:
    strategy:
      matrix:
        mtls_enabled: [\"true\", \"false\"]
    steps:
      - run: echo unrelated
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_block_list_matrix_false_enables_the_e2e_job(self) -> None:
        workflow = """jobs:
  e2e:
    strategy:
      matrix:
        mtls_enabled:
          - \"true\"
          - \"false\"
    steps:
      - env:
          MTLS_ENABLED: ${{ matrix.mtls_enabled }}
        run: make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_step_env_does_not_leak_to_another_step_in_the_same_job(self) -> None:
        workflow = """jobs:
  e2e:
    steps:
      - env:
          MTLS_ENABLED: \"false\"
        run: echo unrelated
      - run: make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_job_env_applies_to_the_e2e_step(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: \"false\"
    steps:
      - run: make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_disabled_env_without_an_e2e_command_is_not_coverage(self) -> None:
        self.assertFalse(
            REVIEW_SURFACE.workflow_has_mtls_disabled_path(
                'env:\n  MTLS_ENABLED: "false"\nrun: echo unrelated\n'
            )
        )

    def test_excluded_false_matrix_value_is_not_an_execution_path(self) -> None:
        workflow = """jobs:
  e2e:
    strategy:
      matrix:
        mtls_enabled: [\"true\", \"false\"]
        exclude:
          - mtls_enabled: \"false\"
    steps:
      - env:
          MTLS_ENABLED: ${{ matrix.mtls_enabled }}
        run: make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_inline_shell_assignment_applies_to_the_e2e_command(self) -> None:
        workflow = """jobs:
  e2e:
    steps:
      - run: MTLS_ENABLED=false make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_multidimensional_excludes_remove_every_false_combination(self) -> None:
        workflow = """jobs:
  e2e:
    strategy:
      matrix:
        mtls_enabled: [true, false]
        runner: [ubuntu, windows]
        exclude:
          - mtls_enabled: false
            runner: ubuntu
          - mtls_enabled: false
            runner: windows
    steps:
      - env:
          MTLS_ENABLED: ${{ matrix.mtls_enabled }}
        run: make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_include_can_readd_a_false_combination_after_exclude(self) -> None:
        workflow = """jobs:
  e2e:
    strategy:
      matrix:
        mtls_enabled: [true, false]
        exclude:
          - mtls_enabled: false
        include:
          - mtls_enabled: false
    steps:
      - env:
          MTLS_ENABLED: ${{ matrix.mtls_enabled }}
        run: make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_step_env_true_overrides_job_env_false(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: false
    steps:
      - env:
          MTLS_ENABLED: true
        run: make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_workflow_env_applies_to_the_e2e_step(self) -> None:
        workflow = """env:
  MTLS_ENABLED: false
jobs:
  e2e:
    steps:
      - run: make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_job_env_overrides_workflow_env(self) -> None:
        workflow = """env:
  MTLS_ENABLED: false
jobs:
  e2e:
    env:
      MTLS_ENABLED: true
    steps:
      - run: make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_export_after_e2e_does_not_change_that_execution(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: true
    steps:
      - run: |
          make e2e
          export MTLS_ENABLED=false
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_temporary_assignment_to_other_command_does_not_leak(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: true
    steps:
      - run: MTLS_ENABLED=false echo disabled && make e2e
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_e2e_text_passed_to_echo_is_not_an_execution(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: false
    steps:
      - run: echo "make e2e"
"""

        self.assertFalse(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))

    def test_export_before_e2e_changes_that_execution(self) -> None:
        workflow = """jobs:
  e2e:
    env:
      MTLS_ENABLED: true
    steps:
      - run: |
          export MTLS_ENABLED=false
          make e2e
"""

        self.assertTrue(REVIEW_SURFACE.workflow_has_mtls_disabled_path(workflow))


if __name__ == "__main__":
    unittest.main()
