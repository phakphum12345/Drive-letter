from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import render_server


class RenderServerEntrypointTests(unittest.TestCase):
    def _run_main_with_env(self, env: dict[str, str], expected_host: str, expected_port: int) -> None:
        with patch.dict(os.environ, env, clear=True):
            with patch.object(render_server, "ThreadingHTTPServer") as server_factory:
                server = server_factory.return_value
                server.server_address = (expected_host, expected_port)
                self.assertEqual(render_server.main(), 0)
                server_factory.assert_called_once_with((expected_host, expected_port))
                server.serve_forever.assert_called_once_with()
                server.server_close.assert_called_once_with()
                self.assertEqual(os.environ["RESEARCH_OS_API_PORT"], str(expected_port))

    def test_defaults_bind_public_interface_and_render_port(self):
        self._run_main_with_env({}, "0.0.0.0", 10000)

    def test_uses_platform_injected_port(self):
        self._run_main_with_env({"PORT": "10037"}, "0.0.0.0", 10037)


if __name__ == "__main__":
    unittest.main()
