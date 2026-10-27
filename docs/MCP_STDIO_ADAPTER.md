# DCP Native MCP stdio adapter (prototype)

- **Status:** local prototype; not release-certified
- **Transport:** STDIO only
- **Protocol target:** `2026-07-28`
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

These tests cover basic JSON-RPC initialize/discovery/calls, strict arguments, unknown-tool rejection, traversal denial and no-write behavior. They are not a substitute for interoperability testing with an official MCP SDK/client or MCP Inspector. Until that test is recorded, **real MCP client interoperability remains UNKNOWN**.

## Not yet implemented

- Official SDK/Inspector interoperability and conformance validation.
- HTTP Streamable transport, OAuth, issuer/audience/scope validation, revocation and remote authorization.
- Resources, prompts, sampling, elicitation, cancellation/timeouts and production observability.
- Integration with Research OS identity/capability/policy/entitlement authorities.
- Release certification, cross-platform verification and deployment.

Do not mark the adapter production-ready, merge it, or deploy it based only on the prototype unit tests.
