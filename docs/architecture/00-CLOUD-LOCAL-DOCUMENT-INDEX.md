# Research OS Cloud + Local Architecture — Document Index

**Document set:** ROS-CL-ARCH  
**Revision:** 1.0-draft  
**Status:** Architecture proposal for review; not an implementation authorization  
**Date:** 2026-11-03  
**Repository:** `phakphum12345/Drive-letter`  
**Baseline:** `main` at `63e863b6823e26d044ac6a524503c795a4bc9165`

## 00. Purpose and reading order

This numbered document set defines the proposed Hybrid Cloud + Local operating model for Research OS. Read the documents in order:

| No. | Document ID | File | Purpose |
|---:|---|---|---|
| 00 | ROS-CL-00 | `00-CLOUD-LOCAL-DOCUMENT-INDEX.md` | Index, scope, status and change control |
| 01 | ROS-CL-01 | `01-CLOUD-LOCAL-ARCHITECTURE.md` | Logical architecture, trust boundaries, execution modes and deployment topology |
| 02 | ROS-CL-02 | `02-CLOUD-LOCAL-API-CONTRACT.md` | Job, Agent, lease, checkpoint, evidence and API contract proposal |
| 03 | ROS-CL-03 | `03-CLOUD-MIGRATION-GAP-AUDIT.md` | Source-backed current-state audit, migration gaps, risks and phased acceptance criteria |

## 01. Scope

The target is one Research OS product with two execution environments:

1. **Cloud Mode** — executes work that needs only cloud-available services and approved cloud data.
2. **Local Mode** — executes work that requires the user's Windows machine, local files, installed tools or Owner Friend runtime.
3. **Hybrid orchestration** — routes each job or job stage to the appropriate environment while preserving one identity, policy, authorization and evidence model.

Cloud and Local are execution modes, not separate user accounts or independent products.

## 02. Explicit non-goals for this document PR

- No Azure resources are provisioned.
- No production service, API, database, queue or installer is changed.
- No user data, ProgramData, OAuth token, session, memory, checkpoint, queue or evidence file is migrated, rewritten or deleted.
- No credentials, client secrets, access tokens or private keys are added to the repository.
- No PR is merged by this documentation change.

## 03. Governing principles

1. Preserve the existing local installation and its data by default.
2. Keep the Windows Friend service private; Local Agent initiates outbound authenticated connections to Cloud.
3. Cloud execution must not depend on a PC being online.
4. Local-only work must wait safely when no eligible Local Agent is connected.
5. A job may be retried only with explicit lease ownership and idempotency protection.
6. A checkpoint is recovery context, not permission to execute or release.
7. Evidence must identify the source revision, job, worker/agent, policy decision and resulting artifacts.
8. Unknowns remain marked **TBD / requires verification** rather than being silently assumed.
9. Roll out through additive, reversible steps with backups and tested restore procedures.

## 04. Review and approval gates

| Gate | Required evidence | May proceed when |
|---|---|---|
| G0 — Documentation review | This document set, source references, unresolved questions | Architecture and migration boundaries are accepted |
| G1 — Contract approval | Versioned schemas, compatibility tests, threat model | API and identity boundaries are approved |
| G2 — Cloud foundation | Subscription, region, budget, network, backup and security evidence | Infrastructure plan is approved |
| G3 — Runtime migration | Data inventory, export/import validation, rollback rehearsal | Data parity and rollback are proven |
| G4 — Hybrid execution | Lease, reconnect, idempotency and offline tests | Local/Cloud routing passes acceptance tests |
| G5 — Production release | Security review, SLO/alerts, restore drill, release gate | Authorized release approver signs off |

## 05. Status vocabulary

- **Verified** — directly observed in the baseline source or test.
- **Proposed** — target design, not yet implemented.
- **TBD** — evidence or decision is still required.
- **Blocked** — must not proceed until the named condition is resolved.

## 06. Change control

This document set is based on the baseline SHA above. Any material runtime change, storage migration, public endpoint, permission expansion or data transformation requires a separate implementation PR with tests, audit evidence and rollback instructions. Update this index and the affected document revision when the contract changes.
