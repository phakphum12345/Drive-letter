import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "research-os-final-gate.yml"
)


class FinalGateFlutterScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        start = cls.source.index("  flutter-gate:\\n")
        end = cls.source.index("  source_integrity:\\n", start)
        cls.job = cls.source[start:end]

    def test_scope_aware_job_is_not_skipped_at_job_level(self):
        header = self.job.split("    steps:\\n", 1)[0]
        self.assertIn("name: Flutter Windows build analyze test", header)
        self.assertIn("needs: detect-flutter-scope", header)
        self.assertNotIn("    if:", header)

    def test_scope_detector_covers_authoritative_legacy_flutter_inputs(self):
        self.assertIn("v3/flutter_app/", self.source)
        self.assertIn("packages/research_os_contracts/", self.source)
        self.assertIn(".github/actions/flutter-setup/", self.source)
        self.assertIn(r"research-os-final-gate\\.yml", self.source)

    def test_irrelevant_scope_has_explicit_report_step(self):
        expected = (
            "      - name: Report legacy Flutter scope decision\\n"
            "        if: needs.detect-flutter-scope.outputs.run_flutter != 'true'\\n"
            "        shell: pwsh\\n"
        )
        self.assertIn(expected, self.job)
        self.assertIn("LEGACY_FLUTTER_WINDOWS=NOT_REQUIRED_FOR_THIS_CHANGE", self.job)

    def test_flutter_validation_steps_only_run_for_relevant_changes(self):
        steps = [
            "Set up Flutter",
            "Validate V3 Flutter source contract",
            "Flutter dependencies",
            "Flutter analyze",
            "Flutter tests",
            "Bootstrap isolated Windows build workspace",
            "Flutter Windows build smoke",
        ]
        for name in steps:
            with self.subTest(step=name):
                marker = f"      - name: {name}\\n"
                self.assertIn(marker, self.job)
                section = self.job.split(marker, 1)[1].split("\\n      - name:", 1)[0]
                self.assertTrue(
                    section.startswith("        if: needs.detect-flutter-scope.outputs.run_flutter == 'true'\\n"),
                    f"{name} must be conditional on the scope decision",
                )


if __name__ == "__main__":
    unittest.main()
