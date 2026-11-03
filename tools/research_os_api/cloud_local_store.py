"""Durable owner-scoped storage for the Cloud + Local control plane.

SQLite is used for local development and tests. Production must configure
RESEARCH_OS_DATABASE_URL with PostgreSQL and install cloud-local-requirements.txt.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from .local_storage import data_root
except ImportError:  # pragma: no cover - direct unittest discovery
    from local_storage import data_root


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CloudLocalStore:
    """Transactional storage with owner scoping and lease fencing."""

    def __init__(self, database_url: str | None = None, *, sqlite_path: str | Path | None = None):
        configured = (database_url or os.getenv("RESEARCH_OS_DATABASE_URL") or "").strip()
        if configured.startswith(("postgres://", "postgresql://")):
            self.backend, self.database_url, self.sqlite_path = "postgres", configured, None
        else:
            if sqlite_path is None and (os.getenv("RENDER", "").strip().lower() == "true" or os.getenv("RESEARCH_OS_RUNTIME_MODE", "").strip().lower() == "cloud"):
                raise RuntimeError("RESEARCH_OS_DATABASE_URL must point to PostgreSQL in cloud mode; ephemeral SQLite fallback is disabled")
            self.backend, self.database_url = "sqlite", None
            raw = sqlite_path or (configured.removeprefix("sqlite:///") if configured.startswith("sqlite:///") else "")
            self.sqlite_path = Path(raw).expanduser() if raw else data_root() / "cloud_local.sqlite3"
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self):
        if self.backend == "sqlite":
            db = sqlite3.connect(str(self.sqlite_path), timeout=30, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 30000")
            return db
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL storage requires cloud-local-requirements.txt") from exc
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _execute(self, db, sql: str, params: tuple[Any, ...] = ()):
        return db.execute(sql.replace("?", "%s") if self.backend == "postgres" else sql, params)

    @contextmanager
    def _transaction(self) -> Iterator[Any]:
        db = self._connect()
        try:
            if self.backend == "sqlite":
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def _reader(self) -> Iterator[Any]:
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    def initialize(self) -> None:
        ddl = (
            """CREATE TABLE IF NOT EXISTS cloud_local_jobs (
                owner_id TEXT NOT NULL, job_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL, execution_mode TEXT NOT NULL, required_capabilities TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                assigned_agent_id TEXT, lease_id TEXT, lease_expires_at TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(owner_id, job_id), UNIQUE(owner_id, idempotency_key))""",
            "CREATE INDEX IF NOT EXISTS idx_cloud_local_jobs_ready ON cloud_local_jobs(owner_id,status,created_at)",
            """CREATE TABLE IF NOT EXISTS cloud_local_agents (
                owner_id TEXT NOT NULL, agent_id TEXT NOT NULL, device_id TEXT NOT NULL,
                token_hash TEXT NOT NULL, lifecycle_state TEXT NOT NULL, payload TEXT NOT NULL,
                last_heartbeat_at TEXT, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id,agent_id), UNIQUE(owner_id,device_id), UNIQUE(token_hash))""",
            """CREATE TABLE IF NOT EXISTS cloud_local_enrollment_grants (
                grant_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL, expires_at TEXT NOT NULL,
                used_at TEXT, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS cloud_local_evidence (
                owner_id TEXT NOT NULL, evidence_id TEXT NOT NULL, job_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(owner_id,evidence_id))""",
            "CREATE INDEX IF NOT EXISTS idx_cloud_local_evidence_job ON cloud_local_evidence(owner_id,job_id,occurred_at)",
            """CREATE TABLE IF NOT EXISTS cloud_local_evidence_recovery_keys (
                owner_id TEXT NOT NULL, recovery_key TEXT NOT NULL, evidence_id TEXT NOT NULL,
                PRIMARY KEY(owner_id,recovery_key))""",
            """CREATE TABLE IF NOT EXISTS cloud_local_checkpoints (
                owner_id TEXT NOT NULL, job_id TEXT NOT NULL, checkpoint_id TEXT NOT NULL,
                created_at TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(owner_id,checkpoint_id), UNIQUE(owner_id,job_id,checkpoint_id))""",
            "CREATE INDEX IF NOT EXISTS idx_cloud_local_checkpoints_job ON cloud_local_checkpoints(owner_id,job_id,created_at)",
        )
        with self._transaction() as db:
            for statement in ddl:
                self._execute(db, statement)

    @staticmethod
    def _payload(row: Any) -> dict[str, Any] | None:
        return json.loads(row["payload"]) if row else None

    def create_job(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        owner, job_id, key = payload["owner_id"], payload["job_id"], payload["idempotency_key"]
        now = _stamp()
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._transaction() as db:
            self._execute(db, """INSERT INTO cloud_local_jobs
                (owner_id,job_id,idempotency_key,status,execution_mode,required_capabilities,payload,created_at,updated_at,attempt)
                VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(owner_id,idempotency_key) DO NOTHING""",
                (owner, job_id, key, payload["status"], payload["execution_mode"],
                 json.dumps(payload.get("required_capabilities", [])), encoded, now, now, int(payload.get("attempt", 0))))
            row = self._execute(db, "SELECT payload FROM cloud_local_jobs WHERE owner_id=? AND idempotency_key=?",
                                (owner, key)).fetchone()
            if row is None:
                raise RuntimeError("job insert did not produce a readable record")
            stored = self._payload(row)
            return stored, stored["job_id"] != job_id

    def get_job(self, owner_id: str, job_id: str) -> dict[str, Any] | None:
        with self._reader() as db:
            row = self._execute(db, "SELECT payload FROM cloud_local_jobs WHERE owner_id=? AND job_id=?",
                                (owner_id, job_id)).fetchone()
            return self._payload(row)

    def list_jobs(self, owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._reader() as db:
            rows = self._execute(db, "SELECT payload FROM cloud_local_jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                                 (owner_id, max(1, min(int(limit), 100)))).fetchall()
            return [self._payload(row) for row in rows]

    def cancel_job(self, owner_id: str, job_id: str) -> dict[str, Any] | None:
        now = _stamp()
        cancellable = {"QUEUED", "ASSIGNED", "RUNNING", "CHECKPOINTING", "WAITING_FOR_LOCAL_AGENT", "RETRY_WAIT"}
        with self._transaction() as db:
            row = self._execute(db, "SELECT payload FROM cloud_local_jobs WHERE owner_id=? AND job_id=?",
                                (owner_id, job_id)).fetchone()
            if not row:
                return None
            payload = self._payload(row)
            if payload["status"] in cancellable:
                payload.update(status="CANCELLED", updated_at=now, lease_id=None, lease_expires_at=None)
                self._execute(db, """UPDATE cloud_local_jobs SET status='CANCELLED',payload=?,updated_at=?,
                    lease_id=NULL,lease_expires_at=NULL WHERE owner_id=? AND job_id=?""",
                    (json.dumps(payload, ensure_ascii=False, sort_keys=True), now, owner_id, job_id))
            return payload

    def create_enrollment_grant(self, owner_id: str, ttl_seconds: int = 600) -> str:
        token, now = secrets.token_urlsafe(32), _now()
        expires = _stamp(now + timedelta(seconds=max(60, min(int(ttl_seconds), 3600))))
        with self._transaction() as db:
            self._execute(db, "INSERT INTO cloud_local_enrollment_grants VALUES (?,?,?,NULL,?)",
                          (_digest(token), owner_id, expires, _stamp(now)))
        return token

    def enrollment_grant_owner(self, grant_token: str) -> str | None:
        with self._reader() as db:
            row = self._execute(db, """SELECT owner_id,expires_at,used_at
                FROM cloud_local_enrollment_grants WHERE grant_hash=?""", (_digest(grant_token),)).fetchone()
            if not row or row["used_at"] is not None or row["expires_at"] <= _stamp():
                return None
            return str(row["owner_id"])

    def enroll_agent(self, grant_token: str, *, owner_id: str, device_id: str,
                     protocol_versions: list[str], capabilities: list[dict[str, str]],
                     os_name: str, agent_version: str, os_version: str = "") -> tuple[dict[str, Any], str]:
        now, agent_id, token = _now(), "agent-" + uuid.uuid4().hex, secrets.token_urlsafe(48)
        stamp = _stamp(now)
        payload = {
            "contract_version": "1.0", "agent_id": agent_id, "owner_id": owner_id,
            "device_id": device_id, "protocol_versions": protocol_versions,
            "capabilities": capabilities, "lifecycle_state": "ACTIVE", "os_name": os_name,
            "os_version": os_version, "agent_version": agent_version,
            "last_heartbeat_at": stamp, "registered_at": stamp, "revoked_at": None,
        }
        with self._transaction() as db:
            grant = self._execute(db, "SELECT owner_id,expires_at,used_at FROM cloud_local_enrollment_grants WHERE grant_hash=?",
                                  (_digest(grant_token),)).fetchone()
            if not grant or grant["owner_id"] != owner_id or grant["used_at"] is not None or grant["expires_at"] <= stamp:
                raise ValueError("enrollment_grant_invalid_or_expired")
            self._execute(db, "UPDATE cloud_local_enrollment_grants SET used_at=? WHERE grant_hash=? AND used_at IS NULL",
                          (stamp, _digest(grant_token)))
            self._execute(db, """INSERT INTO cloud_local_agents
                (owner_id,agent_id,device_id,token_hash,lifecycle_state,payload,last_heartbeat_at,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (owner_id, agent_id, device_id, _digest(token), "ACTIVE",
                 json.dumps(payload, ensure_ascii=False, sort_keys=True), stamp, stamp))
        return payload, token

    def authenticate_agent(self, token: str) -> dict[str, Any] | None:
        with self._reader() as db:
            row = self._execute(db, "SELECT owner_id,agent_id,lifecycle_state,payload FROM cloud_local_agents WHERE token_hash=?",
                                (_digest(token),)).fetchone()
            if not row or row["lifecycle_state"] != "ACTIVE":
                return None
            return {"owner_id": row["owner_id"], "agent_id": row["agent_id"], "agent": self._payload(row)}

    def heartbeat_agent(self, owner_id: str, agent_id: str,
                        capabilities: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
        stamp = _stamp()
        with self._transaction() as db:
            row = self._execute(db, "SELECT payload,lifecycle_state FROM cloud_local_agents WHERE owner_id=? AND agent_id=?",
                                (owner_id, agent_id)).fetchone()
            if not row or row["lifecycle_state"] == "REVOKED":
                return None
            payload = self._payload(row)
            if capabilities is not None:
                payload["capabilities"] = capabilities
            payload.update(lifecycle_state="ACTIVE", last_heartbeat_at=stamp)
            self._execute(db, """UPDATE cloud_local_agents SET lifecycle_state='ACTIVE',payload=?,last_heartbeat_at=?
                WHERE owner_id=? AND agent_id=?""",
                (json.dumps(payload, ensure_ascii=False, sort_keys=True), stamp, owner_id, agent_id))
            return payload

    def list_agents(self, owner_id: str) -> list[dict[str, Any]]:
        with self._reader() as db:
            rows = self._execute(
                db,
                "SELECT payload FROM cloud_local_agents WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [self._payload(row) for row in rows]

    def transition_job(self, owner_id: str, agent_id: str, job_id: str, lease_token: str,
                       status: str, output_refs: list[dict[str, Any]] | None = None,
                       checkpoint_id: str | None = None,
                       evidence: dict[str, Any] | None = None) -> dict[str, Any] | None:
        now = _now()
        allowed = {
            "ASSIGNED": {"RUNNING", "FAILED", "WAITING_FOR_LOCAL_AGENT"},
            "RUNNING": {"CHECKPOINTING", "COMPLETED", "FAILED", "WAITING_FOR_LOCAL_AGENT"},
            "CHECKPOINTING": {"RUNNING", "COMPLETED", "FAILED", "WAITING_FOR_LOCAL_AGENT"},
        }
        if status not in {"RUNNING", "CHECKPOINTING", "WAITING_FOR_LOCAL_AGENT", "COMPLETED", "FAILED"}:
            raise ValueError("job_status_transition_invalid")
        with self._transaction() as db:
            row = self._execute(db, """SELECT payload,lease_id,lease_expires_at,status,assigned_agent_id
                FROM cloud_local_jobs WHERE owner_id=? AND job_id=?""", (owner_id, job_id)).fetchone()
            if (not row or row["assigned_agent_id"] != agent_id or row["lease_id"] != lease_token
                or not row["lease_expires_at"] or row["lease_expires_at"] <= _stamp(now)):
                return None
            if status not in allowed.get(row["status"], set()):
                raise ValueError("job_status_transition_invalid")
            payload = self._payload(row)
            payload.update(status=status, updated_at=_stamp(now))
            if output_refs is not None:
                payload["output_refs"] = output_refs
            if checkpoint_id is not None:
                payload["checkpoint_id"] = checkpoint_id
            terminal = status in {"COMPLETED", "FAILED"}
            release_for_wait = status == "WAITING_FOR_LOCAL_AGENT"
            if terminal or release_for_wait:
                payload["lease_id"] = None
                payload["lease_expires_at"] = None
            if release_for_wait:
                payload["assigned_worker_id"] = None
            self._execute(db, """UPDATE cloud_local_jobs SET status=?,payload=?,updated_at=?,
                assigned_agent_id=?,lease_id=?,lease_expires_at=? WHERE owner_id=? AND job_id=? AND lease_id=?""",
                (status, json.dumps(payload, ensure_ascii=False, sort_keys=True), _stamp(now),
                 None if release_for_wait else agent_id,
                 None if terminal or release_for_wait else lease_token,
                 None if terminal or release_for_wait else row["lease_expires_at"],
                 owner_id, job_id, lease_token))
            if evidence is not None:
                if evidence.get("owner_id") != owner_id or evidence.get("job_id") != job_id:
                    raise ValueError("transition_evidence_scope_mismatch")
                self._execute(db, "INSERT INTO cloud_local_evidence VALUES (?,?,?,?,?)",
                    (owner_id, evidence["evidence_id"], job_id, evidence["occurred_at"],
                     json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
            return payload

    def revoke_agent(self, owner_id: str, agent_id: str) -> bool:
        with self._transaction() as db:
            row = self._execute(db, "SELECT payload FROM cloud_local_agents WHERE owner_id=? AND agent_id=?",
                                (owner_id, agent_id)).fetchone()
            if not row:
                return False
            payload = self._payload(row)
            payload.update(lifecycle_state="REVOKED", revoked_at=_stamp())
            self._execute(db, """UPDATE cloud_local_agents SET lifecycle_state='REVOKED',token_hash=?,payload=?
                WHERE owner_id=? AND agent_id=?""",
                ("revoked:" + uuid.uuid4().hex, json.dumps(payload, ensure_ascii=False, sort_keys=True), owner_id, agent_id))
            return True

    def claim_local_job(self, owner_id: str, agent_id: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        now = _now()
        expiry = _stamp(now + timedelta(seconds=max(15, min(int(lease_seconds), 600))))
        with self._transaction() as db:
            agent_row = self._execute(db, "SELECT payload,lifecycle_state FROM cloud_local_agents WHERE owner_id=? AND agent_id=?",
                                      (owner_id, agent_id)).fetchone()
            if not agent_row or agent_row["lifecycle_state"] != "ACTIVE":
                raise ValueError("agent_not_active")
            capabilities = {item.get("name") for item in self._payload(agent_row).get("capabilities", [])}
            sql = """SELECT job_id,payload FROM cloud_local_jobs WHERE owner_id=?
                AND status IN ('QUEUED','WAITING_FOR_LOCAL_AGENT') AND execution_mode IN ('LOCAL','HYBRID')
                ORDER BY created_at"""
            if self.backend == "postgres":
                sql += " FOR UPDATE SKIP LOCKED"
            for row in self._execute(db, sql, (owner_id,)).fetchall():
                payload = self._payload(row)
                if not set(payload.get("required_capabilities", [])).issubset(capabilities):
                    continue
                lease = secrets.token_urlsafe(24)
                payload.update(status="ASSIGNED", assigned_worker_id=agent_id, lease_id=lease,
                               lease_expires_at=expiry, attempt=int(payload.get("attempt", 0))+1, updated_at=_stamp(now))
                self._execute(db, """UPDATE cloud_local_jobs SET status='ASSIGNED',assigned_agent_id=?,lease_id=?,
                    lease_expires_at=?,attempt=?,payload=?,updated_at=? WHERE owner_id=? AND job_id=?
                    AND status IN ('QUEUED','WAITING_FOR_LOCAL_AGENT')""",
                    (agent_id, lease, expiry, payload["attempt"], json.dumps(payload, ensure_ascii=False, sort_keys=True),
                     _stamp(now), owner_id, payload["job_id"]))
                payload["lease_token"] = lease
                return payload
        return None

    def renew_lease(self, owner_id: str, agent_id: str, job_id: str, lease_token: str,
                    lease_seconds: int = 60) -> dict[str, Any] | None:
        now = _now()
        expiry = _stamp(now + timedelta(seconds=max(15, min(int(lease_seconds), 600))))
        with self._transaction() as db:
            row = self._execute(db, """SELECT payload,lease_id,lease_expires_at,status,assigned_agent_id
                FROM cloud_local_jobs WHERE owner_id=? AND job_id=?""", (owner_id, job_id)).fetchone()
            if (not row or row["assigned_agent_id"] != agent_id or row["lease_id"] != lease_token
                or row["status"] not in {"ASSIGNED", "RUNNING", "CHECKPOINTING"} or not row["lease_expires_at"]
                or row["lease_expires_at"] <= _stamp(now)):
                return None
            payload = self._payload(row)
            payload.update(lease_expires_at=expiry, updated_at=_stamp(now))
            self._execute(db, "UPDATE cloud_local_jobs SET lease_expires_at=?,payload=?,updated_at=? WHERE owner_id=? AND job_id=? AND lease_id=?",
                (expiry, json.dumps(payload, ensure_ascii=False, sort_keys=True), _stamp(now), owner_id, job_id, lease_token))
            return payload

    def create_checkpoint(self, owner_id: str, agent_id: str, job_id: str,
                         lease_token: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now = _now()
        stamp = _stamp(now)
        with self._transaction() as db:
            row = self._execute(db, """SELECT payload,lease_id,lease_expires_at,status,assigned_agent_id
                FROM cloud_local_jobs WHERE owner_id=? AND job_id=?""", (owner_id, job_id)).fetchone()
            if (not row or row["assigned_agent_id"] != agent_id or row["lease_id"] != lease_token
                or row["status"] not in {"RUNNING", "CHECKPOINTING"} or not row["lease_expires_at"]
                or row["lease_expires_at"] <= stamp):
                return None
            job = self._payload(row)
            if payload.get("owner_id") != owner_id or payload.get("job_id") != job_id:
                raise ValueError("checkpoint_owner_or_job_mismatch")
            if not job.get("source_sha") or payload.get("source_sha") != job.get("source_sha"):
                raise ValueError("checkpoint_source_sha_mismatch")
            supersedes = payload.get("supersedes_checkpoint_id")
            if supersedes:
                parent = self._execute(db, """SELECT payload FROM cloud_local_checkpoints
                    WHERE owner_id=? AND job_id=? AND checkpoint_id=?""",
                    (owner_id, job_id, supersedes)).fetchone()
                if parent is None:
                    raise ValueError("superseded_checkpoint_not_found")
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            self._execute(db, "INSERT INTO cloud_local_checkpoints VALUES (?,?,?,?,?)",
                (owner_id, job_id, payload["checkpoint_id"], stamp, encoded))
            job.update(checkpoint_id=payload["checkpoint_id"], status="CHECKPOINTING", updated_at=stamp)
            self._execute(db, """UPDATE cloud_local_jobs SET status='CHECKPOINTING',payload=?,updated_at=?
                WHERE owner_id=? AND job_id=? AND lease_id=?""",
                (json.dumps(job, ensure_ascii=False, sort_keys=True), stamp, owner_id, job_id, lease_token))
            return payload

    def list_checkpoints(self, owner_id: str, job_id: str) -> list[dict[str, Any]]:
        with self._reader() as db:
            rows = self._execute(db, """SELECT payload FROM cloud_local_checkpoints
                WHERE owner_id=? AND job_id=? ORDER BY created_at DESC""", (owner_id, job_id)).fetchall()
            return [self._payload(row) for row in rows]

    def resume_checkpoint(self, owner_id: str, job_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        job = self.get_job(owner_id, job_id)
        if job is None:
            return None
        records = self.list_checkpoints(owner_id, job_id)
        checkpoint = next((item for item in records if item.get("checkpoint_id") == checkpoint_id), None)
        if checkpoint is None:
            return None
        failures = []
        if checkpoint.get("source_sha") != job.get("source_sha"):
            failures.append("source_sha_mismatch")
        if checkpoint.get("workflow_state") == "COMPLETED":
            failures.append("checkpoint_already_completed")
        if checkpoint.get("workflow_state") in {"BLOCKED", "DEFERRED"}:
            failures.append("checkpoint_not_resumable")
        if job.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
            failures.append("job_is_terminal")
        if any(item.get("supersedes_checkpoint_id") == checkpoint_id for item in records):
            failures.append("checkpoint_superseded")
        return {
            "status": "HOLD" if failures else "READY",
            "checkpoint": checkpoint,
            "job_status": job.get("status"),
            "source_sha": job.get("source_sha"),
            "failures": failures,
            "next_action": "repair_checkpoint_then_reverify" if failures else checkpoint["next_action"],
        }

    def append_evidence(self, owner_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._transaction() as db:
            self._execute(db, "INSERT INTO cloud_local_evidence VALUES (?,?,?,?,?)",
                (owner_id, payload["evidence_id"], payload["job_id"], payload["occurred_at"],
                 json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
        return payload

    def append_recovered_evidence(self, owner_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Atomically deduplicate recovered evidence by owner-scoped provenance key."""
        recovery_key = str(payload.get("recovery_key") or "")
        if not recovery_key:
            raise ValueError("recovery_key_required")
        with self._transaction() as db:
            inserted = self._execute(db, """INSERT INTO cloud_local_evidence_recovery_keys
                (owner_id,recovery_key,evidence_id) VALUES (?,?,?) ON CONFLICT(owner_id,recovery_key) DO NOTHING""",
                (owner_id, recovery_key, payload["evidence_id"]))
            if inserted.rowcount == 0:
                row = self._execute(db, """SELECT e.payload FROM cloud_local_evidence e
                    JOIN cloud_local_evidence_recovery_keys k
                      ON k.owner_id=e.owner_id AND k.evidence_id=e.evidence_id
                    WHERE k.owner_id=? AND k.recovery_key=?""", (owner_id, recovery_key)).fetchone()
                if row is None:
                    raise RuntimeError("recovery_key_registry_inconsistent")
                return self._payload(row), False
            self._execute(db, "INSERT INTO cloud_local_evidence VALUES (?,?,?,?,?)",
                (owner_id, payload["evidence_id"], payload["job_id"], payload["occurred_at"],
                 json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
            return payload, True

    def list_evidence(self, owner_id: str, job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._reader() as db:
            rows = self._execute(db, """SELECT payload FROM cloud_local_evidence WHERE owner_id=? AND job_id=?
                ORDER BY occurred_at LIMIT ?""", (owner_id, job_id, max(1, min(int(limit), 250)))).fetchall()
            return [self._payload(row) for row in rows]

    def append_recovery_audit(self, owner_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Append a redacted, owner-scoped audit record for each evidence resolution attempt."""
        if payload.get("owner_id") != owner_id or not payload.get("job_id"):
            raise ValueError("recovery_audit_scope_mismatch")
        record = dict(payload)
        record.setdefault("audit_id", "audit-" + uuid.uuid4().hex)
        record.setdefault("occurred_at", _stamp())
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._transaction() as db:
            self._execute(db, "INSERT INTO cloud_local_recovery_audit VALUES (?,?,?,?,?)",
                          (owner_id, record["audit_id"], record["job_id"], record["occurred_at"], encoded))
        return record

    def list_recovery_audit(self, owner_id: str, job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._reader() as db:
            rows = self._execute(db, """SELECT payload FROM cloud_local_recovery_audit
                WHERE owner_id=? AND job_id=? ORDER BY occurred_at LIMIT ?""",
                (owner_id, job_id, max(1, min(int(limit), 250)))).fetchall()
            return [self._payload(row) for row in rows]
