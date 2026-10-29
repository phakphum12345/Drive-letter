"""Read-only Crowdin API v2 adapter used by the local MCP stdio server.

Only fixed HTTPS GET endpoints are allowed. The personal access token is read
from the host process environment and is never included in output or errors.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Callable

API_BASE = "https://api.crowdin.com/api/v2"
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_LIMIT = 25


class CrowdinAdapterError(RuntimeError):
    """Safe, user-facing error from a read-only Crowdin API call."""


class CrowdinAdapter:
    def __init__(
        self,
        token: str,
        *,
        opener: Callable[..., Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise CrowdinAdapterError("CROWDIN_PERSONAL_ACCESS_TOKEN is not configured.")
        self._token = token.strip()
        self._opener = opener or urlopen
        self._timeout = timeout

    def _get(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "DCP-read-only-MCP-adapter/0.1",
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise CrowdinAdapterError(
                    f"Crowdin rejected the configured credential (HTTP {exc.code})."
                ) from None
            raise CrowdinAdapterError(
                f"Crowdin API request failed (HTTP {exc.code})."
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            # Do not expose request headers, credentials, or implementation details.
            raise CrowdinAdapterError(
                f"Crowdin API is unreachable ({type(exc).__name__})."
            ) from None

        if len(raw) > MAX_RESPONSE_BYTES:
            raise CrowdinAdapterError("Crowdin API response exceeds the 1 MiB limit.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CrowdinAdapterError("Crowdin API returned invalid JSON.") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise CrowdinAdapterError("Crowdin API response has an unexpected shape.")
        return payload

    @staticmethod
    def _unwrap(payload: dict[str, Any], fields: tuple[str, ...]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in payload["data"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("data"), dict):
                continue
            data = entry["data"]
            items.append({key: data[key] for key in fields if key in data})
        return items

    def list_projects(self) -> dict[str, Any]:
        """Return a bounded summary of projects visible to the configured token."""
        payload = self._get(f"/projects?limit={DEFAULT_LIMIT}")
        items = self._unwrap(
            payload, ("id", "name", "identifier", "sourceLanguageId", "targetLanguageIds")
        )
        return {
            "status": "PASS",
            "operation": "READ_ONLY",
            "resource": "crowdin.projects",
            "count": len(items),
            "limit": DEFAULT_LIMIT,
            "items": items,
        }

    def list_project_files(self, project_id: str) -> dict[str, Any]:
        """Return a bounded summary of files in one numeric Crowdin project."""
        if not isinstance(project_id, str) or not project_id.isascii() or not project_id.isdigit():
            raise CrowdinAdapterError("project_id must be a positive integer.")
        if int(project_id) < 1:
            raise CrowdinAdapterError("project_id must be a positive integer.")
        payload = self._get(f"/projects/{int(project_id)}/files?limit={DEFAULT_LIMIT}")
        items = self._unwrap(payload, ("id", "name", "type", "path"))
        return {
            "status": "PASS",
            "operation": "READ_ONLY",
            "resource": "crowdin.project_files",
            "project_id": int(project_id),
            "count": len(items),
            "limit": DEFAULT_LIMIT,
            "items": items,
        }
