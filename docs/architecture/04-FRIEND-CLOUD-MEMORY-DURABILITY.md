# Friend Cloud Memory Durability — Design and Safe Cutover

**Status:** Proposed; infrastructure changes and data cutover are not applied  
**Repository:** `phakphum12345/Drive-letter`  
**Service:** `research-os-api-phakphoum`  
**Scope:** Owner Friend filesystem-backed stores only

## 1. Decision

The Render service currently runs on the Free plan and has no persistent disk configured in its service definition. Friend memory must therefore be described as filesystem-backed but not guaranteed durable across Render restarts or deploys.

The target is to preserve the existing Friend store layout on a Render persistent disk mounted at `/var/data`, with `RESEARCH_OS_OWNER_DATA_ROOT=/var/data`. This is a single-instance design and is not a multi-replica storage solution.

This proposal does not create a disk, change the running service plan, deploy code, restart the service, or migrate existing data.

## 2. Current source-backed behavior

- `render_server.py` resolves the Friend data root in this order: `RESEARCH_OS_OWNER_DATA_ROOT`, `RESEARCH_OS_DATA_DIR`, then `~/.research_os_owner_special`.
- `FriendRuntime.create_owner_special` uses the supplied data root for owner-scoped memory, preview data, evidence, learning records, agent traces, and approval records.
- `PersistentScopedMemory` stores owner/profile/session-scoped records in JSON and atomically replaces the file after writes.
- The existing unit test proves memory survives recreating a runtime with the same local temporary directory. It does not prove survival across Render instance replacement.
- The separate `/v1/memory/commit` research-artifact path has its own durability contract and is not made durable by this Friend data-root change.

## 3. Proposed Render configuration

After backup/export and restore verification, the proposed service configuration is:

```yaml
plan: starter
disk:
  name: friend-owner-data
  mountPath: /var/data
  sizeGB: 1
envVars:
  - key: RESEARCH_OS_OWNER_DATA_ROOT
    value: /var/data
```

The 1 GB disk is a starting capacity assumption, not a measured capacity requirement. Confirm actual store size and growth before applying the infrastructure plan. The disk must be attached to the existing API service; do not create a second API service or database.

## 4. Cost estimate — verify before applying

The current Render pricing page lists the Starter web-service compute tier at approximately **$6/month** and persistent disk storage at **$0.25 per GB per month**. A 1 GB disk therefore gives a planning estimate of **about $6.25/month**, before bandwidth or other usage charges. Pricing can change; re-check the Render plan preview and billing page immediately before approval.

This estimate is incremental to the current Free service configuration. No paid resource is created by this document or its pull request.

## 5. Operational constraints

Render persistent disks:
- Preserve only files written under the configured mount path.
- Are accessible to one service instance; a service with a disk cannot be horizontally scaled to multiple instances.
- Disable zero-downtime deploys; the old instance is stopped before the new instance starts.
- Receive automatic daily snapshots retained for seven days.

Therefore the first implementation must retain the current single-instance model, provide a tested export/restore path, and disclose the brief service interruption associated with deploys.

## 6. Mandatory data-preserving cutover sequence

1. Measure and inventory the current Friend store tree without exposing memory contents in logs.
2. Provide an owner-authorized export/backup of existing Friend stores from the currently running instance. Do not assume that attaching a new disk copies the old ephemeral filesystem.
3. Record file counts, byte totals, schema versions, owner boundaries, and cryptographic hashes in a private audit artifact.
4. Verify that the backup can be restored into an isolated temporary data root and that owner/profile/session isolation remains intact.
5. Review the exact Render infrastructure plan, mount path, capacity, compute plan, and monthly cost.
6. Only after explicit cutover approval, attach the disk to the existing service and set `RESEARCH_OS_OWNER_DATA_ROOT=/var/data`.
7. Restore the verified export to the mounted disk before enabling writes, or use a controlled maintenance cutover that prevents writes from being lost.
8. Verify memory, evidence, learning, approval, trace, and preview stores; compare counts and hashes where applicable.
9. Perform a restart/redeploy persistence check and a restore drill. Keep the source backup until the user accepts the parity report.
10. Keep `/v1/memory/commit` labelled separately as runtime-ephemeral until its own storage design is approved.

## 7. Security and preservation requirements

- Preserve owner/profile/session isolation.
- Do not copy local-only workstation data into Cloud.
- Do not expose memory text, OAuth tokens, secrets, or environment values in logs, CI output, or PR artifacts.
- Do not delete the original local data root or any backup during cutover.
- No automatic data migration, overwrite, or destructive cleanup.
- No secrets or environment values are read or changed as part of this proposal.

## 8. Acceptance criteria for the implementation PR

- Explicit, validated data-root selection for the existing Friend service.
- Tests proving that all Friend stores resolve beneath the configured root.
- Export/restore tooling with owner authorization, integrity metadata, and no content leakage to logs.
- Restore test into an isolated root and post-restart persistence test.
- Render plan reviewed for the existing service only, with exact cost and downtime disclosed.
- No merge or infrastructure apply until required CI checks pass and the user approves the final Render plan.
