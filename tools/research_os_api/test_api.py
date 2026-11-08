import json
from contextlib import contextmanager
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

import server
from auth_session import issue_session, verify_session


class ResearchOSAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.ResearchOSHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)


    @contextmanager
    def identity_sessions(self):
        """Issue signed test sessions against an isolated revocation store."""
        with tempfile.TemporaryDirectory() as data_dir:
            with patch.dict(
                os.environ,
                {
                    "RESEARCH_OS_SESSION_SECRET": "friend-identity-tests-only-secret",
                    "RESEARCH_OS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                def issue(user_id: str, role: str = "owner") -> str:
                    email = user_id.replace(":", ".") + "@example.test"
                    return issue_session({"user_id": user_id, "email": email, "role": role})

                yield issue

    def request(self, method: str, path: str, payload=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])
        self.assertTrue(payload["memory"])

    @patch("server._friend_provider_health", side_effect=RuntimeError("provider offline"))
    def test_health_fails_closed_when_installed_service_requires_friend(self, _friend_health):
        with patch.dict(os.environ, {"RESEARCH_OS_REQUIRE_FRIEND_HEALTH": "true"}, clear=False):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("GET", "/health")
        self.assertEqual(503, raised.exception.code)
        payload = json.loads(raised.exception.read().decode("utf-8"))
        self.assertEqual("degraded", payload["status"])
        self.assertEqual("provider offline", payload["detail"])

    def test_friend_provider_health_reports_safe_http_error_context(self):
        import io
        error_body = json.dumps({
            "connected": False,
            "provider": "owner-mock",
            "error": "provider_health_not_supported",
        }).encode("utf-8")
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8790/owner/provider/health",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(error_body),
        )
        with patch("server.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(
                RuntimeError,
                r"HTTP 503: provider=owner-mock; error=provider_health_not_supported",
            ):
                server._friend_provider_health()

    def test_friend_provider_health_normalizes_explicit_mock_provider(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "connected": True,
            "provider": "owner-mock",
        }).encode("utf-8")
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "mock"}, clear=False):
            with patch("server.urllib.request.urlopen", return_value=response):
                payload = server._friend_provider_health()
        self.assertEqual("owner-mock", payload["provider"])

    @patch(
        "server._friend_provider_health",
        return_value={"connected": True, "provider": "owner-mock"},
    )
    def test_health_passes_when_required_ci_mock_provider_is_connected(self, _friend_health):
        with patch.dict(
            os.environ,
            {"RESEARCH_OS_REQUIRE_FRIEND_HEALTH": "true", "RESEARCH_OS_PROVIDER": "mock"},
            clear=False,
        ):
            status, payload = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])
        self.assertTrue(payload["ui"])

    @patch("server._friend_provider_health", return_value={"connected": True, "provider": "ollama-local"})
    def test_health_passes_when_required_local_provider_is_connected(self, _friend_health):
        with patch.dict(
            os.environ,
            {"RESEARCH_OS_REQUIRE_FRIEND_HEALTH": "true", "RESEARCH_OS_PROVIDER": "local"},
            clear=False,
        ):
            status, payload = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])

    @patch("server._friend_chat")
    def test_mock_provider_generation(self, friend_chat):
        friend_chat.return_value = {"provider": "mock", "text": "วิเคราะห์แนวคิดนี้"}
        with self.identity_sessions() as issue:
            token = issue("owner")
            with patch.dict(
                os.environ,
                {"RESEARCH_OS_AI_ROUTE": "friend"},
                clear=False,
            ):
                status, payload = self.request(
                    "POST",
                    "/v1/ai/generate",
                    {"provider": "mock", "prompt": "วิเคราะห์แนวคิดนี้"},
                    headers={"X-Research-OS-Session": token},
                )
        self.assertEqual(200, status)
        self.assertEqual("mock", payload["provider"])
        self.assertIn("วิเคราะห์", payload["text"])

    @patch("server._friend_chat")
    def test_generate_routes_through_friend_by_default(self, friend_chat):
        friend_chat.return_value = {
            "provider": "owner-mock",
            "text": "friend-ok",
            "decision": {
                "scale": "10^10",
                "capacity": 10_000_000_000,
            },
            "factory": {
                "available": True,
                "scale": "10^10",
                "capacity": 10_000_000_000,
            },
            "helpers": {
                "bounded": True,
                "active_workers": 128,
                "logical_capacity": 10_000_000_000,
            },
            "metadata": {
                "capabilities": ["v3-unified-master"],
            },
        }

        with self.identity_sessions() as issue:
            token = issue("owner")
            with patch.dict(
                os.environ,
                {"RESEARCH_OS_AI_ROUTE": "friend"},
                clear=False,
            ):
                status, payload = self.request(
                    "POST",
                    "/v1/ai/generate",
                    {
                        "prompt": "mega project",
                        "session_id": "untrusted-client-session",
                        "complexity": 9,
                        "risk": 7,
                        "parallelism": 128,
                        "helper_budget": 1_000_000,
                    },
                    headers={
                        "X-Research-OS-Session": token,
                        "X-Research-OS-Owner": "attacker-owner",
                        "X-Research-OS-Profile": "attacker-profile",
                    },
                )

        self.assertEqual(200, status)
        self.assertEqual("friend", payload["route"])
        self.assertEqual("friend-ok", payload["text"])
        self.assertEqual("10^10", payload["decision"]["scale"])
        self.assertEqual("10^10", payload["factory"]["scale"])
        self.assertTrue(payload["helpers"]["bounded"])


    def test_friend_generation_requires_verified_owner_session(self):
        with patch.dict(os.environ, {"RESEARCH_OS_AI_ROUTE": "friend"}, clear=False):
            with patch("server._friend_chat") as friend_chat:
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    self.request("POST", "/v1/ai/generate", {"prompt": "private"})
        self.assertEqual(401, raised.exception.code)
        friend_chat.assert_not_called()

    def test_friend_generation_rejects_non_owner_session(self):
        with self.identity_sessions() as issue:
            token = issue("member-1", role="user")
            with patch.dict(os.environ, {"RESEARCH_OS_AI_ROUTE": "friend"}, clear=False):
                with patch("server._friend_chat") as friend_chat:
                    with self.assertRaises(urllib.error.HTTPError) as raised:
                        self.request(
                            "POST",
                            "/v1/ai/generate",
                            {"prompt": "private"},
                            headers={"X-Research-OS-Session": token},
                        )
        self.assertEqual(403, raised.exception.code)
        friend_chat.assert_not_called()

    def test_friend_scope_uses_verified_user_and_session_not_client_overrides(self):
        with self.identity_sessions() as issue:
            alice_token = issue("google:alice")
            bob_token = issue("google:bob")
            alice_session_id = verify_session(alice_token)["session_id"]
            bob_session_id = verify_session(bob_token)["session_id"]
            with patch.dict(os.environ, {"RESEARCH_OS_AI_ROUTE": "friend"}, clear=False):
                with patch("server._friend_chat", return_value={"provider": "mock", "text": "ok"}) as friend_chat:
                    alice_headers = {
                        "X-Research-OS-Session": alice_token,
                        "X-Research-OS-Owner": "spoofed-owner",
                        "X-Research-OS-Profile": "spoofed-profile",
                    }
                    _, first = self.request("POST", "/v1/ai/generate", {"prompt": "one", "session_id": "spoofed-session"}, headers=alice_headers)
                    _, second = self.request("POST", "/v1/ai/generate", {"prompt": "two", "session_id": "another-spoof"}, headers=alice_headers)
                    _, third = self.request("POST", "/v1/ai/generate", {"prompt": "three"}, headers={"X-Research-OS-Session": bob_token})

        identities = [call.kwargs["identity"] for call in friend_chat.call_args_list]
        self.assertEqual(3, len(identities))
        self.assertEqual("google:alice", identities[0].user_id)
        self.assertEqual(identities[0].profile_id, identities[1].profile_id)
        self.assertEqual(identities[0].session_id, identities[1].session_id)
        self.assertEqual(alice_session_id, identities[0].session_id)
        self.assertEqual(bob_session_id, identities[2].session_id)
        self.assertEqual(server.FRIEND_OWNER_ID, identities[0].owner_id)
        self.assertNotEqual(identities[0].profile_id, identities[2].profile_id)
        self.assertNotEqual(identities[0].session_id, identities[2].session_id)
        self.assertEqual(identities[0].session_id, first["session_id"])
        self.assertEqual(identities[1].session_id, second["session_id"])
        self.assertEqual(identities[2].session_id, third["session_id"])

    @patch("server.urllib.request.urlopen")
    def test_owner_proxy_replaces_client_identity_with_verified_scope(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.headers.get_content_type.return_value = "application/json"
        response.__enter__.return_value.read.return_value = b'{"status":"ok"}'
        urlopen.return_value = response
        with self.identity_sessions() as issue:
            token = issue("google:alice")
            expected_session = verify_session(token)["session_id"]
            status, payload = self.request(
                "GET",
                "/owner/status",
                headers={
                    "X-Research-OS-Session": token,
                    "X-Research-OS-Owner": "attacker-owner",
                    "X-Research-OS-Profile": "attacker-profile",
                },
            )
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])
        forwarded = urlopen.call_args.args[0]
        headers = {key.lower(): value for key, value in forwarded.header_items()}
        self.assertEqual(server.FRIEND_OWNER_ID, headers["x-research-os-owner"])
        self.assertTrue(headers["x-research-os-profile"].startswith("user-"))
        self.assertEqual(expected_session, headers["x-research-os-session"])


    @patch("server.urllib.request.urlopen")
    def test_friend_generation_forwards_only_verified_scope_to_friend_service(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"provider":"owner-mock","text":"friend-ok"}'
        urlopen.return_value = response
        with self.identity_sessions() as issue:
            token = issue("google:api-e2e")
            expected_session = verify_session(token)["session_id"]
            with patch.dict(os.environ, {"RESEARCH_OS_AI_ROUTE": "friend"}, clear=False):
                status, payload = self.request(
                    "POST",
                    "/v1/ai/generate",
                    {"prompt": "e2e", "session_id": "spoofed-session"},
                    headers={
                        "X-Research-OS-Session": token,
                        "X-Research-OS-Owner": "spoofed-owner",
                        "X-Research-OS-Profile": "spoofed-profile",
                    },
                )
        self.assertEqual(200, status)
        self.assertEqual("friend-ok", payload["text"])
        self.assertEqual(expected_session, payload["session_id"])
        forwarded = urlopen.call_args.args[0]
        headers = {key.lower(): value for key, value in forwarded.header_items()}
        self.assertEqual(server.FRIEND_OWNER_ID, headers["x-research-os-owner"])
        self.assertTrue(headers["x-research-os-profile"].startswith("user-"))
        self.assertEqual(expected_session, headers["x-research-os-session"])

    def test_owner_proxy_rejects_missing_or_non_owner_session(self):
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request("GET", "/owner/status")
        self.assertEqual(401, missing.exception.code)
        with self.identity_sessions() as issue:
            token = issue("member-2", role="user")
            with self.assertRaises(urllib.error.HTTPError) as non_owner:
                self.request("GET", "/owner/status", headers={"X-Research-OS-Session": token})
        self.assertEqual(403, non_owner.exception.code)

    def test_memory_search_requires_a_verified_session_and_reports_shared_scope(self):
        query = urllib.parse.quote("conversation knowledge")
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request("GET", f"/v1/memory/search?q={query}&limit=3")
        self.assertEqual(401, missing.exception.code)
        with self.identity_sessions() as issue:
            token = issue("member-1", role="user")
            status, payload = self.request(
                "GET",
                f"/v1/memory/search?q={query}&limit=3",
                headers={"X-Research-OS-Session": token},
            )
        self.assertEqual(200, status)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn("artifact_id", payload["hits"][0])
        self.assertIn("score", payload["hits"][0])
        self.assertEqual("shared-owner-artifact-corpus", payload["scope"])

    @patch("server._friend_chat")
    def test_answer_with_memory_uses_mock_provider(self, friend_chat):
        friend_chat.return_value = {"provider": "mock", "text": "memory-backed mock answer"}
        with self.identity_sessions() as issue:
            token = issue("owner")
            expected_session = verify_session(token)["session_id"]
            with patch.dict(
                os.environ,
                {"RESEARCH_OS_AI_ROUTE": "friend"},
                clear=False,
            ):
                status, payload = self.request(
                    "POST",
                    "/v1/ai/answer-with-memory",
                    {
                        "provider": "mock",
                        "question": "conversation knowledge",
                        "session_id": "untrusted-memory-session",
                    },
                    headers={"X-Research-OS-Session": token},
                )
        self.assertEqual(200, status)
        self.assertEqual("mock", payload["provider"])
        self.assertEqual(expected_session, payload["session_id"])
        self.assertGreaterEqual(payload["memory_count"], 1)
        self.assertTrue(payload["text"])

    def test_conversation_analysis_is_preview_only(self):
        status, payload = self.request("POST", "/v1/conversations/analyze", {
            "title": "API integration",
            "conversation": [
                {"role": "user", "content": "Research OS ควรมี API กลางและไม่ควรผูกกับผู้ให้บริการ AI รายเดียว"},
                {"role": "assistant", "content": "ควรใช้ Provider Interface และ Adapter เพื่อเปลี่ยนโมเดลได้"},
            ],
            "tags": ["api", "provider"],
        })
        self.assertEqual(200, status)
        self.assertFalse(payload["persisted"])
        self.assertIn("artifact_id", payload["artifact"])

    def test_memory_commit_requires_explicit_confirmation_and_sync_key(self):
        original_dir = server.ARTIFACT_DIR
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"RESEARCH_OS_SYNC_KEY": "test-sync-key"},
            clear=False,
        ), self.identity_sessions() as issue:
            server.ARTIFACT_DIR = Path(tmp)
            token = issue("owner")
            auth_headers = {"X-Research-OS-Session": token}
            try:
                status, payload = self.request(
                    "POST",
                    "/v1/memory/commit",
                    {
                        "confirm": True,
                        "title": "Memory integration",
                        "conversation": [
                            {
                                "role": "user",
                                "content": "Research OS ต้องเก็บความรู้จาก Session แบบมีการยืนยันก่อนบันทึก",
                            },
                            {
                                "role": "assistant",
                                "content": "สรุปว่าควรใช้ explicit commit และค้นคืนผ่าน Memory Search",
                            },
                        ],
                        "tags": ["memory", "session"],
                        "min_quality": 20,
                    },
                    headers={**auth_headers, "X-Research-OS-Sync-Key": "test-sync-key"},
                )
                self.assertEqual(200, status)
                self.assertTrue(payload["persisted"])
                self.assertEqual("runtime-ephemeral", payload["durability"])
                self.assertEqual("shared-owner-artifact-corpus", payload["scope"])
                artifact_id = payload["artifact"]["artifact_id"]
                self.assertTrue(any(Path(tmp).glob(f"{artifact_id}*.md")))

                query = urllib.parse.quote("explicit commit")
                status, memory = self.request("GET", f"/v1/memory/search?q={query}", headers=auth_headers)
                self.assertEqual(200, status)
                self.assertGreaterEqual(memory["count"], 1)
            finally:
                server.ARTIFACT_DIR = original_dir

    def test_provider_list(self):
        status, payload = self.request("GET", "/v1/providers")
        self.assertEqual(200, status)
        self.assertIn("mock", payload["providers"])
        self.assertIn("anthropic", payload["providers"])


if __name__ == "__main__":
    unittest.main()
