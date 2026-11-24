# Friend Cloud Memory Durability — Design and Safe Cutover

**Status:** Proposal only; no infrastructure change or data cutover is authorized or applied  
**Repository:** `phakphum12345/Drive-letter`  
**Service:** `research-os-api-phakphoum`  
**Scope:** Owner Friend filesystem-backed stores only  
**Evidence review date:** 2026-11-24

## 1. Decision and boundaries

Friend's current source code supports filesystem-backed owner stores when `RESEARCH_OS_OWNER_DATA_ROOT` (or its fallback) is supplied. That is a local-filesystem persistence mechanism, not proof of durable storage on Render.

The proposed target is a persistent disk mounted at `/var/data`, with `RESEARCH_OS_OWNER_DATA_ROOT=/var/data`, attached to the existing API service after an independently verified export/restore. This is a single-instance design, not a multi-replica storage solution.

This document is a design proposal only. It does not create a disk, change a plan or environment variable, deploy or restart a service, migrate/copy/delete data, or change billing. The current live service is on the Free plan, so the proposed disk cannot be attached without a separately approved paid-plan change.

## 2. What the repository proves

### 2.1 Blueprint configuration (`render.yaml`)

At the reviewed PR base, `render.yaml` declares:

- Web service `research-os-api-phakphoum`, linked to branch `main`
- `plan: free`
- `autoDeploy: true`
- No `disk:` stanza
- No declared `RESEARCH_OS_OWNER_DATA_ROOT` or `RESEARCH_OS_DATA_DIR` variable

This is repository blueprint evidence only. It does not, by itself, establish the live service's plan, attached disks, manually configured environment variables, or deployed revision.

### 2.2 Read-only live Render observation (2026-11-24)

A read-only Render service lookup returned the following for the existing service:

- Compute `plan: free`
- `numInstances: 1`
- Linked branch `main`
- `autoDeploy: yes`
- Region `oregon`
- Public service URL `https://research-os-api-phakphoum-v0wf.onrender.com`

The API also returned a separate `buildPlan: starter` field. That is not the service's compute `plan`; the compute plan returned by the same response is `free`.

The service event history queried from its creation date (2026-10-06) through this review contained no `disk_created`, `disk_updated`, `disk_deleted`, or `disk_snapshot_restored` event. The service-detail response does not expose a direct disk-mount field, so this is recorded as event-history evidence rather than a direct disk inventory. Render's current documentation says persistent disks are available only to paid services; the observed Free compute plan is therefore incompatible with the proposed disk.

The read-only service response did not expose environment-variable values. The live value of `RESEARCH_OS_OWNER_DATA_ROOT` is consequently **not verified** by this review. No secret values were requested or read. Do not infer a live environment override from `render.yaml`.

## 3. Current source-backed Friend data-root behavior

`tools/research_os_api/render_server.py` resolves the Friend data root in this order:

1. `RESEARCH_OS_OWNER_DATA_ROOT`
2. `RESEARCH_OS_DATA_DIR`
3. `Path.home() / ".research_os_owner_special"`

The resolved root is passed to `OwnerFriendService`, which creates the Friend runtime with that data root. If neither environment variable is set, the third path is used. Render documents that the service filesystem is ephemeral unless a persistent disk is attached; therefore the fallback path must not be described as durable across Render restarts or deploys.

When `FriendRuntime.create_owner_special` receives a data root, the current stores are laid out as follows:

| Store | Source-defined location under the data root | Scope evidenced by source |
|---|---|---|
| Memory | `owners/<owner>/memory/memory.json` | Each item carries owner, profile, and session IDs; recall filters on all three |
| Schedule previews | `owners/<owner>/schedule_previews/<profile>/<session>/<preview>.json` | Path and loaded record are checked against owner, profile, session, and preview ID |
| Evidence | `owners/<owner>/evidence/events.jsonl` | Appended records carry owner, profile, and session IDs; token-like values are redacted before writing |
| Learning | `owners/<owner>/learning/learning.json` | Records carry owner ID; reusable-record lookup filters by owner |
| Agent traces | `owners/<owner>/agent/traces.json` | Owner-root file; runs carry owner/profile/session metadata and list/get APIs enforce owner scope |
| Approvals | `owners/<owner>/agent/approvals.json` | Owner-root file; records include owner/profile/session IDs and approval state |

The JSON stores use temporary-file replacement for writes; the evidence store appends JSONL records. These are application-level filesystem behaviors, not a guarantee against loss of an ephemeral instance filesystem.

The existing `owner_special/tests/test_friend_persistence.py` test proves that Friend memory survives recreating a runtime with the same local temporary directory and separately tests memory isolation between two owners. It does **not** prove survival across Render instance replacement, prove that every store has a tested export/restore path, or prove that the current live Render service is using a particular environment override.

## 4. Separate Research OS artifact-memory path

The `/v1/memory/commit` endpoint is not the Friend filesystem store:

- It requires explicit `confirm: true` and the API sync-key authorization.
- It writes curated Markdown research artifacts under `ROOT/research/artifacts` and updates that artifact index.
- The endpoint returns `durability: "runtime-ephemeral"` and explicitly notes that the Render Free-service filesystem is ephemeral.

Changing `RESEARCH_OS_OWNER_DATA_ROOT` for Friend does not move `ROOT/research/artifacts` onto the Friend data root or make this separate artifact path durable. This proposal does not change that endpoint or its storage contract.

## 5. Proposed Render configuration (not applied)

Only after backup/export and restore verification, the proposed configuration for the **existing** service is:

```yaml
plan: 0.5c-512mb
disk:
  name: friend-owner-data
  mountPath: /var/data
  sizeGB: 1
envVars:
  - key: RESEARCH_OS_OWNER_DATA_ROOT
    value: /var/data
```

The 1 GB size is a planning assumption, not a measured capacity requirement. Measure the current store tree and its growth before choosing capacity. Attach the disk to the existing API service; do not create a second API service or database.

The current Render Blueprint reference identifies the smallest paid web-service tier as plan ID `0.5c-512mb` (0.5 CPU, 512 MB); use that current ID rather than the older `starter` label in a future Blueprint. The plan change from the observed Free compute plan to this paid plan and the disk attachment are separate infrastructure/billing changes. Neither is authorized by this document or by merging this documentation PR.

## 6. Cost estimate — re-check before any approval

Render's pricing page, checked on 2026-11-24, lists the smallest paid web-service compute tier (less than 1 CPU, 512 MB RAM) at **$7/month** and SSD storage at **$0.25 per GB per month**. If a 1 GB disk is ultimately selected, the planning estimate is therefore **about $7.25/month for compute plus disk**.

This is not a quote or a statement of the current bill. It excludes bandwidth, any workspace-level subscription (if applicable), additional usage, taxes, and any future pricing change. Render bills compute per service and prorates it by time. Confirm the exact plan, disk size, workspace plan, and final monthly estimate in the Render Dashboard immediately before any approval.

Sources: [Render pricing](https://render.com/pricing), [Render Blueprint YAML reference](https://render.com/docs/blueprint-spec), [Render persistent disks](https://render.com/docs/disks), and [Render deploys / skip phrases](https://render.com/docs/deploys).

## 7. Operational constraints from current Render documentation

Render's persistent-disk documentation states:

- Only filesystem changes beneath the disk's mount path are preserved; the rest of the service filesystem remains ephemeral.
- A persistent disk is accessible to one service instance only; a service with a disk cannot be horizontally scaled to multiple instances.
- A disk is available at runtime, not to the build command, pre-deploy command, or one-off jobs.
- Adding a disk disables zero-downtime deploys. Render stops the old instance before starting the replacement; the instance swap causes an interruption of a few seconds.
- Render creates an automatic snapshot every 24 hours; snapshots are available for seven days.
- Restoring a snapshot restores the whole disk. Changes made after that snapshot are lost, and partial snapshot restores are not supported.

Snapshots are a recovery aid, not a substitute for an owner-authorized export, an independently verified restore, or a tested application-level backup. A snapshot restore can roll back newer data.

The existing service is observed as a single instance today. The proposed disk keeps that constraint; it does not provide horizontal scaling or multi-instance consistency.

## 8. Mandatory data-preserving cutover sequence

No Friend-store export/restore utility or completed Render cutover drill was found in the reviewed source. The following are **future implementation and approval gates**, not existing capabilities:

1. Measure and inventory the current Friend store tree without exposing memory contents in logs.
2. Implement an owner-authorized export/backup for all Friend stores from the currently running instance. Do not assume attaching a disk copies the old ephemeral filesystem.
3. Record file counts, byte totals, schema versions, owner boundaries, and cryptographic hashes in a private audit artifact.
4. Restore the export into an isolated temporary data root; verify hashes, record counts, and owner/profile/session isolation.
5. Review the exact live Render service plan, disk configuration, mount path, capacity, workspace plan, compute plan, and monthly cost.
6. Obtain explicit approval for the paid-plan change and disk attachment on the existing service.
7. During an approved maintenance window, attach the disk and set `RESEARCH_OS_OWNER_DATA_ROOT=/var/data`. Prevent writes from being lost while the old root is exported and the verified backup is restored.
8. Verify memory, evidence, learning, approval, trace, and preview stores; compare counts and hashes where applicable.
9. Perform a restart/redeploy persistence check and a separate restore drill. Keep the source backup until the owner accepts the parity report.
10. Keep `/v1/memory/commit` labelled separately as runtime-ephemeral until its own storage design is reviewed and approved.

## 9. Deployment and safety controls

The live service is observed with `autoDeploy: yes` on `main`. Render documents `[skip render]` and `[render skip]` as commit-message phrases that suppress an automatic deploy for a commit. The merge commit for this documentation-only PR must include `[skip render]` so that merging the proposal does not deploy or restart the live service.

- Preserve owner/profile/session isolation and do not copy local-only workstation data into Cloud.
- Do not expose memory text, OAuth tokens, secrets, or environment values in logs, CI output, or PR artifacts.
- Do not delete the original local data root or any backup during a future cutover.
- No automatic data migration, overwrite, destructive cleanup, plan change, disk creation, environment change, deploy, restart, or billing change is authorized by this proposal.
- Any production, Render infrastructure/billing, secret, migration, or data-cutover operation requires separate explicit approval before execution.

## 10. Acceptance criteria for a future implementation PR

- Explicit, validated data-root selection for the existing Friend service.
- Tests proving each Friend store resolves beneath the configured root and preserves its documented scope.
- Export/restore tooling with owner authorization, integrity metadata, and no content leakage to logs.
- Restore test into an isolated root and post-restart persistence test covering every store.
- Render plan reviewed for the existing service only, with exact cost, disk capacity, snapshot limitations, single-instance constraint, and downtime disclosed.
- No infrastructure apply or data cutover until required CI checks pass and the user explicitly approves the final Render plan and migration window.
