from __future__ import annotations

import unittest

from scripts.repair_v3_ci_sources import (
    repair_candidate,
    repair_service_smoke,
    repair_storage_smoke,
    repair_workflow,
)


class V3CISourceRepairTests(unittest.TestCase):
    def test_workflow_shell_and_contract_repairs_are_idempotent(self) -> None:
        source = (
            "    timeout-minutes: 45\n    strategy:\n"
            "          if ($LASTEXITCODE -ne 0) { throw 'V3 Clean unit tests failed' }\n"
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\n"
        )
        repaired = repair_workflow(source)
        self.assertIn("        shell: bash", repaired)
        self.assertNotIn("$LASTEXITCODE", repaired)
        self.assertIn("unified-master-orchestrator-v3-full", repaired)
        self.assertIn("'6^6'", repaired)
        self.assertIn("-ne 46656", repaired)
        self.assertEqual(repair_workflow(repaired), repaired)

    def test_service_smoke_bootstraps_v3_package_root(self) -> None:
        source = "import os\nimport tempfile\nfrom pathlib import Path\n\nfrom research_os_v3 import DataLayout\n"
        repaired = repair_service_smoke(source)
        self.assertIn("import sys", repaired)
        self.assertIn("PROJECT_ROOT = Path(__file__).resolve().parents[1]", repaired)
        self.assertIn("sys.path.insert(0, str(PROJECT_ROOT))", repaired)
        self.assertEqual(repair_service_smoke(repaired), repaired)

    def test_storage_evidence_uses_logical_scopes_not_relative_to(self) -> None:
        source = (
            '            "user_a_scope": str(alice_again.root.relative_to(second.root)),\n'
            '            "user_b_scope": str(bob_again.root.relative_to(second.root)),'
        )
        repaired = repair_storage_smoke(source)
        self.assertIn('"user_a_scope": "users/alice/profiles/default"', repaired)
        self.assertIn('"user_b_scope": "users/bob/profiles/default"', repaired)
        self.assertNotIn(".relative_to(", repaired)
        self.assertEqual(repair_storage_smoke(repaired), repaired)

    def test_candidate_contract_matches_full_implementation(self) -> None:
        source = (
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\n"
        )
        repaired = repair_candidate(source)
        self.assertIn("unified-master-orchestrator-v3-full", repaired)
        self.assertIn("'6^6'", repaired)
        self.assertIn("-ne 46656", repaired)
        self.assertEqual(repair_candidate(repaired), repaired)


if __name__ == "__main__":
    unittest.main()
