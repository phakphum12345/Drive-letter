# Research OS Cloud + Local — API and Execution Contract

**Document ID:** ROS-CL-02  
**Revision:** 1.0-draft  
**Status:** Proposed schema; implementation must be versioned separately  
**Date:** 2026-11-03  
**Baseline SHA:** `63e863b6823e26d044ac6a524503c795a4bc9165`

## 01. Contract objectives

Define a stable boundary between the shared Control Plane, Cloud workers and Local Agents. The contract must support:
- Explicit execution mode and capability requirements.
- Owner/tenant authorization and data classification.
- Durable assignment, lease ownership and idempotent retries.
- Checkpoint and evidence lineage.
- Agent enrollment, heartbeat, revocation and offline recovery.
- Backward-compatible schema evolution.

This is a design contract. No endpoint or schema in this document is claimed to exist in the current runtime.

## 02. Contract envelope

Every request/event should carry a common envelope:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `contract_version` | string | Yes | Version such as `1.0` |
| `request_id` | string | Yes | Unique request identifier |
| `correlation_id` | string | Yes | End-to-end trace identifier |
| `created_at` | RFC 3339 UTC | Yes | Creation time |
| `actor` | object | Yes | Authenticated user, service or agent identity |
| `owner_id` | string | Yes | Authorized data/ownership scope |
| `source_sha` | string | Conditional | Canonical source revision for code-bound work |

Do not trust `owner_id` merely because it appears in a payload. Derive and verify it against the authenticated principal and policy.

## 03. Job record

Proposed canonical job fields:

| Field | Type | Required | Rules |
|---|---|---:|---|
| `job_id` | opaque string | Yes | Server-generated, immutable |
| `owner_id` | string | Yes | Server-authorized owner scope |
| `execution_mode` | enum | Yes | `CLOUD`, `LOCAL`, `HYBRID`, `AUTO` |
| `status` | enum | Yes | State machine in section 04 |
| `task_type` | string | Yes | Allow-listed task identifier, never arbitrary shell text |
| `required_capabilities` | string[] | Yes | Minimum capabilities and versions |
| `data_classification` | enum | Yes | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `LOCAL_ONLY` |
| `assigned_worker_id` | string/null | No | Cloud worker or Local Agent identity |
| `stage_id` | string/null | No | Current stage in a hybrid workflow |
| `lease_id` | string/null | No | Current lease token; secret-like, never log raw |
| `lease_expires_at` | RFC 3339 UTC/null | No | Server-calculated expiry |
| `idempotency_key` | string | Yes | Stable across retries for the same logical side effect |
| `checkpoint_id` | string/null | No | Latest verified checkpoint |
| `source_sha` | string/null | Conditional | Required for source-dependent tasks |
| `input_refs` | object[] | Yes | References to authorized inputs; avoid embedding large/raw data |
| `output_refs` | object[] | Yes | Artifact/evidence references |
| `policy_decision_id` | string | Yes | Authorization decision used for dispatch |
| `created_at`, `updated_at` | timestamps | Yes | Server timestamps |
| `attempt` | integer | Yes | Monotonically increasing attempt counter |

### 03.1 Example (illustrative only)

```json
{
  "contract_version": "1.0",
  "job_id": "job_example",
  "owner_id": "owner_example",
  "execution_mode": "HYBRID",
  "status": "QUEUED",
  "task_type": "repository.audit",
  "required_capabilities": ["git.read", "python.test"],
  "data_classification": "INTERNAL",
  "assigned_worker_id": null,
  "stage_id": "stage_cloud_analysis",
  "lease_id": null,
  "lease_expires_at": null,
  "idempotency_key": "idem_example",
  "checkpoint_id": null,
  "source_sha": "0123456789abcdef0123456789abcdef01234567",
  "input_refs": [],
  "output_refs": [],
  "policy_decision_id": "policy_example",
  "attempt": 0
}
```

## 04. Job state machine

Proposed states:

| State | Meaning | Allowed next states |
|---|---|---|
| `QUEUED` | Validated and awaiting eligible execution | `ASSIGNED`, `CANCELLED`, `FAILED` |
| `ASSIGNED` | Worker/Agent selected; lease not yet confirmed | `RUNNING`, `QUEUED`, `WAITING_FOR_LOCAL_AGENT` |
| `RUNNING` | Current worker owns an active lease | `CHECKPOINTING`, `WAITING_FOR_LOCAL_AGENT`, `RETRY_WAIT`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `CHECKPOINTING` | Durable stage boundary is being committed | `RUNNING`, `RETRY_WAIT`, `FAILED` |
| `WAITING_FOR_LOCAL_AGENT` | A required local capability is unavailable | `ASSIGNED`, `CANCELLED`, `FAILED` |
| `RETRY_WAIT` | Retry scheduled after retryable failure/lease expiry | `QUEUED`, `FAILED`, `CANCELLED` |
| `COMPLETED` | All required stages and evidence are committed | Terminal |
| `FAILED` | Terminal failure or retry budget exhausted | Terminal; explicit replay creates a new attempt/job |
| `CANCELLED` | Cancelled by an authorized actor | Terminal |

A lease expiry does not itself prove that a worker stopped. Side effects must be protected by idempotency and/or fencing tokens.

## 05. Assignment and lease protocol

1. Worker/Agent authenticates and presents its registered identity and capabilities.
2. Control Plane evaluates owner scope, data classification, policy and capability match.
3. Control Plane assigns a job and creates a unique lease token with expiry.
4. Worker/Agent renews before expiry using compare-and-swap semantics.
5. Completion, failure and checkpoint commits require the current lease/fencing token.
6. If lease expires, Control Plane marks the attempt recoverable and may reassign only after policy checks.
7. A stale worker cannot commit output, acknowledge the job or overwrite a newer checkpoint.
8. Every retry uses the same logical idempotency key for the same external side effect.

Never treat a worker-provided timestamp as authoritative for lease validity; the server clock decides.

## 06. Local Agent lifecycle

Proposed lifecycle:

`UNENROLLED → ENROLLING → ACTIVE → DEGRADED → OFFLINE → REVOKED`

Agent registration includes:
- `agent_id`, owner binding and device identity.
- OS/runtime version and supported protocol versions.
- Capability names and versions.
- Last heartbeat and health status.
- Enrollment/revocation timestamps.
- Policy profile and permitted local resource scopes.

Security requirements:
- Enrollment code is single-use, short-lived and delivered through an authenticated owner flow.
- Agent obtains a device-bound credential and rotates it.
- Credentials are stored using an OS-protected secret facility, not plaintext config.
- Agent initiates outbound TLS connections; no public inbound Windows service port.
- Server can revoke a device immediately.
- Heartbeats contain health/capability metadata, not file contents or secrets.
- Assignment payloads are signed or protected by authenticated transport and are re-authorized before execution.

## 07. Proposed API surface

These are proposed route names, not existing endpoints:

| Method | Proposed route | Purpose |
|---|---|---|
| POST | `/api/v1/jobs` | Create a job after policy validation |
| GET | `/api/v1/jobs/{job_id}` | Read authorized job state |
| POST | `/api/v1/jobs/{job_id}/cancel` | Request authorized cancellation |
| POST | `/api/v1/agents/enroll` | Redeem a single-use enrollment grant |
| POST | `/api/v1/agents/heartbeat` | Update agent health/capabilities |
| POST | `/api/v1/agents/claim` | Claim an eligible local assignment |
| POST | `/api/v1/jobs/{job_id}/lease/renew` | Renew the active lease |
| POST | `/api/v1/jobs/{job_id}/checkpoint` | Commit a checkpoint |
| POST | `/api/v1/jobs/{job_id}/complete` | Commit completion and output refs |
| POST | `/api/v1/jobs/{job_id}/fail` | Report retryable or terminal failure |
| GET | `/api/v1/jobs/{job_id}/events` | Read authorized event history |

Exact route layout may change during implementation, but semantics and security invariants must not.

## 08. Checkpoint contract

Checkpoint fields should include:
- `checkpoint_id`, `job_id`, `owner_id`, `stage_id`.
- `source_sha` and contract/schema version.
- `workflow_state`, `next_action`, compact resumable state.
- `supersedes_checkpoint_id` for lineage.
- `evidence_refs[]` and artifact hashes.
- `created_at`, `created_by`, lease/fencing context.

Rules:
1. Checkpoint data is minimal resumable state, not hidden model reasoning or a raw transcript.
2. A checkpoint does not grant execution, approval or release authority.
3. A changed source SHA invalidates source-dependent resume until re-verification.
4. A superseded checkpoint cannot be resumed as the current state.
5. Checkpoint writes are atomic and owner-scoped.
6. A checkpoint must not contain bearer tokens, OAuth secrets or unredacted credentials.

The existing `platform_work_checkpoint.py` contract is a local JSON append/supersede implementation. The Cloud contract must preserve its safety semantics while adding transactional concurrency and shared persistence.

## 09. Evidence contract

Each evidence record should bind:
- `evidence_id`, `job_id`, `stage_id`, `owner_id`.
- Actor/worker/agent identity and current lease/fencing identifier (redacted or hashed where appropriate).
- Source SHA, policy decision ID and contract version.
- Event type, timestamp, result status and artifact hashes.
- Correlation ID and previous/next checkpoint references.

Evidence is append-only from the application perspective. Corrections create a linked event; they do not silently rewrite history. Retention, export and deletion policies must be defined before production.

## 10. Error model

| Code | Meaning | Retry? |
|---|---|---|
| `AUTHENTICATION_REQUIRED` | Missing/invalid principal | No, re-authenticate |
| `OWNER_SCOPE_DENIED` | Principal not authorized for owner | No |
| `POLICY_DENIED` | Capability or data policy rejected | No, policy change required |
| `CAPABILITY_UNAVAILABLE` | No eligible worker/Agent | Wait or reroute only if policy allows |
| `LEASE_EXPIRED` | Lease no longer current | Reclaim with new lease |
| `FENCING_TOKEN_STALE` | Old worker attempted commit | No commit; reconcile |
| `IDEMPOTENCY_CONFLICT` | Same key with different operation payload | No; investigate |
| `CHECKPOINT_STALE` | Source or checkpoint lineage changed | Re-verify |
| `ARTIFACT_INTEGRITY_FAILED` | Hash/size/type verification failed | Quarantine |
| `RETRY_BUDGET_EXHAUSTED` | Retry limit reached | Terminal |

Error responses must include a safe message and correlation ID, never secrets or raw local paths unless explicitly authorized.

## 11. Compatibility and versioning

- Use explicit contract versions and schema validation at ingress and egress.
- Add optional fields before making them required.
- Unknown enum values fail closed for execution.
- Older Agents may claim only jobs within their supported capability/protocol versions.
- Breaking changes require a new major contract version and a supported migration window.
- Maintain golden JSON fixtures and contract tests for Cloud and Local implementations.

## 12. Acceptance tests required before implementation is production-ready

- [ ] Owner A cannot read, claim, checkpoint or complete Owner B's job.
- [ ] A Local Agent cannot claim a Cloud-only or unsupported-capability job.
- [ ] A Cloud worker cannot claim a `LOCAL_ONLY` job.
- [ ] Offline Local Agent causes a safe wait, not silent Cloud fallback.
- [ ] Expired lease can be reclaimed and stale worker commits are rejected.
- [ ] Duplicate delivery does not repeat a side effect.
- [ ] Checkpoint resume rejects changed source SHA and superseded checkpoint.
- [ ] Agent revocation prevents new claims and lease renewals.
- [ ] Secrets and local file contents do not appear in logs/evidence by default.
- [ ] Restarting API/worker processes does not lose jobs, checkpoints or evidence.
- [ ] Contract fixtures pass across supported Agent/API versions.
