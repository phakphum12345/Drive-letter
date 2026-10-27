# Research OS MCP Platform Evolution

- **Document ID:** ROS-MCP-PLATFORM-001
- **Version:** 0.1.0
- **Status:** RESEARCH BASELINE / PROPOSED
- **Last reviewed:** 2026-10-28
- **Scope:** Research OS / Drive-letter integration with the DCP-owned Native MCP Engine
- **Authority:** Design and evidence only; this document grants no execution, authorization, merge, or release authority.

## 1. Executive decision

Extend the existing Native MCP Engine rather than replace it. The engine remains the local-first Python inspection/diff/copy-preview domain library and CLI. This branch adds a small STDIO JSON-RPC adapter prototype around it; that prototype is not yet certified against an official MCP SDK/client and does not implement HTTP/OAuth or remote authorization. Keep policy and authorization server-side before each operation.

The initial implementation target is a **read-only, local-first MCP adapter** for bounded source inspection, SHA-256 evidence, and diff preview. Keep copy-apply outside the initial tool catalogue; it remains an explicit local CLI operation until a separately reviewed approval and authorization contract exists. Do not add a public listener, secrets, remote repository mutation, automatic merge/deploy, shell/process execution, or implicit trust in model/tool descriptions.

## 2. Findings from the current repository

Source files inspected on the `main` branch:
- `docs/native-mcp-engine.md`
- `tools/mcp_engine/engine.py`
- `tests/test_native_mcp_engine.py`
- `docs/native-mcp-engine-test-plan.md`

### Existing capabilities

- Root-confined file inspection with SHA-256 and a per-file size limit.
- Unified diff for UTF-8 text; binary differences are represented as metadata.
- Copy preview that performs no write.
- Explicit copy-apply to a new destination, exclusive file creation, and post-copy hash verification.
- Unit tests for path traversal, absolute paths, file size limits, copy-preview no-write behavior, hash verification, overwrite refusal, and a competing-file race.

### Missing capabilities (not assumed to exist)

- Official MCP SDK/client interoperability and protocol conformance evidence (a minimal STDIO server prototype now exists on this branch).
- Resources/prompts discovery and any capabilities beyond the two initial read-only tools.
- Production transport lifecycle, cancellation/timeout behavior, and interoperability tests against an MCP client/Inspector.
- Server-side identity, policy, authorization, per-tool scopes, and revocation.
- Remote HTTP deployment, OAuth authorization, request-level rate/size/time budgets, and operational audit storage.
- Formal threat model and adversarial tests for prompt injection, tool poisoning, confused-deputy behavior, secret exposure, and untrusted server metadata.
- Research OS API integration contracts and platform UI projection.
- Cross-platform build/run verification for Windows, Web, and iOS.

A successful unit test of the existing library is not proof of any missing capability above.

## 3. External documentation reviewed

This is a design synthesis, not a claim that every behavior in every SDK has been implemented. Protocol features must be pinned to a version and tested before adoption.

1. **MCP Specification — 2026-07-28 release**  
   https://modelcontextprotocol.io/specification/2026-07-28  
   Release overview: https://blog.modelcontextprotocol.io/posts/2026-07-28/  
   Relevant themes: stateless protocol core, per-request protocol metadata, server discovery, header-based routing, cache hints, multi-round-trip requests, formal extensions, and authorization hardening. This release is a breaking change from the earlier initialize/session model; do not silently mix protocol eras.

2. **MCP authorization specification**  
   https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization  
   Treat HTTP authorization as a server-side responsibility. Validate issuer, token audience/resource, scopes, and expiry; never forward a bearer token to another upstream as token passthrough. Keep STDIO credential handling distinct from HTTP OAuth.

3. **Official MCP Python SDK**  
   https://github.com/modelcontextprotocol/python-sdk  
   https://py.sdk.modelcontextprotocol.io/  
   The current v2 SDK supports servers/clients, tools/resources/prompts, STDIO and Streamable HTTP. Before adoption, compare the pinned SDK and its exact spec support against the existing Python runtime and repository dependency policy. Do not add an unpinned dependency or assume v1/v2 compatibility.

4. **Official MCP TypeScript SDK**  
   https://github.com/modelcontextprotocol/typescript-sdk  
   https://ts.sdk.modelcontextprotocol.io/v2/  
   The current v2 package layout separates client and server packages and targets the 2026-07-28 spec. Use it as a compatibility reference if a TypeScript/browser-facing adapter is considered; do not duplicate the Python engine's domain logic in a second runtime without a concrete need.

5. **OpenAI MCP server guide and risk guidance**  
   https://developers.openai.com/api/docs/guides/tools-connectors-mcp  
   https://developers.openai.com/api/docs/mcp  
   Remote servers can expose data and actions; tool calls can be configured to require approval. Treat prompt injection and overly broad tool parameters as design threats. Prefer minimal scopes, reviewed servers, and explicit approval for sensitive actions.

6. **GitHub MCP server configuration**  
   https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md  
   Supports toolset selection, individual tool allowlists, read-only mode, and lockdown controls. Read-only filtering takes precedence over write tools. Lockdown is described as best-effort content filtering, not a security boundary; enforce authority in the actual server/policy layer too.

7. **GitHub Copilot MCP guidance**  
   https://docs.github.com/en/copilot/concepts/customizations/mcp  
   Enable only the tools needed, prefer read-only tools, review third-party servers and their data access, and do not assume all clients support resources/prompts or the same OAuth flows.

## 4. Platform target architecture

```text
Research OS UI / automation surface
            |
            v
MCP Client Adapter (explicit server allowlist)
            |
            v
MCP Protocol Adapter (version-pinned; schema validation)
            |
            v
Identity -> Capability -> Policy -> Authorization -> Entitlement
            |
            v
Tool Dispatcher (read-only allowlist, budgets, cancellation)
            |
            v
Existing Native MCP Engine (inspect / diff / preview)
            |
            v
Evidence envelope (status, operation, input digest, result digest,
source SHA, protocol/adapter version, correlation ID, timestamps)
            |
            v
Existing Research OS evidence / final-gate authorities
```

The UI, model, tool metadata, adapter, and worker are not policy authorities. Reuse existing Research OS identity, policy, authorization, evidence, and final-gate services where their contracts are verified. Do not create parallel approval, evidence, health, or release authorities.

## 5. Implementation phases and gates

### Phase A — Inventory and contract freeze
- [x] Inspect existing engine, tests, and design notes.
- [x] Review official protocol, SDK, authorization, OpenAI, and GitHub references.
- [x] Inspect current CI workflow and verify the existing engine has no third-party runtime dependency manifest at the repository root.
- [x] Pin the prototype protocol target to `2026-07-28` in the adapter and document it.
- [ ] Record official SDK/client interoperability and compatibility range in a machine-readable contract.
- **Gate:** prototype uses Python standard library only; do not add a remote server or third-party dependency until compatibility and policy are reviewed.

### Phase B — Read-only adapter prototype
- [x] Add a thin STDIO adapter around existing engine functions; no duplicated file-processing logic.
- [x] Expose only `inspect_file` and `diff_files`; copy preview remains out of the tool catalogue.
- [x] Validate allowed tool names and exact argument keys; reject traversal through the existing engine and reject invalid roots/over-limit messages.
- [ ] Add additional output-size limits and adversarial symlink/race coverage.
- [ ] Keep configured roots server-owned; callers may select only a relative path inside an allowlisted root.
- [ ] Return bounded structured results with explicit `PASS/FAIL/SKIPPED/UNKNOWN`, operation type, SHA-256, and truncation indicators.
- [x] Add basic JSON-RPC initialize, tool discovery/call, malformed JSON, extra-argument, unknown-tool, traversal, no-write, and oversized-message tests; wire them into CI Lite.
- [ ] Add protocol-level tests with an official compatible client/Inspector and test cancellation, timeout, oversized output, and transport disconnects.
- **Gate:** prototype has no write tools, public listener, or secrets; keep Draft until official-client interoperability and remaining negative tests are evidenced.

### Phase C — Security and governance
- [ ] Write a threat model for prompt injection, tool poisoning, confused deputy, path races/symlinks, SSRF, secret leakage, replay, and denial-of-service.
- [ ] Enforce identity/capability/policy/authorization/entitlement server-side before dispatch.
- [ ] Allowlist tool names and parameter schemas; reject unknown tools by default.
- [ ] Add per-request time, output, concurrency, and rate budgets; redact sensitive values from logs.
- [ ] Treat tool descriptions, resource content, repository text, and server metadata as untrusted data, never as policy instructions.
- [ ] For HTTP deployment, follow the pinned MCP authorization spec and validate token issuer, audience/resource, scopes, expiry, and revocation behavior.
- [ ] Keep local STDIO and remote HTTP profiles separate; do not expose a local service publicly as a shortcut.
- **Gate:** negative tests prove unauthorized calls cannot reach engine functions; no credential/token passthrough.

### Phase D — Research OS integration
- [ ] Publish a versioned integration contract and a capability inventory, including source of truth and owner for every field.
- [ ] Project MCP server status, tools, scopes, protocol version, latency, evidence links, and error states into the app without granting authority to the UI.
- [ ] Display unknown, stale, denied, truncated, and unavailable states distinctly; never convert missing evidence to PASS.
- [ ] Reuse the existing Back Box/checkpoint and evidence patterns rather than creating another artifact authority.
- [ ] Keep locale-independent stable identifiers and localizable UI strings separate from protocol payloads.
- **Gate:** UI actions are presentation-only unless a separately authorized, server-backed operation is implemented.

### Phase E — Controlled write capability (not in initial scope)
- [ ] Define a separate capability and policy for every write operation.
- [ ] Require explicit, attributable approval bound to exact parameters, destination, and source/result hashes.
- [ ] Revalidate policy and destination immediately before the write; never overwrite existing files.
- [ ] Emit immutable audit evidence and support denial/revocation.
- [ ] Prohibit auto-merge, release, deployment, workflow dispatch, shell/process execution, and credential management unless separately specified, reviewed, and approved.
- **Gate:** remain unimplemented until all required security and approval evidence passes.

### Phase F — Release certification
- [ ] Unit tests, protocol conformance/interoperability tests, adversarial security tests, schema/contract tests, and regression suite.
- [ ] CI checks tied to the exact commit SHA; inspect every required workflow result.
- [ ] Verify local STDIO profile and any HTTP profile separately.
- [ ] Verify Windows execution; record Web/iOS as not applicable to the server runtime unless an actual client surface requires those builds.
- [ ] Manual review of tool inventory, permissions, logging redaction, and user-visible error/unknown states.
- **Gate:** Draft remains until exact-SHA evidence is complete; merge and deployment require separate approval.

## 6. Required contracts

Each tool definition must record:
- stable tool ID and version;
- purpose and side-effect classification;
- strict input and output schemas;
- required capability and policy ID;
- allowlisted root/resource scope;
- time, byte, concurrency, and rate limits;
- approval requirement;
- audit/evidence fields;
- failure modes and whether retry is safe;
- protocol/SDK compatibility range.

Each evidence record should include, where available:
- event and correlation IDs;
- actor/client identity (non-secret identifier);
- tool ID/version and protocol version;
- source repository/ref/commit SHA and relative path;
- input digest and output digest;
- policy/authorization/entitlement decision references;
- start/end timestamps, duration, operation result;
- truncation and error metadata.

Do not store bearer tokens, API keys, full secrets, or unnecessary conversation contents in evidence or logs.

## 7. Acceptance criteria

- Existing engine tests remain passing and unchanged engine semantics are preserved.
- MCP protocol tests prove discovery/list/call behavior for the pinned protocol and SDK.
- Read-only mode is enforced in the server dispatcher, not only through client UI or annotations.
- Unauthorized, unknown, malformed, oversized, timed-out, and out-of-root calls fail closed.
- No existing destination can be overwritten; initial MCP tools cannot write.
- Tool results and evidence are bounded, attributable, and do not mislabel missing checks as success.
- CI status is verified for the exact final SHA.
- No merge, deployment, or release is inferred from documentation or unit tests alone.

## 8. Evidence status at authoring

| Item | Status | Basis |
|---|---|---|
| Existing local engine identified | PASS | Repository files inspected |
| Existing engine is a wire-protocol server | FAIL | Existing documentation explicitly says it is not |
| Official documentation synthesis | PASS | Sources listed in section 3 reviewed on 2026-10-28 |
| Adapter implemented | SKIPPED | This change is a research/architecture baseline only |
| MCP interoperability tests | UNKNOWN | No protocol adapter exists to test yet |
| Remote auth / deployment | UNKNOWN | Not implemented or verified |
| Merge / deployment | SKIPPED | No merge or deployment performed |

## 9. Change control

This document does not authorize runtime changes by itself. Implementation must be incremental, reuse the existing engine and Research OS authority chain, keep the initial tool set read-only, and provide exact-SHA evidence. Any change to protocol version, SDK major version, authentication model, write permissions, or evidence contract requires a reviewed contract/version update.

## Revision history

- **0.1.0 — 2026-10-28:** Initial research baseline and phased platform-level upgrade plan.
