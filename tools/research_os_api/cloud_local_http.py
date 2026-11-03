"""Authenticated HTTP dispatch for the Research OS Cloud + Local v1 API."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

try:
    from .api_auth import require_session
    from .cloud_local_store import CloudLocalStore
except ImportError:  # pragma: no cover - direct server execution
    from api_auth import require_session
    from cloud_local_store import CloudLocalStore


_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_ROOT = _ROOT / "contracts" / "research_os" / "cloud_local" / "v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class CloudLocalHTTP:
    """Routes Cloud + Local API requests; identities always come from credentials."""

    def __init__(
        self,
        store: CloudLocalStore | None = None,
        session_resolver: Callable[[Any], dict[str, Any]] | None = None,
    ) -> None:
        self.store = store or CloudLocalStore()
        self.session_resolver = session_resolver or require_session
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError as exc:
            raise RuntimeError("Cloud + Local API requires contract-requirements.txt") from exc
        self._validators = {}
        for name in ("job", "agent", "evidence"):
            schema = json.loads((_SCHEMA_ROOT / f"{name}.schema.json").read_text(encoding="utf-8"))
            self._validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())

    def _validate(self, name: str, payload: dict[str, Any]) -> str | None:
        errors = sorted(self._validators[name].iter_errors(payload), key=lambda item: list(item.path))
        if not errors:
            return None
        error = errors[0]
        field = ".".join(str(part) for part in error.path) or "payload"
        return f"{field}: {error.message}"

    def _principal(self, headers: Any) -> dict[str, Any] | None:
        try:
            principal = self.session_resolver(headers)
        except (ValueError, RuntimeError):
            return None
        if not isinstance(principal, dict) or not str(principal.get("user_id") or "").strip():
            return None
        return principal

    def _agent(self, headers: Any) -> dict[str, Any] | None:
        authorization = str(headers.get("Authorization") or "").strip()
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            return None
        return self.store.authenticate_agent(token.strip())

    @staticmethod
    def _response(status: int, **payload: Any) -> tuple[int, dict[str, Any]]:
        return status, payload

    def dispatch(
        self,
        method: str,
        request_target: str,
        headers: Any,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        method = method.upper()
        path = urlsplit(request_target).path.rstrip("/") or "/"
        parts = [unquote(part) for part in path.split("/") if part]
        body = body or {}
        try:
            if method == "GET":
                return self._get(parts, urlsplit(request_target).query, headers)
            if method == "POST":
                return self._post(parts, headers, body)
            return self._response(405, error="method_not_allowed")
        except ValueError as exc:
            return self._response(400, error="bad_request", detail=str(exc))
        except Exception:
            # Do not leak SQL, filesystem paths, credentials or internal exceptions.
            return self._response(500, error="cloud_local_internal_error")

    def _get(self, parts: list[str], query: str, headers: Any) -> tuple[int, dict[str, Any]]:
        from urllib.parse import parse_qs
        params = parse_qs(query)
        principal = self._principal(headers)
        if principal is None:
            return self._response(401, error="authentication_required")
        owner_id = str(principal["user_id"])

        if parts == ["api", "v1", "jobs"]:
            limit = int(params.get("limit", ["50"])[0])
            jobs = self.store.list_jobs(owner_id, limit)
            return self._response(200, jobs=jobs, count=len(jobs))
        if parts == ["api", "v1", "agents"]:
            agents = self.store.list_agents(owner_id)
            return self._response(200, agents=agents, count=len(agents))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"]:
            job = self.store.get_job(owner_id, parts[3])
            return self._response(200, job=job) if job else self._response(404, error="job_not_found")
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "evidence":
            job_id = parts[3]
            if self.store.get_job(owner_id, job_id) is None:
                return self._response(404, error="job_not_found")
            evidence = self.store.list_evidence(owner_id, job_id)
            return self._response(200, evidence=evidence, count=len(evidence))
        return self._response(404, error="not_found")

    def _post(self, parts: list[str], headers: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if parts == ["api", "v1", "agents", "enroll"]:
            return self._enroll(body)
        if parts == ["api", "v1", "agents", "heartbeat"]:
            return self._heartbeat(headers, body)
        if parts == ["api", "v1", "agents", "claim"]:
            return self._claim(headers, body)
        if parts == ["api", "v1", "evidence"]:
            return self._append_evidence(headers, body)
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "transition":
            return self._agent_job_action(headers, body, parts[3], "transition")
        if len(parts) == 6 and parts[:3] == ["api", "v1", "jobs"] and parts[4:] == ["lease", "renew"]:
            return self._agent_job_action(headers, body, parts[3], "lease")

        principal = self._principal(headers)
        if principal is None:
            return self._response(401, error="authentication_required")
        owner_id = str(principal["user_id"])

        if parts == ["api", "v1", "agents", "enrollment-grants"]:
            ttl = int(body.get("ttl_seconds", 600))
            token = self.store.create_enrollment_grant(owner_id, ttl)
            return self._response(201, enrollment_token=token, expires_in_seconds=max(60, min(ttl, 3600)),
                                  owner_id=owner_id, single_use=True)
        if parts == ["api", "v1", "jobs"]:
            return self._create_job(owner_id, body)
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            job = self.store.cancel_job(owner_id, parts[3])
            return self._response(200, job=job) if job else self._response(404, error="job_not_found")
        if len(parts) == 5 and parts[:3] == ["api", "v1", "agents"] and parts[4] == "revoke":
            revoked = self.store.revoke_agent(owner_id, parts[3])
            return self._response(200, revoked=True) if revoked else self._response(404, error="agent_not_found")

        # Agent-only routes must never fall through to user-session authorization.
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] in {"lease", "transition"}:
            return self._response(404, error="not_found")
        return self._response(404, error="not_found")

    def _create_job(self, owner_id: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        mode = str(body.get("execution_mode") or "").upper()
        classification = str(body.get("data_classification") or "").upper()
        input_refs = body.get("input_refs", [])
        if not isinstance(input_refs, list):
            raise ValueError("input_refs must be an array")
        if mode not in {"CLOUD", "LOCAL", "HYBRID", "AUTO"}:
            raise ValueError("execution_mode is invalid")
        classifications = {classification}
        classifications.update(
            str(ref.get("data_classification") or "").upper()
            for ref in input_refs if isinstance(ref, dict) and ref.get("data_classification")
        )
        contains_local = "LOCAL_ONLY" in classifications
        if contains_local and mode not in {"LOCAL", "HYBRID"}:
            return self._response(403, error="locality_policy_denied",
                                  policy="cloud-local.local-only.v1",
                                  detail="LOCAL_ONLY data may only use LOCAL or HYBRID execution.")
        if mode in {"CLOUD", "HYBRID", "AUTO"} and any(
            value in {"INTERNAL", "CONFIDENTIAL"} for value in classifications
        ):
            return self._response(403, error="cloud_data_consent_required",
                                  policy="cloud-local.cloud-consent.v1",
                                  detail="Cloud stages are disabled for INTERNAL or CONFIDENTIAL data until an explicit upload-consent policy is implemented.")
        policy_id = "pd-" + uuid.uuid4().hex
        now = _now()
        payload = {
            "contract_version": "1.0",
            "request_id": "req-" + uuid.uuid4().hex,
            "correlation_id": str(body.get("correlation_id") or "corr-" + uuid.uuid4().hex),
            "created_at": now,
            "updated_at": now,
            "actor": {"principal_type": "user", "principal_id": owner_id},
            "owner_id": owner_id,
            "job_id": "job-" + uuid.uuid4().hex,
            "execution_mode": mode,
            "status": "WAITING_FOR_LOCAL_AGENT" if mode in {"LOCAL", "HYBRID"} else "QUEUED",
            "task_type": str(body.get("task_type") or "").strip(),
            "required_capabilities": body.get("required_capabilities", []),
            "data_classification": classification,
            "idempotency_key": str(body.get("idempotency_key") or "").strip(),
            "input_refs": input_refs,
            "output_refs": [],
            "policy_decision_id": policy_id,
            "attempt": 0,
        }
        for optional in ("source_sha", "stage_id"):
            if body.get(optional) is not None:
                payload[optional] = body[optional]
        error = self._validate("job", payload)
        if error:
            raise ValueError(error)
        job, replay = self.store.create_job(payload)
        return self._response(200 if replay else 201, job=job, idempotent_replay=replay)

    def _enroll(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        grant = str(body.get("enrollment_token") or "").strip()
        owner_id = self.store.enrollment_grant_owner(grant) if grant else None
        if not owner_id:
            return self._response(401, error="enrollment_grant_invalid_or_expired")
        agent, token = self.store.enroll_agent(
            grant, owner_id=owner_id, device_id=str(body.get("device_id") or "").strip(),
            protocol_versions=body.get("protocol_versions") or [],
            capabilities=body.get("capabilities") or [],
            os_name=str(body.get("os_name") or "").strip(),
            os_version=str(body.get("os_version") or ""),
            agent_version=str(body.get("agent_version") or "").strip(),
        )
        error = self._validate("agent", agent)
        if error:
            self.store.revoke_agent(owner_id, agent["agent_id"])
            raise ValueError(error)
        return self._response(201, agent=agent, agent_token=token, token_delivery="one_time")

    def _heartbeat(self, headers: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        identity = self._agent(headers)
        if identity is None:
            return self._response(401, error="agent_authentication_required")
        capabilities = body.get("capabilities")
        if capabilities is not None and not isinstance(capabilities, list):
            raise ValueError("capabilities must be an array")
        candidate = dict(identity["agent"])
        if capabilities is not None:
            candidate["capabilities"] = capabilities
        candidate.update(lifecycle_state="ACTIVE", last_heartbeat_at=_now())
        error = self._validate("agent", candidate)
        if error:
            raise ValueError(error)
        agent = self.store.heartbeat_agent(identity["owner_id"], identity["agent_id"], capabilities)
        if agent is None:
            return self._response(401, error="agent_revoked")
        return self._response(200, agent=agent)

    def _claim(self, headers: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        identity = self._agent(headers)
        if identity is None:
            return self._response(401, error="agent_authentication_required")
        job = self.store.claim_local_job(identity["owner_id"], identity["agent_id"],
                                         int(body.get("lease_seconds", 60)))
        return self._response(200, job=job)

    def _append_evidence(self, headers: Any, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        identity = self._agent(headers)
        if identity is None:
            return self._response(401, error="agent_authentication_required")
        owner_id = identity["owner_id"]
        job_id = str(body.get("job_id") or "").strip()
        job = self.store.get_job(owner_id, job_id)
        if job is None:
            return self._response(404, error="job_not_found")
        payload = {
            "contract_version": "1.0",
            "evidence_id": "ev-" + uuid.uuid4().hex,
            "job_id": job_id,
            "owner_id": owner_id,
            "stage_id": str(body.get("stage_id") or job.get("stage_id") or "").strip(),
            "actor_id": identity["agent_id"],
            "event_type": str(body.get("event_type") or "").strip(),
            "occurred_at": _now(),
            "result": str(body.get("result") or "INFO").upper(),
            "source_sha": str(body.get("source_sha") or job.get("source_sha") or "").strip(),
            "policy_decision_id": job["policy_decision_id"],
            "correlation_id": job["correlation_id"],
        }
        for optional in ("lease_fingerprint", "artifact_hashes", "previous_evidence_id"):
            if body.get(optional) is not None:
                payload[optional] = body[optional]
        error = self._validate("evidence", payload)
        if error:
            raise ValueError(error)
        self.store.append_evidence(owner_id, payload)
        return self._response(201, evidence=payload)

    def _agent_job_action(self, headers: Any, body: dict[str, Any], job_id: str,
                          action: str) -> tuple[int, dict[str, Any]]:
        identity = self._agent(headers)
        if identity is None:
            return self._response(401, error="agent_authentication_required")
        owner_id, agent_id = identity["owner_id"], identity["agent_id"]
        lease = str(body.get("lease_token") or "").strip()
        if action == "lease":
            job = self.store.renew_lease(owner_id, agent_id, job_id, lease,
                                         int(body.get("lease_seconds", 60)))
        else:
            current = self.store.get_job(owner_id, job_id)
            if current is None:
                return self._response(404, error="job_not_found")
            candidate = dict(current)
            candidate["status"] = str(body.get("status") or "").upper()
            candidate["updated_at"] = _now()
            if body.get("output_refs") is not None:
                candidate["output_refs"] = body["output_refs"]
            if body.get("checkpoint_id") is not None:
                candidate["checkpoint_id"] = body["checkpoint_id"]
            if candidate["status"] in {"COMPLETED", "FAILED"}:
                candidate["lease_id"] = None
                candidate["lease_expires_at"] = None
            error = self._validate("job", candidate)
            if error:
                raise ValueError(error)
            job = self.store.transition_job(
                owner_id, agent_id, job_id, lease, candidate["status"],
                output_refs=candidate.get("output_refs"), checkpoint_id=candidate.get("checkpoint_id"),
            )
        return self._response(200, job=job) if job else self._response(409, error="lease_invalid_or_expired")

