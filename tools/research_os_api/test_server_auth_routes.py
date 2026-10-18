from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oauth_handoff
import qr_pairing
import server_auth_routes


class ServerAuthRouteTests(unittest.TestCase):
    def test_callback_requires_code_and_state(self):
        with self.assertRaises(Exception):
            server_auth_routes.auth_callback("github", "")

    def test_status_without_cookie_is_disconnected(self):
        result = server_auth_routes.auth_status(None)
        self.assertFalse(result["connected"])
        self.assertIsNone(result["account"])

    def test_non_google_qr_callback_completes_pairing_and_one_time_handoff(self):
        previous_data_dir = os.environ.get("RESEARCH_OS_DATA_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["RESEARCH_OS_DATA_DIR"] = temp_dir
            try:
                for provider in ("github", "microsoft"):
                    with self.subTest(provider=provider):
                        pairing = qr_pairing.create_pairing()
                        oauth_state = f"state-{provider}"
                        qr_pairing.bind_oauth_state(
                            pairing["pairing_id"],
                            pairing["pairing_secret"],
                            oauth_state,
                            provider,
                        )
                        session = f"session-{provider}"
                        principal = {
                            "user_id": f"{provider}:123",
                            "email": f"{provider}@example.com",
                            "role": "USER",
                        }

                        def store_handoff(_root, session_value, redirect_uri, *, code=None):
                            return oauth_handoff.create_handoff(
                                Path(temp_dir), session_value, redirect_uri, code=code
                            )

                        with (
                            patch.object(
                                server_auth_routes,
                                "complete_runtime_login",
                                return_value={
                                    "provider": provider,
                                    "principal": principal,
                                    "session": session,
                                    "set_cookie": "research_os_session=test; HttpOnly",
                                },
                            ),
                            patch.object(server_auth_routes, "create_handoff", side_effect=store_handoff),
                            patch.object(
                                server_auth_routes,
                                "consume_handoff",
                                side_effect=lambda _root, code: oauth_handoff.consume_handoff(
                                    Path(temp_dir), code
                                ),
                            ),
                            patch.object(server_auth_routes, "verify_session", return_value=principal),
                        ):
                            result, cookie = server_auth_routes.auth_callback(
                                provider, f"code=authorization-code&state={oauth_state}"
                            )
                            self.assertIn("research_os_session", cookie)
                            self.assertEqual(result["pairing"]["provider"], provider)
                            self.assertTrue(result["pairing"]["paired"])
                            status = qr_pairing.get_status(
                                pairing["pairing_id"], pairing["pairing_secret"]
                            )
                            self.assertTrue(status["connected"])
                            self.assertEqual(status["account"]["user_id"], principal["user_id"])

                            handoff = server_auth_routes.auth_provider_handoff(
                                pairing["pairing_secret"]
                            )
                            self.assertTrue(handoff["connected"])
                            self.assertEqual(handoff["session"], session)
                            self.assertEqual(handoff["account"]["user_id"], principal["user_id"])
                            with self.assertRaisesRegex(
                                server_auth_routes.MultiLoginRuntimeError, "missing, expired, or already consumed"
                            ):
                                server_auth_routes.auth_provider_handoff(pairing["pairing_secret"])
            finally:
                if previous_data_dir is None:
                    os.environ.pop("RESEARCH_OS_DATA_DIR", None)
                else:
                    os.environ["RESEARCH_OS_DATA_DIR"] = previous_data_dir


if __name__ == "__main__":
    unittest.main()
