from __future__ import annotations
import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import email_otp

class EmailOTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"RESEARCH_OS_DATA_DIR": self.temp.name, "RESEARCH_OS_EMAIL_OTP_SECRET": "unit-test-otp-secret"}, clear=False)
        self.env.start()
        self.sent = []
        self.sender = patch.object(email_otp, "_send_email", side_effect=lambda email, code: self.sent.append((email, code)))
        self.sender.start()
    def tearDown(self):
        self.sender.stop(); self.env.stop(); self.temp.cleanup()
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
        with patch.dict(os.environ, {"RESEARCH_OS_EMAIL_OTP_SECRET": "", "RESEARCH_OS_SESSION_SECRET": ""}):
            with self.assertRaises(email_otp.EmailOTPError) as raised:
                email_otp.start_email_otp("user@example.com", now=1000)
            self.assertEqual(raised.exception.status, 503)

if __name__ == "__main__": unittest.main()
