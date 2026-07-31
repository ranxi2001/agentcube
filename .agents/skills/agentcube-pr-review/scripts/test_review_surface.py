#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("review_surface.py")
SPEC = importlib.util.spec_from_file_location("review_surface", SCRIPT)
assert SPEC and SPEC.loader
REVIEW_SURFACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW_SURFACE)


class ReviewSurfaceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
