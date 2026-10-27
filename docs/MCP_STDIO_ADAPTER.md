# DCP Native MCP stdio adapter (prototype)

- **Status:** protocol-aligned prototype; release certification is still pending
- **Transport:** STDIO only
- **Modern protocol:** `2026-07-28` using `server/discover` and per-request `_meta`
- **Legacy compatibility:** `2025-11-25` initialize handshake only; unsupported older revisions are rejected rather than incorrectly negotiated
- **Tools exposed:** `inspect_file`, `diff_files`
- **Writes / HTTP / OAuth:** not exposed or implemented

## Run locally

From the repository root:

```bash
python -m tools.mcp_engine.server --root ./docs
```

The configured root must already exist. The process reads newline-delimited JSON-RPC messages from standard input and writes protocol messages to standard output. Diagnostic messages, if any, go to standard error. Use a dedicated MCP client to launch the process; do not expose this command through a public web server.

Example MCP client configuration (adjust the absolute paths for the host):

```json
{
  "mcpServers": {
    "dcp-native-readonly": {
      "command": "python",
      "args": [
        "-m",
        "tools.mcp_engine.server",
        "--root",
        "/absolute/path/to/approved/project"
      ]
    }
  }
}
```

## Protocol behavior

The modern path handles `server/discover` and advertises `2026-07-28`. Modern requests carry the protocol version in `params._meta["io.modelcontextprotocol/protocolVersion"]`; responses include server identity in the result `_meta`. The adapter also retains a legacy `initialize` path for clients proposing `2025-11-25`; other legacy revisions are rejected rather than responding with a version the client may not support.

The official MCP Python SDK v2 client is used in CI through its real STDIO subprocess transport. That integration test must demonstrate modern discovery, tool listing, a read-only tool call, traversal denial, and no filesystem side effects. A green CI run is evidence for that exact tested SHA only; it is not release certification or proof of compatibility with every MCP host.

## Tool contract

### `inspect_file`

Input: `{"path":"relative/file.txt"}`

Reads one existing file under the server-configured root and returns the engine's size, encoding, SHA-256 and read-only operation evidence.

### `diff_files`

Input: `{"left_path":"before.txt","right_path":"after.txt"}`

Compares two existing files under the same configured root. UTF-8 files return a unified diff; binary/non-UTF-8 files return comparison metadata without a text diff.

## Security boundaries

- Root is configured by the server operator; tool callers cannot select or change the root.
- Tool names and argument keys are allowlisted; unknown tools and extra arguments are rejected.
- The adapter does not expose `copy_preview`, `copy_apply`, shell commands, process execution, network calls, or repository write operations.
- The server does not bind a TCP/HTTP port and does not implement remote authentication. STDIO access is local process access, so the launching client and host account must be trusted.
- The engine's file-size limit remains 2 MiB. The adapter also has a per-message size limit.
- MCP tool descriptions and file contents are untrusted data, not policy instructions.

## Verification

Run:

```bash
python -m compileall -q tools/mcp_engine
python -m unittest discover -s tests -p "test_native_mcp_*.py" -v
```

CI Lite installs the official SDK v2 line (`mcp>=2,<3`) to run the interoperability test. The SDK version resolved by a given CI run should be recorded from that run's logs before making a reproducibility claim. The adapter's own protocol tests still cover strict arguments, unknown-tool rejection, traversal denial, malformed JSON, oversized messages, and no-write behavior.

## Not yet implemented

- MCP Inspector and cross-host interoperability / conformance validation.
- A pinned SDK lockfile and a recorded exact dependency version for reproducible local runs.
- HTTP Streamable transport, OAuth, issuer/audience/scope validation, revocation and remote authorization.
- Resources, prompts, sampling, elicitation, production cancellation/timeouts and observability.
- Integration with Research OS identity/capability/policy/entitlement authorities.
- Release certification, cross-platform verification and deployment.

Do not mark the adapter production-ready, merge it, or deploy it based only on unit tests or a single official-client integration test.
