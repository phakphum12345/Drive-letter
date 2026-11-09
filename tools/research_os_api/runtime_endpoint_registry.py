"""Atomic, loopback-only runtime endpoint registry for Research OS services.

Each service owns one JSON record (api.json / friend.json / developer.json), avoiding lost updates
when independent Windows services publish endpoints concurrently.
"""
from __future__ import annotations

import ipaddress
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SERVICES = frozenset({"api", "friend", "developer", "agent"})


def runtime_directory() -> Path:
    configured = os.environ.get("RESEARCH_OS_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return (Path(program_data) / "ResearchOS" / "runtime").resolve()
    state_home = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return (base / "research-os" / "runtime").resolve()


def _service_name(service: str) -> str:
    value = str(service).strip().lower()
    if value not in _SERVICES:
        raise ValueError("unsupported runtime service")
    return value


def endpoint_path(service: str, directory: str | Path | None = None) -> Path:
    name = _service_name(service)
    root = Path(directory).expanduser().resolve() if directory is not None else runtime_directory()
    return root / f"{name}.json"


def _validate_endpoint(host: str, port: int) -> tuple[str, int]:
    normalized_host = str(host).strip().strip("[]").lower()
    if normalized_host == "localhost":
        normalized_host = "127.0.0.1"
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError as exc:
        raise ValueError("runtime endpoints must bind to a loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("runtime endpoints must bind to a loopback IP")
    normalized_port = int(port)
    if normalized_port < 1 or normalized_port > 65535:
        raise ValueError("runtime endpoint port must be between 1 and 65535")
    return normalized_host, normalized_port


def publish_endpoint(
    service: str,
    host: str,
    port: int,
    *,
    directory: str | Path | None = None,
    pid: int | None = None,
) -> dict[str, Any]:
    name = _service_name(service)
    normalized_host, normalized_port = _validate_endpoint(host, port)
    path = endpoint_path(name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    url_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    record: dict[str, Any] = {
        "schema_version": 1,
        "service": name,
        "host": normalized_host,
        "port": normalized_port,
        "url": f"http://{url_host}:{normalized_port}",
        "pid": int(pid if pid is not None else os.getpid()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return record


def read_endpoint(
    service: str, *, directory: str | Path | None = None
) -> dict[str, Any] | None:
    name = _service_name(service)
    path = endpoint_path(name, directory)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or raw.get("service") != name:
        return None
    try:
        host, port = _validate_endpoint(str(raw.get("host", "")), int(raw.get("port", 0)))
        pid = int(raw.get("pid", 0))
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    url_host = f"[{host}]" if ":" in host else host
    expected_url = f"http://{url_host}:{port}"
    if raw.get("url") != expected_url:
        return None
    result = dict(raw)
    result.update({"host": host, "port": port, "pid": pid, "url": expected_url})
    return result


def remove_endpoint(
    service: str,
    *,
    directory: str | Path | None = None,
    expected_pid: int | None = None,
) -> bool:
    name = _service_name(service)
    path = endpoint_path(name, directory)
    current = read_endpoint(name, directory=directory)
    if current is None:
        return False
    if expected_pid is not None and current["pid"] != int(expected_pid):
        return False
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
