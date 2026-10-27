"""Protocol-level tests for the DCP read-only MCP stdio adapter."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class McpStdioServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
        (self.root / "b.txt").write_text("alpha\ngamma\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, messages):
        payload = "".join(json.dumps(item) + "\n" for item in messages)
        result = subprocess.run(
            [sys.executable, "-m", "tools.mcp_engine.server", "--root", str(self.root)],
            input=payload, text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_and_tools_list_expose_only_read_only_tools(self):
        replies = self.request([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2026-07-28")
        names = {tool["name"] for tool in replies[1]["result"]["tools"]}
        self.assertEqual(names, {"inspect_file", "diff_files"})

    def test_inspect_file_returns_hash_and_read_only_evidence(self):
        replies = self.request([{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                 "params": {"name": "inspect_file", "arguments": {"path": "a.txt"}}}])
        value = replies[0]["result"]["structuredContent"]
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["operation"], "READ_ONLY")
        self.assertEqual(len(value["sha256"]), 64)

    def test_diff_file_returns_diff(self):
        replies = self.request([{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                 "params": {"name": "diff_files", "arguments": {"left_path": "a.txt", "right_path": "b.txt"}}}])
        value = replies[0]["result"]["structuredContent"]
        self.assertFalse(value["equal"])
        self.assertIn("-beta", value["diff"])
        self.assertIn("+gamma", value["diff"])

    def test_unknown_tool_is_rejected(self):
        replies = self.request([{"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                 "params": {"name": "copy_apply", "arguments": {}}}])
        self.assertTrue(replies[0]["result"]["isError"])

    def test_extra_arguments_are_rejected(self):
        replies = self.request([{"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                                 "params": {"name": "inspect_file", "arguments": {"path": "a.txt", "apply": True}}}])
        self.assertEqual(replies[0]["error"]["code"], -32602)

    def test_path_traversal_is_denied(self):
        replies = self.request([{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                 "params": {"name": "inspect_file", "arguments": {"path": "../outside.txt"}}}])
        self.assertTrue(replies[0]["result"]["isError"])

    def test_malformed_json_gets_parse_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "tools.mcp_engine.server", "--root", str(self.root)],
            input="{bad json}\n", text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], -32700)

    def test_no_write_side_effects(self):
        before = sorted(p.name for p in self.root.iterdir())
        self.request([{"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                       "params": {"name": "inspect_file", "arguments": {"path": "a.txt"}}}])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
