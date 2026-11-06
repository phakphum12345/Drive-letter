from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import render_server


class RenderServerEntrypointTests(unittest.TestCase):
    def _run_main_with_env(self, env: dict[str, str], expected_host: str, expected_port: int) -> None:
        with patch.dict(os.environ, env, clear=True):
            with patch.object(render_server, "_ensure_friend_service", return_value=None) as friend_start:
                with patch.object(render_server, "ThreadingHTTPServer") as server_factory:
                    server = server_factory.return_value
                    server.server_address = (expected_host, expected_port)
                    self.assertEqual(render_server.main(), 0)
                    friend_start.assert_called_once_with()
                    server_factory.assert_called_once_with((expected_host, expected_port), render_server.CloudResearchOSHandler)
                    server.serve_forever.assert_called_once_with()
                    server.server_close.assert_called_once_with()
                    self.assertEqual(os.environ["RESEARCH_OS_API_PORT"], str(expected_port))

    def test_defaults_bind_public_interface_and_render_port(self):
        self._run_main_with_env({}, "0.0.0.0", 10000)

    def test_uses_platform_injected_port(self):
        self._run_main_with_env({"PORT": "10037"}, "0.0.0.0", 10037)

    def test_friend_readiness_requires_expected_provider(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "gemini"}, clear=True):
            with patch.object(render_server, "_friend_status", return_value={"providers": ["gemini"]}):
                self.assertEqual(render_server._assert_friend_provider_ready()["providers"], ["gemini"])

    def test_friend_readiness_rejects_mock_when_gemini_is_selected(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "gemini"}, clear=True):
            with patch.object(render_server, "_friend_status", return_value={"providers": ["owner-mock"]}):
                with self.assertRaisesRegex(RuntimeError, "provider mismatch"):
                    render_server._assert_friend_provider_ready()

    def test_local_mode_maps_to_ollama_provider(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "local"}, clear=True):
            self.assertEqual(render_server._expected_provider(), "ollama-local")

    def test_existing_friend_with_wrong_provider_fails_closed(self):
        with patch.object(render_server, "FRIEND_URL", "http://127.0.0.1:8790"):
            with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "gemini"}, clear=True):
                with patch.object(render_server, "_friend_status", return_value={"providers": ["owner-mock"]}):
                    with self.assertRaisesRegex(RuntimeError, "provider mismatch"):
                        render_server._ensure_friend_service()

    def test_health_returns_503_when_friend_provider_is_unavailable(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), render_server.CloudResearchOSHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(render_server, "_assert_friend_provider_ready", side_effect=RuntimeError("not ready")):
                request = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/health")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(request, timeout=3)
                self.assertEqual(503, raised.exception.code)
                payload = json.loads(raised.exception.read().decode("utf-8"))
                self.assertEqual("degraded", payload["status"])
                self.assertEqual("RuntimeError", payload["detail"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)



if __name__ == "__main__":
    unittest.main()
