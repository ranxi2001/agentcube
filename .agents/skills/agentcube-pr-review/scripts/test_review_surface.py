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
            'env:\n  MTLS_ENABLED: "false"\n',
            "func TestCodeInterpreterWarmPool(t *testing.T) {\n\tskipIfMTLS(t)\n}\n",
        )

        self.assertFalse(coverage["warm_pool_skipped_by_default"])


if __name__ == "__main__":
    unittest.main()
