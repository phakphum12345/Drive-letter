import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from google_oauth import GoogleOAuthBroker, GoogleOAuthError


class GoogleOAuthBrokerTest(unittest.TestCase):
    def test_begin_requires_backend_credentials(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GoogleOAuthError):
                GoogleOAuthBroker(tmp).begin()

    def test_begin_builds_google_authorization_url_without_exposing_secret(self):
        env = {
            "RESEARCH_OS_GOOGLE_CLIENT_ID": "client-id.apps.googleusercontent.com",
            "RESEARCH_OS_GOOGLE_CLIENT_SECRET": "super-secret",
            "RESEARCH_OS_API_PORT": "8787",
            "RESEARCH_OS_API_BASE_URL": "https://research.example.test",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            broker = GoogleOAuthBroker(tmp)
            payload = broker.begin()
            url = payload["authorization_url"]
            self.assertIn("accounts.google.com/o/oauth2/v2/auth", url)
            self.assertIn("client-id.apps.googleusercontent.com", url)
            self.assertNotIn("super-secret", url)
            self.assertIn("https%3A%2F%2Fresearch.example.test%2Fv1%2Fgoogle-workspace%2Foauth%2Fcallback", url)
            self.assertTrue((Path(tmp) / "google_workspace" / "oauth_state.json").exists())

    def test_status_and_disconnect_use_backend_token_store(self):
        env = {
            "RESEARCH_OS_GOOGLE_CLIENT_ID": "client-id",
            "RESEARCH_OS_GOOGLE_CLIENT_SECRET": "client-secret",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            broker = GoogleOAuthBroker(tmp)
            self.assertFalse(broker.status()["connected"])
            broker.token_path.write_text(json.dumps({"refresh_token": "refresh"}), encoding="utf-8")
            self.assertTrue(broker.status()["connected"])
            result = broker.disconnect()
            self.assertTrue(result["disconnected"])
            self.assertFalse(broker.token_path.exists())


    def test_begin_prefers_matched_web_client_credentials_from_secret_file(self):
        env = {
            "RESEARCH_OS_GOOGLE_CLIENT_ID": "stale-env-client-id",
            "RESEARCH_OS_GOOGLE_CLIENT_SECRET": "stale-env-secret",
            "RESEARCH_OS_GOOGLE_CLIENT_JSON_FILE": "",
            "RESEARCH_OS_API_BASE_URL": "https://research.example.test",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            client_file = Path(tmp) / "client_secret.json"
            client_file.write_text(
                json.dumps({
                    "web": {
                        "client_id": "secret-file-client.apps.googleusercontent.com",
                        "client_secret": "secret-file-secret",
                        "redirect_uris": [
                            "https://research.example.test/v1/google-workspace/oauth/callback"
                        ],
                    }
                }),
                encoding="utf-8",
            )
            os.environ["RESEARCH_OS_GOOGLE_CLIENT_JSON_FILE"] = str(client_file)
            broker = GoogleOAuthBroker(tmp)
            payload = broker.begin()
            self.assertIn("secret-file-client.apps.googleusercontent.com", payload["authorization_url"])
            self.assertNotIn("stale-env-client-id", payload["authorization_url"])
            self.assertNotIn("secret-file-secret", payload["authorization_url"])
            self.assertEqual(broker.client_secret, "secret-file-secret")

    def test_begin_rejects_secret_file_with_unregistered_redirect_uri(self):
        env = {
            "RESEARCH_OS_GOOGLE_CLIENT_ID": "stale-env-client-id",
            "RESEARCH_OS_GOOGLE_CLIENT_SECRET": "stale-env-secret",
            "RESEARCH_OS_API_BASE_URL": "https://research.example.test",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            client_file = Path(tmp) / "client_secret.json"
            client_file.write_text(
                json.dumps({
                    "web": {
                        "client_id": "file-client-id",
                        "client_secret": "file-client-secret",
                        "redirect_uris": ["https://wrong.example.test/callback"],
                    }
                }),
                encoding="utf-8",
            )
            os.environ["RESEARCH_OS_GOOGLE_CLIENT_JSON_FILE"] = str(client_file)
            with self.assertRaisesRegex(GoogleOAuthError, "not listed"):
                GoogleOAuthBroker(tmp).begin()

    def test_invalid_secret_file_does_not_fall_back_to_environment_credentials(self):
        env = {
            "RESEARCH_OS_GOOGLE_CLIENT_ID": "env-client-id",
            "RESEARCH_OS_GOOGLE_CLIENT_SECRET": "env-client-secret",
            "RESEARCH_OS_GOOGLE_CLIENT_JSON_FILE": "/missing/client_secret.json",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            broker = GoogleOAuthBroker(tmp)
            self.assertFalse(broker.config.oauth_configured)
            with self.assertRaises(GoogleOAuthError):
                broker.begin()



if __name__ == "__main__":
    unittest.main()
