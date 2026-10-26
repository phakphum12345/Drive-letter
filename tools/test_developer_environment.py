import unittest
from unittest.mock import patch

from tools import developer_environment as inventory


class DeveloperEnvironmentTests(unittest.TestCase):
    def test_reports_available_and_missing_tools_without_launching_them(self):
        def fake_which(name):
            return f"/fake/bin/{name}" if name in {"git", "python"} else None

        result = inventory.inspect_environment(which=fake_which)

        self.assertEqual(result["mode"], "READ_ONLY")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["summary"]["checked"], len(inventory.TOOL_NAMES))
        self.assertEqual(result["summary"]["available"], 1)
        git = next(item for item in result["tools"] if item["name"] == "git")
        self.assertEqual(git["status"], "PASS")
        self.assertEqual(git["path"], "/fake/bin/git")
        wsl = next(item for item in result["tools"] if item["name"] == "wsl")
        self.assertEqual(wsl["status"], "SKIPPED")
        self.assertIsNone(wsl["path"])

    def test_all_missing_is_skipped_not_a_false_pass(self):
        result = inventory.inspect_environment(which=lambda _name: None)
        self.assertEqual(result["summary"]["available"], 0)
        self.assertEqual(result["summary"]["status"], "SKIPPED")
        self.assertTrue(all(item["status"] == "SKIPPED" for item in result["tools"]))

    def test_inventory_does_not_call_subprocess(self):
        with patch("subprocess.run", side_effect=AssertionError("must not execute")):
            result = inventory.inspect_environment(which=lambda _name: None)
        self.assertEqual(result["mode"], "READ_ONLY")


if __name__ == "__main__":
    unittest.main()
