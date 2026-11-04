"""Evidence lookup routing and provenance-preserving recovery helpers."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def _sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) in (40, 64) and all(ch in "0123456789abcdefABCDEF" for ch in text)


def resolve_evidence(records: list[dict[str, Any]], *, owner_id: str, job_id: str,
                     stage_id: str, event_type: str, source_sha: str) -> dict[str, Any]:
    """Prefer exact original, then verified same-stage evidence; never cross owner/job/SHA."""
    scoped = [item for item in records if item.get("owner_id") == owner_id
              and item.get("job_id") == job_id and item.get("stage_id") == stage_id
              and item.get("source_sha") == source_sha and _sha(item.get("source_sha"))]
    exact = next((item for item in scoped if item.get("event_type") == event_type
                  and item.get("evidence_class", "ORIGINAL") == "ORIGINAL"), None)
    if exact:
        return {"status": "FOUND", "route": "PRIMARY", "evidence": exact}
    fallback = next((item for item in reversed(scoped)
                     if (item.get("event_type") == event_type or item.get("recovered_event_type") == event_type)
                     and item.get("evidence_class") in {"REPLICA", "RECOVERED"}), None)
    if fallback:
        return {"status": "FOUND", "route": "FALLBACK", "evidence": fallback}
    related = [item for item in scoped if item.get("event_type") != event_type]
    if related:
        return {"status": "PARTIAL", "route": "RELATED_EVIDENCE",
                "evidence": related[-1], "missing_event_type": event_type}
    return {"status": "MISSING", "route": "EXHAUSTED", "evidence": None}


def build_recovered_evidence(*, job: dict[str, Any], checkpoints: list[dict[str, Any]],
                             evidence: list[dict[str, Any]], owner_id: str, stage_id: str,
                             event_type: str, checkpoint: dict[str, Any] | None,
                             actor_id: str) -> dict[str, Any] | None:
    """Build an explicitly RECOVERED record only from verified same-owner/job/SHA sources."""
    source_sha = str(job.get("source_sha") or "")
    if job.get("owner_id") != owner_id or not _sha(source_sha) or not stage_id or not event_type:
        return None
    valid_evidence = [item for item in evidence if item.get("owner_id") == owner_id
                      and item.get("job_id") == job.get("job_id")
                      and item.get("source_sha") == source_sha and _sha(item.get("source_sha"))
                      and item.get("evidence_class", "ORIGINAL") == "ORIGINAL"]
    valid_checkpoints = [item for item in checkpoints if item.get("owner_id") == owner_id
                         and item.get("job_id") == job.get("job_id")
                         and item.get("source_sha") == source_sha and _sha(item.get("source_sha"))]
    if checkpoint is not None and checkpoint not in valid_checkpoints:
        return None
    stage_evidence = [item for item in valid_evidence if item.get("stage_id") == stage_id]
    stage_checkpoints = [item for item in valid_checkpoints if item.get("stage_id") == stage_id]
    if checkpoint is None and not stage_evidence and not stage_checkpoints:
        return None
    sources = sorted({str(item.get("evidence_id")) for item in stage_evidence}
                     | {str(item.get("checkpoint_id")) for item in stage_checkpoints})
    if not sources:
        return None
    key_material = {"owner_id": owner_id, "job_id": job["job_id"], "stage_id": stage_id,
                    "event_type": event_type, "source_sha": source_sha, "sources": sources}
    recovery_key = hashlib.sha256(json.dumps(key_material, sort_keys=True).encode()).hexdigest()
    hashes = sorted({value for item in stage_checkpoints for value in item.get("artifact_hashes", [])})
    previous = stage_evidence[-1].get("evidence_id") if stage_evidence else None
    return {
        "contract_version": "1.0", "evidence_id": "ev-rec-" + uuid.uuid4().hex,
        "job_id": job["job_id"], "owner_id": owner_id, "stage_id": stage_id,
        "actor_id": actor_id, "event_type": "evidence.recovered",
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "result": "INFO", "source_sha": source_sha,
        "policy_decision_id": job["policy_decision_id"], "correlation_id": job["correlation_id"],
        "artifact_hashes": hashes, "previous_evidence_id": previous,
        "evidence_class": "RECOVERED", "recovered_event_type": event_type,
        "recovery_sources": sources,
        "recovery_reason": "requested evidence route was missing; reconstructed from verified same-job checkpoint/evidence metadata",
        "recovery_key": recovery_key,
    }
