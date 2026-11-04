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
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_session import issue_session
from server import ResearchOSHandler


class ControlCenterAuditHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "RESEARCH_OS_DATA_DIR": self.temp.name,
            "RESEARCH_OS_SESSION_SECRET": "test-only-control-center-audit-secret",
        })
        self.env.start()
        self.owner_session = issue_session({
            "sub": "audit-owner",
            "email": "owner@example.test",
            "role": "owner",
        })
        self.other_session = issue_session({
            "sub": "audit-other",
            "email": "other@example.test",
            "role": "user",
        })
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
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def snapshot(self):
        return {
            "audit_id": "audit-http-1",
            "observed_at": "2026-11-04T12:00:00Z",
            "status": "DEFERRED",
            "source": "Native Control Center",
            "checks": [
                {"check": "Runtime", "state": "PASS", "detail": "Observed"},
                {"check": "Release authority", "state": "DEFERRED", "detail": "Separate gate"},
            ],
        }

    def test_audit_api_requires_verified_session(self) -> None:
        status, payload = self.request("/v1/control-center/audits")
        self.assertEqual(401, status)
        self.assertEqual("authentication_required", payload["error"])

    def test_audit_history_is_persisted_and_scoped_to_session_identity(self) -> None:
        status, saved = self.request(
            "/v1/control-center/audits",
            method="POST",
            body=self.snapshot(),
            token=self.owner_session,
        )
        self.assertEqual(201, status)
        self.assertTrue(saved["persisted"])
        self.assertEqual("audit-http-1", saved["audit"]["audit_id"])

        status, listed = self.request(
            "/v1/control-center/audits?limit=20", token=self.owner_session
        )
        self.assertEqual(200, status)
        self.assertEqual(1, listed["count"])
        self.assertEqual("observation_only", listed["authority"])

        status, other = self.request(
            "/v1/control-center/audits", token=self.other_session
        )
        self.assertEqual(200, status)
        self.assertEqual(0, other["count"])

    def test_invalid_audit_payload_is_rejected(self) -> None:
        status, payload = self.request(
            "/v1/control-center/audits",
            method="POST",
            body={**self.snapshot(), "status": "AUTHORIZED"},
            token=self.owner_session,
        )
        self.assertEqual(400, status)
        self.assertEqual("bad_request", payload["error"])


if __name__ == "__main__":
    unittest.main()
