from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_session import issue_session
from server import ResearchOSHandler


class PluginCenterHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "RESEARCH_OS_DATA_DIR": self.temp.name,
            "RESEARCH_OS_SESSION_SECRET": "test-only-plugin-center-owner-secret",
        })
        self.env.start()
        self.owner = issue_session({"sub": "plugin-owner", "email": "owner@example.test", "role": "owner"})
        self.user = issue_session({"sub": "plugin-user", "email": "user@example.test", "role": "user"})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ResearchOSHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.env.stop()
        self.temp.cleanup()

    def request(self, path: str, *, method: str = "GET", body=None, token: str | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Research-OS-Session"] = token
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_google_workspace_status_is_owner_only(self) -> None:
        status, payload = self.request("/v1/google-workspace/dashboard")
        self.assertEqual(401, status)
        self.assertEqual("authentication_required", payload["error"])

        status, payload = self.request("/v1/google-workspace/dashboard", token=self.user)
        self.assertEqual(403, status)
        self.assertEqual("owner_required", payload["error"])

        status, dashboard = self.request("/v1/google-workspace/dashboard", token=self.owner)
        self.assertEqual(200, status)
        self.assertEqual("backend_only", dashboard["token_storage"])

    def test_workspace_service_mutations_require_owner_and_persist(self) -> None:
        payload = {"enabled_services": ["drive", "sheets"]}
        status, denied = self.request(
            "/v1/google-workspace/services", method="POST", body=payload, token=self.user
        )
        self.assertEqual(403, status)
        settings = Path(self.temp.name) / "google_workspace" / "settings.json"
        self.assertFalse(settings.exists())

        status, saved = self.request(
            "/v1/google-workspace/services", method="POST", body=payload, token=self.owner
        )
        self.assertEqual(200, status)
        self.assertTrue(settings.is_file())
        self.assertEqual({"drive", "sheets"}, {
            item["service"] for item in saved["services"] if item["enabled"]
        })

    def test_google_oauth_lifecycle_mutations_require_owner(self) -> None:
        for path in (
            "/v1/google-workspace/oauth/start",
            "/v1/google-workspace/oauth/disconnect",
        ):
            with self.subTest(path=path):
                status, payload = self.request(path, method="POST", body={}, token=self.user)
                self.assertEqual(403, status)
                self.assertEqual("owner_required", payload["error"])


if __name__ == "__main__":
    unittest.main()
