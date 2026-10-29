from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "apps" / "research_os_web" / "app.js"
EXPECTED_API = "https://phakphumwir.tail4b06c9.ts.net"


class ResearchOSWebEndpointContractTests(unittest.TestCase):
    def test_pages_default_targets_tailscale_api_not_hosted_render(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_API, source)
        self.assertNotIn("onrender.com", source.lower())

    def test_api_endpoint_remains_configurable_and_cookie_credentials_enabled(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("window.RESEARCH_OS_API_BASE_URL", source)
        self.assertIn("credentials:'include'", source)

    def test_health_and_auth_use_the_shared_api_request_adapter(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("request('/health')", source)
        self.assertIn("request('/v1/auth/google/status')", source)


if __name__ == "__main__":
    unittest.main()
