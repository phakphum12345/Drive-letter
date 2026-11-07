from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import email_otp
import server


class _QuietResearchOSHandler(server.ResearchOSHandler):
    def log_message(self, _format, *_args):
        pass


class EmailOTPMinimalEmulatorTests(unittest.TestCase):
    """Exercise the real HTTP auth routes with an in-memory email delivery sink."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "RESEARCH_OS_DATA_DIR": self.temp.name,
                "RESEARCH_OS_EMAIL_OTP_SECRET": "minimal-emulator-otp-secret",
                "RESEARCH_OS_SESSION_SECRET": "minimal-emulator-session-secret",
                "RESEARCH_OS_OWNER_EMAILS": "owner@example.com",
            },
            clear=False,
        )
        self.env.start()
        self.delivered = []
        self.sender = patch.object(
            email_otp,
            "_send_email",
            side_effect=lambda email, code: self.delivered.append((email, code)),
        )
        self.sender.start()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _QuietResearchOSHandler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.sender.stop()
        self.env.stop()
        self.temp.cleanup()

    def _post(self, path: str, payload: dict):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except Exception as exc:
            if hasattr(exc, "code"):
                return exc.code, json.loads(exc.read().decode("utf-8")), exc.headers
            raise
        with response:
            return response.status, json.loads(response.read().decode("utf-8")), response.headers

    def test_email_otp_start_verify_and_session_cookie_over_http(self):
        status, started, _headers = self._post(
            "/v1/auth/email-otp/start",
            {"email": "Owner@example.com"},
        )
        self.assertEqual(status, 202)
        self.assertEqual(started["delivery"], "email")
        self.assertEqual(started["expires_in"], 300)
        self.assertEqual(self.delivered[0][0], "owner@example.com")
        code = self.delivered[0][1]

        status, verified, headers = self._post(
            "/v1/auth/email-otp/verify",
            {"email": "owner@example.com", "code": code},
        )
        self.assertEqual(status, 200)
        self.assertTrue(verified["connected"])
        self.assertEqual(verified["provider"], "email_otp")
        self.assertEqual(verified["account"]["email"], "owner@example.com")
        self.assertEqual(verified["account"]["role"], "OWNER")
        self.assertIn("research_os_session=", headers.get("Set-Cookie", ""))

        status, rejected, _headers = self._post(
            "/v1/auth/email-otp/verify",
            {"email": "owner@example.com", "code": code},
        )
        self.assertEqual(status, 401)
        self.assertEqual(rejected["error"], "email_otp_rejected")


if __name__ == "__main__":
    unittest.main()
