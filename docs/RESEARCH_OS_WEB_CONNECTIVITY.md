# Research OS Web ↔ API Connectivity Contract

Status: implementation target; live end-to-end verification is not implied by this document.

## Intended route

```text
GitHub Pages (https://phakphum12345.github.io)
  → HTTPS API base: https://phakphumwir.tail4b06c9.ts.net
  → Tailscale Serve
  → Windows Research OS API on its OS-assigned 127.0.0.1 port (runtime/api.json)
```

The browser must not use `localhost` or `127.0.0.1` as its API base: on an iPhone, those addresses refer to the iPhone, not the Windows host. The Windows API remains loopback-bound; Tailscale Serve is the access path. Do not expose the API port publicly or disable authentication/owner authorization.

## Native Flutter endpoint contract

- The Flutter API default is also `https://phakphumwir.tail4b06c9.ts.net`, so new installs do not target a hosted API.
- A saved endpoint on an `*.onrender.com` host is migrated to Tailscale Serve on load. On Windows, saved loopback URLs are refreshed from the current generated `runtime/api.json`; stale loopback URLs are discarded if no runtime record exists. Custom non-loopback endpoints remain explicit user choices.
- A Windows Flutter process discovers the current local API URL from `%ProgramData%\\ResearchOS\\runtime\\api.json` or the configured local data directory. It does not assume a fixed port.
- An iPhone must not use `127.0.0.1` for the Windows host; it uses the stable HTTPS Tailscale hostname.

## Browser/API contract

- The web client may override the default with `window.RESEARCH_OS_API_BASE_URL` before `app.js` loads.
- API requests use `credentials: 'include'` for session cookies.
- The API must return `Access-Control-Allow-Origin: https://phakphum12345.github.io` (not `*`) and `Access-Control-Allow-Credentials: true`.
- Preflight must allow the methods and headers actually used by the client.
- The Tailscale hostname must be reachable from the browsing device and its Tailscale identity must be authorized.
- Pairing links/secrets expire after 180 seconds; generate a fresh QR if it expires.

## Evidence and remaining runtime checks

Source contract tests can verify the configured URL and browser request policy. They cannot prove that Windows services are running, Tailscale Serve is online, CORS is correct on the live service, Google OAuth redirects are registered, or QR pairing completes. Those require runtime checks on the Windows host and a real browser/device.

## Expected verification sequence

1. GitHub Actions source/contract tests pass on the PR SHA.
2. GitHub Pages deployment completes from the intended branch/SHA.
3. From an authorized Tailscale client, open `https://phakphumwir.tail4b06c9.ts.net/health` and verify HTTP 200 JSON.
4. From GitHub Pages, verify the browser's `/health` request succeeds without CORS errors.
5. Verify provider status/login, callback, session status, QR pairing status, and owner-only routes independently.
6. Record the exact SHA, HTTP status, and response for each check; never infer a successful pairing from health alone.

## Dynamic local service endpoint contract

- API, Friend, Developer API, Agent API, and V3 local services request OS-assigned ports (`0`); the operating system chooses the actual socket port atomically during bind.
- The API publishes `runtime/api.json`, Friend publishes `runtime/friend.json`, Developer API publishes `runtime/developer.json`, and the optional Agent API publishes `runtime/agent.json`. Each service owns a separate atomic JSON file so concurrent writes cannot overwrite another service's record. V3 retains its own atomic `service.json` registry.
- Records contain schema version, service name, loopback host, actual port, URL, process ID, and update timestamp. They contain no credentials or user data.
- Consumers validate the schema and loopback address before using a record. Missing, malformed, mismatched, or non-loopback records fail closed.
- API resolves Friend from the runtime registry at request time. Windows Flutter resolves API and Developer API registries on Windows; evaluation tools resolve the Agent API registry when it is started; Web/iOS use configured stable HTTPS endpoints.
- Ollama remains at `127.0.0.1:11434` with the existing model configuration. It is a provider endpoint, not a Research OS service port.
- Service shutdown removes only the endpoint record owned by that process ID. It does not terminate listeners by port number.
