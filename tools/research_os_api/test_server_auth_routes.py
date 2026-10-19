from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import multi_login_runtime
import oauth_handoff
import qr_pairing
import server_auth_routes


class ServerAuthRouteTests(unittest.TestCase):
    def test_callback_requires_code_and_state(self):
        with self.assertRaises(server_auth_routes.MultiLoginRuntimeError):
            server_auth_routes.auth_callback("github", "")

    def test_status_without_cookie_is_disconnected(self):
        result = server_auth_routes.auth_status(None)
        self.assertFalse(result["connected"])
        self.assertIsNone(result["account"])

    def test_non_google_qr_callback_completes_real_login_and_one_time_handoff(self):
        previous_data_dir = os.environ.get("RESEARCH_OS_DATA_DIR")
        previous_v3_data_dir = os.environ.get("RESEARCH_OS_V3_DATA_DIR")
        previous_session_secret = os.environ.get("RESEARCH_OS_SESSION_SECRET")
        with tempfile.TemporaryDirectory() as temp_dir:
            v3_data_dir = str(Path(temp_dir) / "v3-data")
            try:
                for provider in ("github", "microsoft"):
                    with self.subTest(provider=provider):
                        provider_env = {
                            "RESEARCH_OS_DATA_DIR": temp_dir,
                            "RESEARCH_OS_V3_DATA_DIR": v3_data_dir,
                            "RESEARCH_OS_SESSION_SECRET": "isolated-non-google-auth-test-secret",
                            f"RESEARCH_OS_{provider.upper()}_CLIENT_ID": f"{provider}-client-id",
                            f"RESEARCH_OS_{provider.upper()}_CLIENT_SECRET": f"{provider}-client-secret",
                        }
                        # Clear the inherited environment so a Google credential cannot
                        # accidentally make this non-Google regression test pass.
                        with patch.dict(os.environ, provider_env, clear=True):
                            pairing = qr_pairing.create_pairing()
                            redirect_uri = f"http://127.0.0.1:8787/v1/auth/{provider}/callback"
                            authorization_url = server_auth_routes.auth_pairing_authorize(
                                provider,
                                pairing["pairing_id"],
                                pairing["pairing_secret"],
                                redirect_uri,
                            )
                            state = parse_qs(urlparse(authorization_url).query)["state"][0]
                            self.assertNotIn("google", urlparse(authorization_url).netloc.lower())
                            self.assertNotIn("RESEARCH_OS_GOOGLE_CLIENT_ID", os.environ)
                            self.assertNotIn("RESEARCH_OS_GOOGLE_CLIENT_SECRET", os.environ)

                            if provider == "github":
                                profile = {
                                    "id": 123,
                                    "login": "test-github-user",
                                    "name": "Test GitHub User",
                                    "email": None,
                                }
                                verified_emails = [
                                    {"email": "github@example.com", "verified": True, "primary": True},
                                ]
                                profile_responses = [profile, verified_emails]
                            else:
                                profile_responses = [
                                    {
                                        "sub": "microsoft-sub-123",
                                        "email": "microsoft@example.com",
                                        "name": "Test Microsoft User",
                                    },
                                ]

                            def fake_token_exchange(url, data):
                                self.assertEqual(
                                    url,
                                    multi_login_runtime.get_provider(provider).token_endpoint,
                                )
                                self.assertEqual(data["client_id"], provider_env[
                                    f"RESEARCH_OS_{provider.upper()}_CLIENT_ID"
                                ])
                                self.assertEqual(data["client_secret"], provider_env[
                                    f"RESEARCH_OS_{provider.upper()}_CLIENT_SECRET"
                                ])
                                self.assertEqual(data["code"], "authorization-code")
                                self.assertEqual(data["redirect_uri"], redirect_uri)
                                return {"access_token": f"{provider}-access-token"}

                            def store_handoff(_root, session_value, redirect_uri, *, code=None):
                                return oauth_handoff.create_handoff(
                                    Path(temp_dir), session_value, redirect_uri, code=code
                                )

                            with (
                                patch.object(
                                    multi_login_runtime,
                                    "_post_form",
                                    side_effect=fake_token_exchange,
                                ),
                                patch.object(
                                    multi_login_runtime,
                                    "_get_json",
                                    side_effect=profile_responses,
                                ),
                                patch.object(
                                    server_auth_routes,
                                    "create_handoff",
                                    side_effect=store_handoff,
                                ),
                                patch.object(
                                    server_auth_routes,
                                    "consume_handoff",
                                    side_effect=lambda _root, code: oauth_handoff.consume_handoff(
                                        Path(temp_dir), code
                                    ),
                                ),
                            ):
                                result, response_cookie = server_auth_routes.auth_callback(
                                    provider, f"code=authorization-code&state={state}"
                                )
                                self.assertIn("research_os_session", response_cookie)
                                self.assertEqual(result["provider"], provider)
                                self.assertEqual(result["principal"]["user_id"], (
                                    "github:123" if provider == "github" else "microsoft:microsoft-sub-123"
                                ))

                                status = qr_pairing.get_status(
                                    pairing["pairing_id"], pairing["pairing_secret"]
                                )
                                self.assertTrue(status["connected"])
                                self.assertEqual(
                                    status["account"]["user_id"],
                                    result["principal"]["user_id"],
                                )

                                # Verify the actual signed session from the returned cookie.
                                auth_status = server_auth_routes.auth_status(response_cookie)
                                self.assertTrue(auth_status["connected"])
                                self.assertEqual(
                                    auth_status["account"]["user_id"],
                                    result["principal"]["user_id"],
                                )
                                self.assertEqual(
                                    auth_status["account"]["email"],
                                    result["principal"]["email"],
                                )

                                handoff = server_auth_routes.auth_provider_handoff(
                                    pairing["pairing_secret"]
                                )
                                self.assertTrue(handoff["connected"])
                                self.assertEqual(handoff["session"], result["session"])
                                self.assertEqual(
                                    handoff["account"]["user_id"],
                                    result["principal"]["user_id"],
                                )
                                with self.assertRaisesRegex(
                                    server_auth_routes.MultiLoginRuntimeError,
                                    "missing, expired, or already consumed",
                                ):
                                    server_auth_routes.auth_provider_handoff(
                                        pairing["pairing_secret"]
                                    )
            finally:
                for key, previous in (
                    ("RESEARCH_OS_DATA_DIR", previous_data_dir),
                    ("RESEARCH_OS_V3_DATA_DIR", previous_v3_data_dir),
                    ("RESEARCH_OS_SESSION_SECRET", previous_session_secret),
                ):
                    if previous is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = previous


if __name__ == "__main__":
    unittest.main()
