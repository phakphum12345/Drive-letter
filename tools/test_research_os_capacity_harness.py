from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "research_os_capacity_harness.py"


class _Handler(BaseHTTPRequestHandler):
    status_code = 200
    paths: list[str] = []

    def do_GET(self):
        type(self).paths.append(self.path)
        body = b'{"status":"ok"}'
        self.send_response(type(self).status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class CapacityHarnessIntegrationTests(unittest.TestCase):
    def setUp(self):
        _Handler.status_code = 200
        _Handler.paths = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "evidence.json"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def invoke(self, requests=3, concurrency=2):
        url = f"http://127.0.0.1:{self.server.server_port}/health?probe=1"
        return subprocess.run(
            [
                sys.executable, str(HARNESS), "--url", url,
                "--requests", str(requests), "--concurrency", str(concurrency),
                "--timeout", "2", "--output", str(self.output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_probe_records_local_http_success_and_query(self):
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(3, report["summary"]["requests_completed"])
        self.assertEqual(0, report["summary"]["requests_failed"])
        self.assertEqual({"200": 3}, report["summary"]["http_status_counts"])
        self.assertEqual("NOT_COLLECTED", report["resource_observation"]["server_process_cpu_memory"])
        self.assertEqual(3, len(_Handler.paths))
        self.assertTrue(all(path == "/health?probe=1" for path in _Handler.paths))

    def test_http_error_returns_nonzero_and_is_recorded(self):
        _Handler.status_code = 503
        result = self.invoke(requests=2, concurrency=1)
        self.assertEqual(2, result.returncode, result.stderr)
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(2, report["summary"]["requests_failed"])
        self.assertEqual({"503": 2}, report["summary"]["http_status_counts"])

    def test_invalid_request_bound_fails_before_network_access(self):
        result = self.invoke(requests=0)
        self.assertEqual(2, result.returncode)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
