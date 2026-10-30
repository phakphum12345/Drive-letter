from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class OwnerApiSpineStartupContractTests(unittest.TestCase):
    def test_desktop_startup_e2e_keeps_dependencies_alive_until_app_proof(self):
        workflow = (ROOT / ".github/workflows/owner-special-friend.yml").read_text(encoding="utf-8")
        start = workflow.index("Start Friend service + API Spine and prove Owner Desktop startup")
        end = workflow.index("Upload validated Owner desktop", start)
        step = workflow[start:end]

        self.assertIn("Start-Process python", step)
        self.assertIn("RESEARCH_OS_FRIEND_URL", step)
        self.assertIn("RESEARCH_OS_API_BASE_URL", step)
        self.assertIn("Start-Process $exe.FullName", step)
        self.assertIn("/owner/status", step)
        self.assertIn("/owner/provider", step)
        self.assertIn("OWNER_DESKTOP_STARTUP_E2E=PASS", step)
        self.assertIn("finally", step)
        self.assertIn("Stop-Process -Id $gateway.Id", step)
        self.assertIn("Stop-Process -Id $service.Id", step)

    def test_installed_desktop_is_probed_through_the_canonical_api_spine(self):
        validator = (ROOT / "owner_special/scripts/validate-owner-installer.ps1").read_text(encoding="utf-8")

        self.assertIn("tools\\research_os_api\\render_server.py", validator)
        self.assertIn("$env:RESEARCH_OS_API_BASE_URL = $apiBase", validator)
        self.assertIn("$env:RESEARCH_OS_FRIEND_URL = 'http://127.0.0.1:8790'", validator)
        self.assertIn('"$apiBase/owner/status"', validator)
        self.assertIn('"$apiBase/owner/provider"', validator)
        self.assertIn("through the API Spine", validator)
        self.assertIn("Stop-Process -Id $apiProcess.Id", validator)
        self.assertIn("Remove-Item \"Env:$name\"", validator)


if __name__ == "__main__":
    unittest.main()
