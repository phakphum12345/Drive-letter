"""Contract tests for exact-SHA Flutter scope skip evidence."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "research-os-final-gate.yml"
VERIFIER = ROOT / "tools" / "aeos" / "verify_pr_checks.py"


class FinalGateFlutterScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.verifier = VERIFIER.read_text(encoding="utf-8")
        start = cls.workflow.index("  detect-flutter-scope:\n")
        end = cls.workflow.index("  python-gate:\n", start)
        cls.scope_job = cls.workflow[start:end]
        start = cls.workflow.index("  flutter-gate:\n")
        end = cls.workflow.index("  source_integrity:\n", start)
        cls.flutter_job = cls.workflow[start:end]

    def test_scope_detector_covers_authoritative_flutter_inputs(self):
        self.assertIn("tools/aeos/(verify_pr_checks|test_verify_pr_checks)", self.workflow)
        self.assertIn("v3/flutter_app/", self.workflow)
        self.assertIn("packages/research_os_contracts/", self.workflow)
        self.assertIn(".github/actions/flutter-setup/", self.workflow)
        self.assertIn("research-os-final-gate|v3-candidate|v3-clean-core", self.workflow)

    def test_scope_detector_records_skip_as_a_decision_not_a_pass(self):
        self.assertIn("name: Decide whether legacy Flutter Windows validation is relevant", self.scope_job)
        self.assertIn("outputs:", self.scope_job)
        self.assertIn("run_flutter:", self.scope_job)
        self.assertIn("LEGACY_FLUTTER_WINDOWS=SKIP_UNRELATED_CHANGES", self.scope_job)
        self.assertIn("SKIP_LEGACY_FLUTTER:", self.scope_job)
        self.assertNotIn("SCOPE_WAIVER=VERIFIED", self.scope_job)

    def test_flutter_job_is_skipped_only_when_scope_says_not_relevant(self):
        header = self.flutter_job.split("    steps:\n", 1)[0]
        self.assertIn("needs: detect-flutter-scope", header)
        self.assertIn("if: needs.detect-flutter-scope.outputs.run_flutter == 'true'", header)

    def test_verifier_requires_trusted_exact_sha_scope_proof(self):
        self.assertIn("def prove_flutter_scope_skip(", self.verifier)
        self.assertIn('run.get("path") != ".github/workflows/research-os-final-gate.yml"', self.verifier)
        self.assertIn('run.get("head_sha") != expected_head_sha', self.verifier)
        self.assertIn('head.get("sha") != expected_head_sha', self.verifier)
        self.assertIn("all PR files are outside Flutter validation scope", self.verifier)
        self.assertIn("check_run+exact_scope_evidence", self.verifier)

    def test_contract_test_is_wired_into_final_gate(self):
        self.assertIn("python tools/aeos/test_final_gate_flutter_scope.py", self.workflow)


if __name__ == "__main__":
    unittest.main()
