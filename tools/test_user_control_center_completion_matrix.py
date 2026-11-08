import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "current" / "USER_CONTROL_CENTER_COMPLETION_MATRIX.json"


class UserControlCenterCompletionMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    def test_baseline_is_not_misreported_as_complete(self):
        self.assertEqual("BASELINE_AUDIT", self.matrix["status"])

    def test_required_surfaces_are_tracked(self):
        ids = {item["id"] for item in self.matrix["capabilities"]}
        self.assertTrue({
            "web.control_center.dashboard",
            "web.research_chat",
            "web.projects_files",
            "web.history_activity",
            "web.settings_account",
            "web.admin_console",
            "flutter.projects",
            "flutter.workflows",
            "flutter.chat",
            "flutter.native_control",
            "flutter.owner_experience",
            "plugin_center.marketplace",
            "api_management",
            "control_center_ci",
            "web.agent_center",
            "web.platform_directory",
            "recon.back_box.config_snapshot",
            "recon.back_box.public_github_targets",
            "recon.back_box.native_ui",
            "recon.branch_reconciliation",
        }.issubset(ids))

    def test_recon_capabilities_are_tracked_without_claiming_local_only_actions_are_remote(self):
        by_id = {item["id"]: item for item in self.matrix["capabilities"]}
        self.assertEqual("CANONICAL_WIRED", by_id["recon.back_box.config_snapshot"]["status"])
        self.assertEqual("CANONICAL_WIRED", by_id["recon.back_box.public_github_targets"]["status"])
        self.assertEqual("PARTIAL", by_id["recon.back_box.native_ui"]["status"])
        self.assertIn("local-only", by_id["recon.back_box.native_ui"]["detail"])

    def test_plugin_runtime_registry_is_not_claimed_as_marketplace(self):
        plugin = next(item for item in self.matrix["capabilities"] if item["id"] == "plugin_center.marketplace")
        self.assertEqual("MISSING_EXECUTOR", plugin["status"])
        self.assertIn("general user-facing plugin marketplace", plugin["detail"])
        self.assertIn("first-party", plugin["detail"])
        self.assertIn("still missing", plugin["detail"])

    def test_each_capability_has_evidence_and_acceptance_criteria(self):
        for item in self.matrix["capabilities"]:
            with self.subTest(capability=item["id"]):
                self.assertTrue(item["evidence"])
                self.assertTrue(item["acceptance"])
                self.assertIn(item["status"], {
                    "CANONICAL_WIRED", "IMPLEMENTED_NOT_WIRED",
                    "WIRED_NOT_EXECUTABLE", "MISSING_EXECUTOR",
                    "PARTIAL", "ORPHAN", "DUPLICATE", "UNKNOWN",
                })


if __name__ == "__main__":
    unittest.main()
