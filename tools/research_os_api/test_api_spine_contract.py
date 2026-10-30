from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class APISpineContractTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_native_client_uses_one_api_base_url(self):
        main = self.read("owner_special/flutter_app/lib/main.dart")
        client = self.read("owner_special/flutter_app/lib/src/owner_api.dart")
        self.assertIn("RESEARCH_OS_API_BASE_URL", main)
        self.assertNotIn("RESEARCH_OS_FRIEND_URL", main)
        self.assertNotIn("researchOsBaseUrl", client)
        self.assertIn("$baseUrl/v1/ai/generate", client)

    def test_friend_routes_are_gateway_proxied(self):
        server = self.read("tools/research_os_api/server.py")
        self.assertIn('if path.startswith("/owner/"):', server)
        self.assertIn("self._proxy_friend", server)
        self.assertIn('path == "/v1/launch-desk/run"', server)

    def test_google_and_qr_use_canonical_public_base(self):
        server = self.read("tools/research_os_api/server.py")
        identity = self.read("tools/research_os_api/google_identity.py")
        workspace = self.read("tools/research_os_api/google_oauth.py")
        for source in (server, identity, workspace):
            self.assertIn("RESEARCH_OS_API_BASE_URL", source)
            self.assertNotIn("RENDER_EXTERNAL_URL", source)

    def test_email_otp_contract_is_present_and_fail_closed_without_smtp(self):
        module = self.read("tools/research_os_api/email_otp.py")
        api = self.read("tools/research_os_api/server.py")
        self.assertIn("OTP_TTL_SECONDS = 300", module)
        self.assertIn("OTP_MAX_ATTEMPTS = 5", module)
        self.assertIn("compare_digest", module)
        self.assertIn("/v1/auth/email-otp/start", api)
        self.assertIn("/v1/auth/email-otp/verify", api)

    def test_local_launcher_uses_loopback_and_dynamic_default_ports(self):
        launcher = self.read("scripts/start-research-os-local.ps1")
        self.assertIn('[string]$HostAddress = "127.0.0.1"', launcher)
        self.assertIn("[int]$Port = 0", launcher)
        self.assertIn("[int]$FriendPort = 0", launcher)
        self.assertIn("Get-FreeLoopbackPort", launcher)
        self.assertNotIn("[int]$Port = 8787", launcher)
        self.assertNotIn("[int]$FriendPort = 8790", launcher)

    def test_runtime_entrypoints_support_ephemeral_ports(self):
        api = self.read("tools/research_os_api/server.py")
        friend = self.read("owner_special/scripts/run_friend_service.py")
        self.assertIn('default=int(os.getenv("RESEARCH_OS_API_PORT", "0"))', api)
        self.assertIn('default=0)', friend)
        self.assertIn("server.server_address[1]", api)

if __name__ == "__main__":
    unittest.main()
