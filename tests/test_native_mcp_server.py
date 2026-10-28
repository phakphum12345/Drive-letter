"""Protocol-level and official-client tests for the DCP read-only MCP stdio adapter."""
import asyncio
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

    def test_legacy_initialize_and_tools_list_expose_only_read_only_tools(self):
        replies = self.request([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-11-25")
        names = {tool["name"] for tool in replies[1]["result"]["tools"]}
        self.assertEqual(names, {"inspect_file", "diff_files", "crowdin_list_projects", "crowdin_list_project_files"})

    def test_modern_discovery_has_correct_protocol_metadata(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 1, "method": "server/discover",
            "params": {"_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
            }},
        }])
        result = replies[0]["result"]
        self.assertEqual(result["supportedVersions"], ["2026-07-28"])
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "dcp-native-mcp")

    def test_modern_requests_require_version_envelope(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}},
        }])
        self.assertEqual({tool["name"] for tool in replies[0]["result"]["tools"]}, {"inspect_file", "diff_files"})

    def test_inspect_file_returns_hash_and_read_only_evidence(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "inspect_file", "arguments": {"path": "a.txt"}},
        }])
        value = replies[0]["result"]["structuredContent"]
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["operation"], "READ_ONLY")
        self.assertEqual(len(value["sha256"]), 64)

    def test_diff_file_returns_diff(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "diff_files", "arguments": {"left_path": "a.txt", "right_path": "b.txt"}},
        }])
        value = replies[0]["result"]["structuredContent"]
        self.assertFalse(value["equal"])
        self.assertIn("-beta", value["diff"])
        self.assertIn("+gamma", value["diff"])

    def test_unknown_tool_is_rejected(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "copy_apply", "arguments": {}},
        }])
        self.assertTrue(replies[0]["result"]["isError"])

    def test_extra_arguments_are_rejected(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "inspect_file", "arguments": {"path": "a.txt", "apply": True}},
        }])
        self.assertEqual(replies[0]["error"]["code"], -32602)

    def test_path_traversal_is_denied(self):
        replies = self.request([{
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "inspect_file", "arguments": {"path": "../outside.txt"}},
        }])
        self.assertTrue(replies[0]["result"]["isError"])

    def test_malformed_json_gets_parse_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "tools.mcp_engine.server", "--root", str(self.root)],
            input="{bad json}\n", text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], -32700)

    def test_oversized_message_is_rejected_and_server_recovers(self):
        payload = ("x" * (1024 * 1024 + 32)) + "\n" + json.dumps(
            {"jsonrpc": "2.0", "id": 9, "method": "ping"}
        ) + "\n"
        result = subprocess.run(
            [sys.executable, "-m", "tools.mcp_engine.server", "--root", str(self.root)],
            input=payload, text=True, capture_output=True, timeout=10,
        )
        replies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[1]["id"], 9)
        self.assertEqual(replies[1]["result"], {})

    def test_no_write_side_effects(self):
        before = sorted(p.name for p in self.root.iterdir())
        self.request([{
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
                       "name": "inspect_file", "arguments": {"path": "a.txt"}},
        }])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)


class OfficialMcpClientInteropTests(unittest.TestCase):
    """Exercise the actual stdio transport and modern negotiation in MCP SDK v2."""

    def test_official_sdk_discovers_lists_and_calls_only_read_tools(self):
        from mcp import Client, StdioServerParameters

        async def exercise():
            before = sorted(p.name for p in self.root.iterdir())
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "tools.mcp_engine.server", "--root", str(self.root)],
            )
            async with Client(params) as client:
                self.assertEqual(client.protocol_version, "2026-07-28")
                self.assertEqual(client.server_info.name, "dcp-native-mcp")
                tools = await client.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, {"inspect_file", "diff_files", "crowdin_list_projects", "crowdin_list_project_files"})
                inspected = await client.call_tool("inspect_file", {"path": "a.txt"})
                self.assertFalse(inspected.is_error)
                self.assertEqual(inspected.structured_content["operation"], "READ_ONLY")
                denied = await client.call_tool("inspect_file", {"path": "../outside.txt"})
                self.assertTrue(denied.is_error)
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)

        asyncio.run(exercise())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
        (self.root / "b.txt").write_text("alpha\ngamma\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
