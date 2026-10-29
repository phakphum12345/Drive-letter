# Research OS Web ↔ API Connectivity Contract

Status: implementation target; live end-to-end verification is not implied by this document.

## Intended route

```text
GitHub Pages (https://phakphum12345.github.io)
  → HTTPS API base: https://phakphumwir.tail4b06c9.ts.net
  → Tailscale Serve
  → Windows Research OS API on 127.0.0.1:8787
```

The browser must not use `localhost` or `127.0.0.1` as its API base: on an iPhone, those addresses refer to the iPhone, not the Windows host. The Windows API remains loopback-bound; Tailscale Serve is the access path. Do not expose the API port publicly or disable authentication/owner authorization.

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
