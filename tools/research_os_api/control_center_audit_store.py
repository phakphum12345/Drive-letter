"""Authenticated, local-first persistence for Native Control Center audit snapshots.

Audit records are observations, not release authority. Each record is scoped to
the verified Research OS user and stored beneath the configured data root.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from local_storage import data_root

_LOCK = threading.RLock()
_ALLOWED_STATUS = frozenset({"PASS", "FAIL", "DEFERRED", "PARTIAL"})
_ALLOWED_CHECK_STATE = frozenset({"PASS", "FAIL", "DEFERRED", "UNKNOWN"})
_MAX_AUDITS_PER_USER = 100


def _path() -> Path:
    return data_root() / "sessions" / "control_center_audits.json"


def _user_id(value: str) -> str:
    result = str(value or "").strip()
    if (
        not result
        or any(ord(char) < 32 or ord(char) == 127 for char in result)
        or result in {".", ".."}
        or "/" in result
        or chr(92) in result
    ):
        raise ValueError("invalid user_id")
    return result


def _read() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return {"users": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("control center audit store is unreadable")
    if not isinstance(value, dict) or not isinstance(value.get("users", {}), dict):
        raise RuntimeError("control center audit store has an invalid shape")
    value.setdefault("users", {})
    return value


def _write(value: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _normalize(snapshot: dict[str, Any]) -> dict[str, Any]:
    audit_id = str(snapshot.get("audit_id") or "").strip()
    if not audit_id or len(audit_id) > 128:
        raise ValueError("audit_id must be 1..128 characters")
    status = str(snapshot.get("status") or "").strip().upper()
    if status not in _ALLOWED_STATUS:
        raise ValueError("unsupported audit status")
    observed_at = str(snapshot.get("observed_at") or "").strip()
    if not observed_at or len(observed_at) > 64:
        raise ValueError("observed_at is required")
    source = str(snapshot.get("source") or "Native Control Center").strip()[:160]
    raw_checks = snapshot.get("checks", [])
    if not isinstance(raw_checks, list) or len(raw_checks) > 32:
        raise ValueError("checks must be a list containing at most 32 items")
    checks = []
    for raw in raw_checks:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("check") or "").strip()
        state = str(raw.get("state") or "UNKNOWN").strip().upper()
        if not name or len(name) > 120 or state not in _ALLOWED_CHECK_STATE:
            raise ValueError("invalid audit check")
        checks.append({
            "check": name,
            "state": state,
            "detail": str(raw.get("detail") or "")[:500],
        })
    if not checks:
        raise ValueError("at least one audit check is required")
    return {
        "audit_id": audit_id,
        "observed_at": observed_at,
        "status": status,
        "source": source,
        "checks": checks,
    }


def list_audits(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    scoped = _user_id(user_id)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with _LOCK:
        users = _read()["users"]
        records = users.get(scoped, [])
        if not isinstance(records, list):
            raise RuntimeError("user audit history has an invalid shape")
        return [item for item in records[-limit:][::-1] if isinstance(item, dict)]


def save_audit(user_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    scoped = _user_id(user_id)
    normalized = _normalize(snapshot)
    with _LOCK:
        value = _read()
        users = value["users"]
        records = users.get(scoped, [])
        if not isinstance(records, list):
            raise RuntimeError("user audit history has an invalid shape")
        records = [item for item in records if isinstance(item, dict)]
        records = [item for item in records if item.get("audit_id") != normalized["audit_id"]]
        records.append(normalized)
        users[scoped] = records[-_MAX_AUDITS_PER_USER:]
        _write(value)
    return normalized


__all__ = ["list_audits", "save_audit"]
