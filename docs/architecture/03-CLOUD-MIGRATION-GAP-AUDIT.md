# Research OS Cloud Migration — Current-State Gap Audit

**Document ID:** ROS-CL-03  
**Revision:** 1.0-draft  
**Status:** Source-backed initial audit; implementation verification still required  
**Audit date:** 2026-11-03  
**Repository:** `phakphum12345/Drive-letter`  
**Audited baseline:** `main` at `63e863b6823e26d044ac6a524503c795a4bc9165`

## 01. Executive summary

The repository already contains meaningful building blocks for a hybrid architecture: a Python API, Windows ServiceHost, Owner Friend runtime, checkpoint contract, SQLite lease-based task queue, event delivery and crash-recovery tests.

However, the current implementation is **local-first and filesystem-backed in several critical paths**. The existing Dockerfile is not the production API image. The current queue uses SQLite, and local JSON/JSONL stores cannot be assumed safe for multi-replica cloud execution. No Azure production deployment was verified in the audited source.

**Conclusion:** proceed with architecture and contract review first. Do not deploy the current Dockerfile as the production API, scale the SQLite queue across replicas, or migrate local data until the gaps below are closed.

## 02. Audit scope and method

Reviewed source files on the baseline commit. This is a static source audit, not a live deployment, penetration test, load test, restore drill or runtime migration.

| Area | Files reviewed |
|---|---|
| Container | `research-os/Dockerfile`, `research-os/requirements.txt` |
| API and identity | `tools/research_os_api/server.py`, `auth_session.py`, `identity_storage.py` |
| OAuth and conversations | `google_oauth.py`, `google_workspace.py`, `conversation_store.py`, `local_storage.py` |
| Checkpoints | `tools/platform_work_checkpoint.py`, `current/PLATFORM_WORK_CHECKPOINT_CONTRACT.json` |
| Queue and event delivery | `v3/research_os_v3/queue.py`, `event_delivery.py`, `v3/tests/test_worker_crash_recovery.py` |
| Worker guidance | `docs/RESEARCH_OS_WORKER_POOL.md` |
| Owner Friend | `owner_special/research_os_friend/runtime.py`, `orchestrator.py`, `models.py`, `memory.py`, `evidence.py`, `approval.py` |
| Windows service | `tools/research_os_service/Program.cs` |
| Artifact workflow | `.github/workflows/artifacts-build.yml` |

## 03. Verified current-state findings

### 03.1 API container is not the production API container

**Evidence:** `research-os/Dockerfile` copies `app` and `service`, then runs `python app/main.py`. It does not copy or invoke `tools/research_os_api/server.py`.

The dependency installation command ends with `|| true`, which allows the image build to continue even if dependency installation fails.

**Gap:** create a dedicated, reproducible production API image with pinned dependencies, failure-fast build, non-root runtime, health checks and externalized durable state.

**Risk:** a successful image build could be mistaken for proof that the actual API is packaged and operational.

### 03.2 API-to-Friend endpoint is currently a local loopback dependency on baseline

**Evidence:** baseline `tools/research_os_api/server.py` defaults `RESEARCH_OS_FRIEND_URL` to `http://127.0.0.1:0`. The Windows ServiceHost and Owner Friend service are separate processes.

**Related PR:** PR #65 proposes setting the installed Friend endpoint to `http://127.0.0.1:8790` through ServiceHost and installer environment. At audit time PR #65 is open and unmerged; its changes are not part of this baseline.

**Gap:** settle the local service endpoint contract and add health/readiness checks before packaging the Local Agent. Cloud services must never reuse a machine-local loopback address.

**Risk:** local Friend calls fail if the endpoint is not configured; remote Cloud cannot reach a user's loopback service.

### 03.3 Durable task queue is SQLite-backed

**Evidence:** `v3/research_os_v3/queue.py` opens a SQLite database, creates queue/outbox tables, uses `BEGIN IMMEDIATE`, lease IDs and lease expiry. `event_delivery.py` also persists events/deliveries in SQLite and uses lease ownership.

**Positive existing controls:** `v3/tests/test_worker_crash_recovery.py` verifies expired lease reclaim and rejection of stale worker acknowledgement.

**Gap:** SQLite is not approved as the shared multi-replica Cloud queue. Select and test a transactional shared database or managed broker; preserve lease fencing, outbox, idempotency and recovery semantics.

**Risk:** placing one SQLite file on ephemeral or shared container storage can cause data loss, locking contention or unsupported concurrency behavior.

### 03.4 Checkpoint storage is local JSON

**Evidence:** `tools/platform_work_checkpoint.py` writes `RESEARCH_OS_DATA_DIR/platform/work_checkpoints.json` using JSON file read/write and temporary-file replacement. The contract in `current/PLATFORM_WORK_CHECKPOINT_CONTRACT.json` states that checkpoints do not grant release authority and that changed canonical SHA invalidates resume.

**Positive existing controls:** owner-scoped lookup, checkpoint lineage/supersede checks, source SHA validation and evidence references are present.

**Gap:** migrate checkpoint metadata to transactional durable storage only after schema mapping and parity tests. Preserve all current authorization and invalidation rules.

**Risk:** concurrent writers and multi-replica processes are not proven safe by a local JSON file.

### 03.5 Sessions, OAuth and conversations have filesystem persistence

**Evidence:**
- `auth_session.py` persists revocation markers under a configured data directory.
- `google_oauth.py` writes `oauth_state.json` and `oauth_token.json` under the Google Workspace data root.
- `conversation_store.py` reads and writes a JSON conversation store.
- `tools/research_os_service/Program.cs` configures a Windows data directory and conversation-store path.

**Gap:** define cloud session/revocation semantics, owner-scoped OAuth credential storage, encryption/key rotation, atomic updates, multi-instance consistency and import/export behavior.

**Risk:** ephemeral containers can lose state; multiple replicas can observe inconsistent revocation or overwrite file-backed records. OAuth tokens are sensitive and must not be copied into logs or ordinary artifacts.

### 03.6 Owner Friend runtime persists several owner-scoped stores

**Evidence:** `owner_special/research_os_friend/runtime.py` creates owner-scoped persistent memory, evidence JSONL, learning records, agent traces, approval records and preview storage under the configured data root.

**Positive existing controls:** `orchestrator.py` authorizes requests and selected tools; approval is enforced for explicitly requested side-effecting tools; memory is scoped by owner/profile/session.

**Gap:** inventory every persistent store and classify it as local-only, cloud-eligible metadata, or transferable artifact. Define transactionality, concurrency, encryption, retention and owner isolation for each.

**Risk:** moving the Friend runtime to Cloud without a full store inventory could leak local context or lose approvals/evidence/memory.

### 03.7 Worker guidance already expects durable ownership

**Evidence:** `docs/RESEARCH_OS_WORKER_POOL.md` states that workers are stateless and durable ownership lives in delivery leases; failed handlers leave work recoverable after lease expiry.

**Gap:** reconcile that worker model with the actual deployment/storage substrate and prove behavior with multi-worker tests.

### 03.8 Artifact workflow supports local and Render endpoint profiles only

**Evidence:** `.github/workflows/artifacts-build.yml` offers `local` and `render` deployment modes and compiles an API base URL into web/Windows artifacts. The workflow is an artifact build workflow; it is not evidence of Azure deployment.

**Gap:** add a separate, reviewed deployment workflow only after target infrastructure and secrets model are approved. Do not put credentials into build-time Dart defines or public frontend bundles.

## 04. Migration gap register

| ID | Gap | Severity | Required action | Exit evidence |
|---|---|---|---|---|
| G-01 | Production API image not represented by current Dockerfile | Critical | Build image from actual API entrypoint | Container smoke test + health/readiness |
| G-02 | Dependency install ignores failure | High | Pin and fail-fast dependencies | Reproducible clean build |
| G-03 | Local Friend loopback dependency | High | Separate Local Agent/Friend boundary | Local endpoint tests; no Cloud loopback assumption |
| G-04 | SQLite queue/event store not approved for multi-replica Cloud | Critical | Choose shared durable transactional backend | Concurrent claim/lease/fencing/recovery tests |
| G-05 | Checkpoint JSON file not concurrency-safe for shared Cloud use | High | Define transactional checkpoint repository | Concurrent writes, lineage and SHA tests |
| G-06 | File-backed session revocation | Critical | Centralize authoritative session/revocation state | Cross-replica revocation tests |
| G-07 | OAuth state/token JSON persistence | Critical | Secure owner-scoped credential vault | Encryption, rotation, callback and revoke tests |
| G-08 | Conversation JSON store | High | Define canonical store and sync conflict model | Multi-device consistency tests |
| G-09 | Friend memory/evidence/learning/approval/trace/preview stores | High | Full store inventory and placement decision | Store-by-store migration and restore tests |
| G-10 | No verified Azure deployment workflow/resources | High | Approve infrastructure and deployment plan | IaC review, identity and deployment evidence |
| G-11 | Local Agent enrollment/revocation protocol not established in this audit | High | Define device identity and outbound channel | Enrollment, revoke, offline and reconnect tests |
| G-12 | Cloud/local data classification and upload consent not finalized | Critical | Define policy and owner consent | Negative tests proving LOCAL_ONLY data stays local |
| G-13 | Backup/restore and RPO/RTO not specified | High | Define and rehearse recovery objectives | Restore drill and measured results |
| G-14 | Observability/correlation across Cloud and Local | Medium | Standardize correlation IDs and safe telemetry | Trace from UI through worker/Agent and evidence |

## 05. Data impact and preservation matrix

| Existing data | Proposed treatment | Migration allowed now? | Preservation requirement |
|---|---|---:|---|
| Windows ProgramData / Research OS data root | Keep local during initial rollout | No | Backup before any future migration; never delete as part of deployment |
| Owner Friend memory | Keep local until classification and consent are approved | No | Owner/profile/session scope preserved |
| Friend evidence JSONL | Keep local; later export as verified append-only records if approved | No | Hash and record count before/after |
| Approval records | Keep local until a secure authoritative store is ready | No | Never drop pending/denied/approved decision history |
| OAuth state and tokens | Keep in current protected local store until credential-vault migration is designed | No | Never expose token contents; support revoke/rotation |
| Session revocation markers | Preserve current markers; centralize only with parity tests | No | A revoked session must remain revoked after cutover |
| Conversations | Preserve local source and define conflict/sync rules | No | No overwrite or merge without reconciliation |
| Platform checkpoints | Preserve source JSON and lineage | No | Validate SHA, supersede links and evidence refs |
| SQLite queue and event DB | Keep local database untouched during design phase | No | Backup and test replay/restore before any conversion |
| Local files and generated artifacts | Remain local unless explicit job policy permits transfer | No | No silent upload |

**Rule:** migration must be additive and reversible. The source remains intact until destination parity, restore and rollback are verified and an authorized cutover is approved.

## 06. Required design decisions before implementation

1. Cloud provider subscription/tenant, region and data residency.
2. Monthly budget ceiling, workload volume, concurrency and latency targets.
3. Canonical identity provider and cross-device device identity model.
4. Managed relational database and queue/messaging selection.
5. Owner-scoped OAuth credential vault and token lifecycle.
6. Data classification and exact local-to-cloud transfer consent.
7. Local Agent enrollment, credential rotation and revocation.
8. Artifact retention, evidence retention and deletion/legal requirements.
9. RPO/RTO, backup schedule and restore authority.
10. Whether Render is temporary, remains as an environment, or is retired.

## 07. Proposed PR sequence and acceptance criteria

| Order | PR scope | Must include | Acceptance criteria |
|---:|---|---|---|
| 00 | This architecture documentation | Numbered docs and evidence references | Reviewers can identify current facts, proposals and unknowns |
| 01 | Contract schemas and compatibility tests | Job/Agent/lease/checkpoint/evidence schemas | Golden fixtures, schema validation, owner-isolation tests |
| 02 | Production API container | Actual API entrypoint, pinned dependencies, non-root, health | Build and run smoke test; no dependency failure suppression |
| 03 | Cloud foundation as reviewed IaC | Network, identity, database, object store, secrets, monitoring | Plan review, least privilege, budget and backup checks |
| 04 | Durable Cloud job store and router | Transactional state, idempotency, lease fencing | Multi-worker claim/reclaim/restart tests |
| 05 | Local Agent service | Outbound channel, enrollment, heartbeat, revocation | No inbound public port; offline/reconnect tests |
| 06 | Hybrid workflow orchestration | Stage transitions and checkpoint handoff | Cloud continues when PC off; Local stage waits safely |
| 07 | Store migration (only when necessary) | Per-store migration scripts and parity reports | Source preserved, counts/hashes match, rollback rehearsal |
| 08 | Security and production release | Threat model, penetration checks, SLO, restore drill | All required gates green and explicit release approval |

## 08. Verification plan

Before implementation:
- [ ] Re-run source audit on the PR base SHA and update references if main has moved.
- [ ] Confirm exact data roots for every persistent store and installer edition.
- [ ] Inspect all queue constructors/call sites and current database locations.
- [ ] Inspect API auth/session routes and OAuth callback handling end-to-end.
- [ ] Inventory all Friend stores, preview data and local tool capabilities.
- [ ] Confirm whether any existing Render environment currently stores production data.
- [ ] Define backup/restore procedure for every persistent store.

During implementation:
- [ ] Unit and contract tests.
- [ ] Cross-owner authorization tests.
- [ ] Concurrent multi-worker tests.
- [ ] Lease expiry, stale worker and duplicate delivery tests.
- [ ] Cloud container restart and database failover tests.
- [ ] Local Agent offline/reconnect/revocation tests.
- [ ] Data export/import parity and rollback tests.
- [ ] Security scan, secret scan, SBOM and dependency review.

## 09. Open PR #65 dependency note

PR #65 (`fix/research-os-friend-service-url`) is separate from this documentation change. Its purpose is to correct the installed Windows API-to-Friend endpoint. At the time of this audit it was open and unmerged, so the baseline finding in section 03.2 remains accurate. Re-check its live CI and review status before merging; do not treat its proposed fix as already deployed.

## 10. Audit limitations

- Static source inspection only; no production database, cloud subscription or Windows installation was accessed.
- No Azure resource inventory or billing data was available.
- No live API, Local Agent, Owner Friend or Render environment was exercised.
- No concurrency/load/penetration/backup-restore test was run for this audit.
- File list is a focused audit, not proof that every persistent store in the repository has been found.

## 11. Audit disposition

**Disposition: HOLD implementation pending architecture review and closure of Critical gaps G-01, G-04, G-06, G-07 and G-12.**

Documentation can be reviewed now. Runtime changes, Azure provisioning, multi-replica deployment and data migration require separate approved PRs and evidence.
