from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import email_otp

# Keep a reference to the real transport before the OTP state tests stub it.
_SEND_EMAIL = email_otp._send_email


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class EmailOTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "RESEARCH_OS_DATA_DIR": self.temp.name,
                "RESEARCH_OS_EMAIL_OTP_SECRET": "unit-test-otp-secret",
            },
            clear=False,
        )
        self.env.start()
        self.sent = []
        self.sender = patch.object(
            email_otp,
            "_send_email",
            side_effect=lambda email, code: self.sent.append((email, code)),
        )
        self.sender.start()

    def tearDown(self):
        self.sender.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_code_hash_single_use_and_normalized_email(self):
        email_otp.start_email_otp("User@example.com", now=1000)
        target, code = self.sent[0]
        raw = Path(self.temp.name, "email_otp_challenges.json").read_text()
        self.assertNotIn(code, raw)
        self.assertEqual(email_otp.verify_email_otp(target, code, now=1001), "user@example.com")
        with self.assertRaises(email_otp.EmailOTPError):
            email_otp.verify_email_otp(target, code, now=1002)

    def test_expiry_and_wrong_code_attempt_limit(self):
        email_otp.start_email_otp("a@example.com", now=1000)
        with self.assertRaisesRegex(email_otp.EmailOTPError, "expired"):
            email_otp.verify_email_otp("a@example.com", self.sent[0][1], now=1300)
        email_otp.start_email_otp("b@example.com", now=2000)
        for _ in range(email_otp.OTP_MAX_ATTEMPTS):
            with self.assertRaises(email_otp.EmailOTPError):
                email_otp.verify_email_otp("b@example.com", "000000", now=2001)

    def test_resend_rate_limit(self):
        email_otp.start_email_otp("a@example.com", now=1000)
        with self.assertRaisesRegex(email_otp.EmailOTPError, "wait"):
            email_otp.start_email_otp("a@example.com", now=1010)

    def test_invalid_email_rejected(self):
        with self.assertRaises(email_otp.EmailOTPError):
            email_otp.start_email_otp("not-an-email", now=1000)

    def test_otp_requires_a_server_side_secret(self):
        with patch.dict(
            os.environ,
            {"RESEARCH_OS_EMAIL_OTP_SECRET": "", "RESEARCH_OS_SESSION_SECRET": ""},
        ):
            with self.assertRaises(email_otp.EmailOTPError) as raised:
                email_otp.start_email_otp("user@example.com", now=1000)
            self.assertEqual(raised.exception.status, 503)

    def test_resend_https_delivery_uses_bearer_key_and_never_smtp(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_OS_EMAIL_API_KEY": "re_test_secret",
                "RESEARCH_OS_EMAIL_FROM": "Research OS <auth@example.com>",
                "RESEARCH_OS_EMAIL_PROVIDER": "resend",
            },
            clear=False,
        ):
            with patch.object(
                email_otp.urllib.request,
                "urlopen",
                return_value=_FakeResponse(),
            ) as urlopen:
                _SEND_EMAIL("user@example.com", "123456")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer re_test_secret")
        self.assertEqual(request.get_header("User-agent"), "ResearchOS/1.0")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["from"], "Research OS <auth@example.com>")
        self.assertEqual(payload["to"], ["user@example.com"])
        self.assertIn("123456", payload["text"])

    def test_email_api_requires_key_and_sender(self):
        with patch.dict(
            os.environ,
            {"RESEARCH_OS_EMAIL_API_KEY": "", "RESEARCH_OS_EMAIL_FROM": ""},
            clear=False,
        ):
            with self.assertRaises(email_otp.EmailOTPError) as raised:
                _SEND_EMAIL("user@example.com", "123456")
        self.assertEqual(raised.exception.status, 503)
        self.assertIn("RESEARCH_OS_EMAIL_API_KEY", str(raised.exception))

    def test_email_api_http_failure_does_not_leak_provider_response(self):
        failure = urllib.error.HTTPError(
            "https://api.resend.com/emails",
            401,
            "unauthorized",
            {},
            None,
        )
        with patch.dict(
            os.environ,
            {
                "RESEARCH_OS_EMAIL_API_KEY": "re_test_secret",
                "RESEARCH_OS_EMAIL_FROM": "auth@example.com",
            },
            clear=False,
        ):
            with patch.object(email_otp.urllib.request, "urlopen", side_effect=failure):
                with self.assertRaises(email_otp.EmailOTPError) as raised:
                    _SEND_EMAIL("user@example.com", "123456")
        self.assertEqual(raised.exception.status, 503)
        self.assertNotIn("re_test_secret", str(raised.exception))
        self.assertNotIn("unauthorized", str(raised.exception))

    def test_email_api_network_failure_is_reported_without_secret(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_OS_EMAIL_API_KEY": "re_test_secret",
                "RESEARCH_OS_EMAIL_FROM": "auth@example.com",
            },
            clear=False,
        ):
            with patch.object(
                email_otp.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("network unreachable"),
            ):
                with self.assertRaises(email_otp.EmailOTPError) as raised:
                    _SEND_EMAIL("user@example.com", "123456")
        self.assertEqual(raised.exception.status, 503)
        self.assertNotIn("re_test_secret", str(raised.exception))

    def test_unsupported_email_provider_fails_closed(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_OS_EMAIL_API_KEY": "re_test_secret",
                "RESEARCH_OS_EMAIL_FROM": "auth@example.com",
                "RESEARCH_OS_EMAIL_PROVIDER": "smtp",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(email_otp.EmailOTPError, "Unsupported Email API provider"):
                _SEND_EMAIL("user@example.com", "123456")


if __name__ == "__main__":
    unittest.main()
