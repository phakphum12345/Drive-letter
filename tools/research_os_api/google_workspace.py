from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


WORKSPACE_SERVICES = (
    "drive",
    "docs",
    "sheets",
    "calendar",
    "gmail",
    "contacts",
    "tasks",
    "keep",
    "meet",
    "forms",
    "chat",
)

DEFAULT_SCOPES = {
    "drive": ("https://www.googleapis.com/auth/drive",),
    "docs": ("https://www.googleapis.com/auth/documents",),
    "sheets": ("https://www.googleapis.com/auth/spreadsheets",),
    "calendar": ("https://www.googleapis.com/auth/calendar",),
    "gmail": ("https://www.googleapis.com/auth/gmail.modify",),
    "contacts": ("https://www.googleapis.com/auth/contacts",),
    "tasks": ("https://www.googleapis.com/auth/tasks",),
    "keep": ("https://www.googleapis.com/auth/keep",),
    "meet": ("https://www.googleapis.com/auth/meetings.space.created",),
    "forms": ("https://www.googleapis.com/auth/forms.body.readonly", "https://www.googleapis.com/auth/forms.responses.readonly"),
    "chat": ("https://www.googleapis.com/auth/chat.spaces.readonly", "https://www.googleapis.com/auth/chat.messages.readonly"),
}


GOOGLE_CLIENT_JSON_ENV = "RESEARCH_OS_GOOGLE_CLIENT_JSON_FILE"


def load_google_oauth_client_credentials() -> tuple[str, str, tuple[str, ...], bool]:
    """Load one matched Google OAuth web-client pair from Render Secret Files or env.

    An explicitly configured JSON path wins over environment variables. On
    Render, a single client_secret_*.json in /etc/secrets is auto-discovered.
    The complete client ID/secret pair is always taken from the same source.
    """
    configured_path = os.environ.get(GOOGLE_CLIENT_JSON_ENV, "").strip()
    secret_dir = Path("/etc/secrets")
    if configured_path:
        path = Path(configured_path).expanduser()
    elif secret_dir.is_dir():
        candidates = sorted(secret_dir.glob("client_secret_*.json"))
        if len(candidates) > 1:
            raise ValueError("multiple Google OAuth client JSON files found in /etc/secrets")
        path = candidates[0] if candidates else None
    else:
        path = None

    if path is not None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Google OAuth client JSON file cannot be read") from exc
        web = payload.get("web") if isinstance(payload, dict) else None
        if not isinstance(web, dict):
            raise ValueError("Google OAuth client JSON must contain a web client")
        client_id = str(web.get("client_id") or "").strip()
        client_secret = str(web.get("client_secret") or "").strip()
        raw_redirects = web.get("redirect_uris")
        redirects = tuple(
            str(item).strip()
            for item in raw_redirects
            if isinstance(item, str) and item.strip()
        ) if isinstance(raw_redirects, list) else ()
        if not client_id or not client_secret:
            raise ValueError("Google OAuth client JSON is missing client credentials")
        if not redirects:
            raise ValueError("Google OAuth client JSON has no authorized redirect URIs")
        return client_id, client_secret, redirects, True

    client_id = (
        os.environ.get("RESEARCH_OS_GOOGLE_CLIENT_ID")
        or os.environ.get("GOOGLE_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.environ.get("RESEARCH_OS_GOOGLE_CLIENT_SECRET")
        or os.environ.get("GOOGLE_CLIENT_SECRET")
        or ""
    ).strip()
    return client_id, client_secret, (), False


@dataclass(frozen=True)
class WorkspaceServiceStatus:
    service: str
    enabled: bool
    state: str
    scopes: tuple[str, ...]
    note: str = ""


class GoogleWorkspaceConfig:
    """Local-first Google Workspace configuration surface.

    Client secrets and refresh tokens stay on the backend. Flutter receives only
    capability/status metadata and never the raw credentials.
    """

    def __init__(self, data_dir: str | os.PathLike[str] | None = None) -> None:
        root = Path(data_dir or os.environ.get("RESEARCH_OS_DATA_DIR") or Path.home() / "ResearchOSData")
        self.root = root / "google_workspace"
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.root / "settings.json"
        self.token_path = self.root / "oauth_token.json"

    @property
    def client_id_configured(self) -> bool:
        try:
            return bool(load_google_oauth_client_credentials()[0])
        except ValueError:
            return False

    @property
    def client_secret_configured(self) -> bool:
        try:
            return bool(load_google_oauth_client_credentials()[1])
        except ValueError:
            return False

    @property
    def oauth_configured(self) -> bool:
        return self.client_id_configured and self.client_secret_configured

    @property
    def connected(self) -> bool:
        if not self.token_path.exists():
            return False
        try:
            payload = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        return bool(payload.get("access_token") or payload.get("refresh_token"))

    def _load_enabled(self) -> set[str]:
        if not self.settings_path.exists():
            return set(WORKSPACE_SERVICES)
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return set(WORKSPACE_SERVICES)
        raw = payload.get("enabled_services", WORKSPACE_SERVICES)
        return {str(item) for item in raw if str(item) in WORKSPACE_SERVICES}

    def set_enabled_services(self, services: Iterable[str]) -> None:
        enabled = sorted({str(item) for item in services if str(item) in WORKSPACE_SERVICES})
        self.settings_path.write_text(json.dumps({"enabled_services": enabled}, ensure_ascii=False, indent=2), encoding="utf-8")

    def statuses(self) -> list[WorkspaceServiceStatus]:
        enabled = self._load_enabled()
        result: list[WorkspaceServiceStatus] = []
        for service in WORKSPACE_SERVICES:
            is_enabled = service in enabled
            if not is_enabled:
                state = "disabled"
                note = "disabled by user"
            elif not self.oauth_configured:
                state = "not_configured"
                note = "Google OAuth client ID/secret required on backend"
            elif not self.connected:
                state = "ready_for_oauth"
                note = "OAuth credentials configured; user authorization still required"
            else:
                state = "connected"
                note = "Google OAuth token is stored on the backend"
            result.append(WorkspaceServiceStatus(service, is_enabled, state, DEFAULT_SCOPES[service], note))
        return result

    def dashboard(self) -> dict:
        statuses = self.statuses()
        return {
            "hub": "google_workspace",
            "oauth_configured": self.oauth_configured,
            "client_id_configured": self.client_id_configured,
            "client_secret_configured": self.client_secret_configured,
            "connected": self.connected,
            "services": [asdict(item) for item in statuses],
            "connected_count": sum(1 for item in statuses if item.state == "connected"),
            "enabled_count": sum(1 for item in statuses if item.enabled),
            "total_count": len(statuses),
            "token_storage": "backend_only",
            "local_root": str(self.root),
        }


def get_google_workspace_dashboard() -> dict:
    return GoogleWorkspaceConfig().dashboard()
