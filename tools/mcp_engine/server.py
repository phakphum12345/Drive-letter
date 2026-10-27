"""Minimal read-only MCP stdio adapter for the DCP native engine.

This intentionally implements only the JSON-RPC methods needed for a small
stdio MCP server. It does not expose HTTP, authentication, shell execution, or
write-capable engine functions.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from tools.mcp_engine.engine import EngineError, diff_files, inspect_file

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "dcp-native-mcp", "version": "0.1.0"}
MAX_LINE_BYTES = 1024 * 1024


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text_result(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
        "structuredContent": value,
        "isError": False,
    }


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "inspect_file",
            "description": "Read-only inspection of one existing file under the configured root; returns size, encoding and SHA-256.",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "diff_files",
            "description": "Read-only comparison of two existing files under the configured root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "left_path": {"type": "string", "minLength": 1},
                    "right_path": {"type": "string", "minLength": 1},
                },
                "required": ["left_path", "right_path"],
                "additionalProperties": False,
            },
        },
    ]


def _dispatch(message: dict[str, Any], root: str) -> dict[str, Any] | None:
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return _error(message.get("id"), -32600, "Invalid JSON-RPC request.")

    method = message["method"]
    request_id = message.get("id")
    is_notification = "id" not in message

    if method == "notifications/initialized":
        return None
    if method == "notifications/cancelled":
        return None
    if method == "initialize":
        params = message.get("params")
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid initialize params.")
        requested = params.get("protocolVersion")
        # Negotiate to the one version this adapter explicitly implements.
        version = requested if requested == PROTOCOL_VERSION else PROTOCOL_VERSION
        return _response(request_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": _tool_specs()})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _error(request_id, -32602, "Invalid tools/call params.")
        name = params["name"]
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "Tool arguments must be an object.")
        allowed = {
            "inspect_file": {"path"},
            "diff_files": {"left_path", "right_path"},
        }
        if name not in allowed:
            return _text_result({"status": "FAIL", "error": "Unknown tool."}) | {"result": {"isError": True, "content": [{"type": "text", "text": "Unknown tool."}]}, "id": request_id, "jsonrpc": "2.0"}
        if set(arguments) != allowed[name] or any(not isinstance(v, str) or not v for v in arguments.values()):
            return _error(request_id, -32602, "Invalid tool arguments.")
        try:
            if name == "inspect_file":
                value = inspect_file(root, arguments["path"])
            else:
                value = diff_files(root, arguments["left_path"], root, arguments["right_path"])
            return _response(request_id, _text_result(value))
        except (EngineError, OSError, ValueError) as exc:
            safe_message = str(exc) if isinstance(exc, EngineError) else "Unable to inspect the requested file."
            return _response(request_id, {
                "content": [{"type": "text", "text": json.dumps({"status": "FAIL", "error": safe_message}, ensure_ascii=False)}],
                "isError": True,
            })
    if is_notification:
        return None
    return _error(request_id, -32601, "Method not found.")


def serve(root: str) -> int:
    # Validate the root before accepting protocol requests.
    from pathlib import Path
    try:
        resolved = Path(root).expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("root is not a directory")
    except (OSError, ValueError):
        print("Configured root must be an existing directory.", file=sys.stderr)
        return 2

    for raw in sys.stdin.buffer:
        if len(raw) > MAX_LINE_BYTES:
            print(json.dumps(_error(None, -32700, "Message exceeds the size limit.")), flush=True)
            continue
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(json.dumps(_error(None, -32700, "Parse error.")), flush=True)
            continue
        if not isinstance(message, dict):
            print(json.dumps(_error(None, -32600, "Invalid JSON-RPC request.")), flush=True)
            continue
        response = _dispatch(message, str(resolved))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DCP read-only MCP stdio server")
    parser.add_argument("--root", required=True, help="Existing directory that bounds all file access")
    args = parser.parse_args(argv)
    return serve(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
