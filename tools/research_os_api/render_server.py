#!/usr/bin/env python3
"""Cloud and service entrypoint for Research OS API with browser-safe CORS headers."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from v2_server import V2ResearchOSHandler



FRIEND_URL = os.getenv("RESEARCH_OS_FRIEND_URL", "http://127.0.0.1:8790").rstrip("/")
FRIEND_OWNER_ID = os.getenv("RESEARCH_OS_FRIEND_OWNER", "owner").strip() or "owner"


def _friend_provider_health() -> dict[str, object]:
    request = urllib.request.Request(
        f"{FRIEND_URL}/owner/provider/health",
        headers={
            "Accept": "application/json",
            "X-Research-OS-Owner": FRIEND_OWNER_ID,
            "X-Research-OS-Profile": "default",
            "X-Research-OS-Session": "render-readiness",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Friend provider health response is not an object")
    return value


def _expected_provider() -> str:
    selected = os.getenv("RESEARCH_OS_PROVIDER", "gemini").strip().lower()
    if selected in {"local", "ollama"}:
        return "ollama-local"
    return selected


def _assert_friend_provider_ready() -> dict[str, object]:
    expected = _expected_provider()
    health = _friend_provider_health()
    if health.get("connected") is not True or health.get("provider") != expected:
        raise RuntimeError(
            f"Friend provider is not connected: expected {expected}, reported {health.get('provider')!r}"
        )
    return {"providers": [expected], "provider_health": health}


def _ensure_friend_service():
    """Reuse a local Friend service or start one inside this Render container."""
    parsed = urlsplit(FRIEND_URL)
    if parsed.scheme != "http" or (parsed.hostname or "").lower() not in {
        "127.0.0.1", "localhost", "::1"
    }:
        raise RuntimeError("Friend service must remain on an internal loopback HTTP address")
    port = parsed.port or 8790

    try:
        _assert_friend_provider_ready()
        return None
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
        # No reachable Friend provider: start the embedded service below.
        pass

    from owner_special.research_os_friend import OwnerFriendService

    repository_root = Path(__file__).resolve().parents[2]
    data_root = Path(
        os.getenv("RESEARCH_OS_OWNER_DATA_ROOT")
        or os.getenv("RESEARCH_OS_DATA_DIR")
        or (Path.home() / ".research_os_owner_special")
    ).expanduser().resolve()
    service = OwnerFriendService(
        owner_id=FRIEND_OWNER_ID,
        host="127.0.0.1",
        port=port,
        data_root=data_root,
        repository_root=repository_root,
    )
    service.start()
    try:
        last_error: Exception | None = None
        for _ in range(40):
            try:
                _assert_friend_provider_ready()
                return service
            except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
                last_error = exc
                time.sleep(0.25)
        raise RuntimeError(
            f"Friend service did not become provider-ready: {type(last_error).__name__ if last_error else 'timeout'}"
        )
    except Exception:
        service.close()
        raise


class CloudResearchOSHandler(V2ResearchOSHandler):
    """Primary Research OS handler with V1 compatibility and V2 namespace."""

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == "/health":
            try:
                _assert_friend_provider_ready()
            except Exception as exc:
                self._send(
                    503,
                    {
                        "status": "degraded",
                        "service": "research-os-api",
                        "friend": "unavailable",
                        "detail": type(exc).__name__,
                    },
                )
                return
        super().do_GET()

    def end_headers(self) -> None:
        configured_origins = {
            item.strip()
            for item in os.getenv(
                "RESEARCH_OS_ALLOWED_ORIGIN",
                "https://phakphum12345.github.io",
            ).split(",")
            if item.strip()
        }
        request_origin = self.headers.get("Origin", "").strip()
        self.send_header("Vary", "Origin")
        if request_origin and request_origin in configured_origins:
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Research-OS-Sync-Key, X-Research-OS-Owner, X-Research-OS-Profile, X-Research-OS-Session, X-Research-OS-OAuth-State, X-Research-OS-Client",
        )
        self.send_header("Access-Control-Max-Age", "86400")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()


def main() -> int:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "10000"))
    friend_service = _ensure_friend_service()
    server = None
    try:
        server = ThreadingHTTPServer((host, port), CloudResearchOSHandler)
        actual_port = int(server.server_address[1])
        os.environ["RESEARCH_OS_API_PORT"] = str(actual_port)
        print(f"Research OS primary API listening on http://{host}:{actual_port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        if friend_service is not None:
            friend_service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
