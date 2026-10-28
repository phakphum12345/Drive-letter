"""Read-only MCP stdio adapter for the DCP native engine.

Supports the MCP 2026-07-28 stateless request envelope and the 2025-11-25
legacy initialize handshake for existing hosts. No HTTP, auth, shell, or
write-capable engine function is exposed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.mcp_engine.engine import EngineError, diff_files, inspect_file

PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "dcp-native-mcp", "version": "0.2.0"}
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
MAX_LINE_BYTES = 1024 * 1024


def _response(
    request_id: Any,
    result: dict[str, Any],
    *,
    modern: bool = False,
    cacheable: bool = False,
) -> dict[str, Any]:
    if modern:
        result.setdefault("_meta", {SERVER_INFO_META_KEY: SERVER_INFO})
        result.setdefault("resultType", "complete")
    if modern and cacheable:
        result.setdefault("ttlMs", 0)
        result.setdefault("cacheScope", "public")
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
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    envelope = params.get("_meta")
    envelope = envelope if isinstance(envelope, dict) else {}
    requested_version = envelope.get(PROTOCOL_VERSION_META_KEY)
    modern_request = requested_version == PROTOCOL_VERSION

    # 2026-07-28 discovery is a regular request, not an initialize handshake.
    if method == "server/discover":
        if not modern_request:
            return _error(request_id, -32022, "Unsupported protocol version.")
        return _response(request_id, {
            "supportedVersions": [PROTOCOL_VERSION],
            "capabilities": {"tools": {"listChanged": False}},
        }, modern=True, cacheable=True)

    # Retain compatibility with existing pre-2026 hosts, but never label their
    # handshake as 2026-07-28.
    if method == "initialize":
        init_params = message.get("params")
        if not isinstance(init_params, dict):
            return _error(request_id, -32602, "Invalid initialize params.")
        requested = init_params.get("protocolVersion")
        if requested != LEGACY_PROTOCOL_VERSION:
            return _error(request_id, -32022, "Unsupported protocol version.")
        return _response(request_id, {
            "protocolVersion": LEGACY_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized" or method == "notifications/cancelled":
        return None

    if not modern_request:
        # Non-discovery requests must be versioned either by the modern
        # per-request envelope or by the legacy initialize flow.
        if method not in ("ping", "tools/list", "tools/call"):
            return None if is_notification else _error(request_id, -32601, "Method not found.")
    elif method == "ping":
        # ping was removed from the modern protocol.
        return _error(request_id, -32601, "Method not found.")

    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": _tool_specs()}, modern=modern_request, cacheable=modern_request)
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
            return _response(request_id, {
                "isError": True,
                "content": [{"type": "text", "text": "Unknown tool."}],
            }, modern=modern_request)
        if set(arguments) != allowed[name] or any(not isinstance(v, str) or not v for v in arguments.values()):
            return _error(request_id, -32602, "Invalid tool arguments.")
        try:
            if name == "inspect_file":
                value = inspect_file(root, arguments["path"])
            else:
                value = diff_files(root, arguments["left_path"], root, arguments["right_path"])
            return _response(request_id, _text_result(value), modern=modern_request)
        except (EngineError, OSError, ValueError) as exc:
            safe_message = str(exc) if isinstance(exc, EngineError) else "Unable to inspect the requested file."
            return _response(request_id, {
                "content": [{"type": "text", "text": json.dumps({"status": "FAIL", "error": safe_message}, ensure_ascii=False)}],
                "isError": True,
            }, modern=modern_request)
    if is_notification:
        return None
    return _error(request_id, -32601, "Method not found.")


def serve(root: str) -> int:
    try:
        resolved = Path(root).expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("root is not a directory")
    except (OSError, ValueError):
        print("Configured root must be an existing directory.", file=sys.stderr)
        return 2

    while True:
        raw = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not raw:
            break
        if len(raw) > MAX_LINE_BYTES:
            while raw and not raw.endswith(bytes([10])):
                raw = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
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
