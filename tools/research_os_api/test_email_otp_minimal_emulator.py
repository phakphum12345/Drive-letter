from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server


class _QuietResearchOSHandler(server.ResearchOSHandler):
    def log_message(self, _format, *_args):
        pass


class DisabledEmailOTPRouteTests(unittest.TestCase):
    """Ensure retired Email OTP endpoints cannot send mail or create sessions."""

    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _QuietResearchOSHandler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

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
                return exc.code, json.loads(exc.read().decode("utf-8"))
            raise
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_email_otp_start_route_is_not_registered(self):
        status, payload = self._post(
            "/v1/auth/email-otp/start",
            {"email": "owner@example.com"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not_found")

    def test_email_otp_verify_route_is_not_registered(self):
        status, payload = self._post(
            "/v1/auth/email-otp/verify",
            {"email": "owner@example.com", "code": "123456"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
