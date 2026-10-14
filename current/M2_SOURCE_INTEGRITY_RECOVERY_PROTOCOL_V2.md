# M.2 Source Integrity Recovery Protocol v2

**Protocol ID:** M2-SIRP-002  
**Status:** Proposed for verification; not a release authorization  
**Applies to:** source snapshots, imported repositories, workflow definitions, UI/build outputs, and recovery of previously damaged files  
**Core rule:** a green gate is evidence only for the exact revision, paths, and assertions it actually tested.

## 1. Incident signatures this protocol must detect

1. **Revision/SHA drift:** PR head, merge commit, checkout HEAD, audit target SHA, UI-reported SHA, build input SHA, and published artifact SHA refer to different revisions or are not linked by verifiable evidence.
2. **Workflow coverage gaps:** files exist in the repository but no applicable workflow includes them; path filters, working directories, sparse checkout, generated-file steps, or composite actions omit them.
3. **Path aliasing or file swallowing:** files with identical basenames, case-fold collisions, moved/renamed files, duplicate trees, or a wrong working directory cause a tool or UI to read a different file than intended.
4. **Content corruption:** NUL bytes, BOM-only files, unexpected BOMs, zero-byte source, truncated files, invalid encoding, line-ending-only changes that alter byte hashes, or an imported file that differs from its authoritative blob.
5. **False-green validation:** a gate reports success while validating only a structural placeholder, skipping absent test surfaces, testing a different SHA, or not checking the actual production/UI artifact.
6. **Recovery without provenance:** a damaged file is reconstructed or stripped of bytes without a known-good source, immutable blob SHA, path, and commit lineage.

## 2. Required SHA chain

For each audit run, record and compare these identities separately:

- PR head SHA.
- PR merge SHA, if the workflow checks the merge ref.
- Explicit TARGET_SHA.
- git rev-parse HEAD after checkout.
- Source SHA used by the UI/API, if displayed or embedded.
- Build input SHA and resulting artifact provenance.
- Commit SHA attached to every evidence report.

The audit must fail if a workflow claims exact-SHA validation but the checked-out HEAD differs from its target. If the UI does not expose a source/build SHA, record that as UNVERIFIED, not PASS. A workflow run tied to a head SHA must not be presented as proof for a later SHA.

## 3. Repository and path integrity

- Enumerate tracked files from the exact checkout using Git, not only a filesystem glob.
- Detect missing tracked files, unreadable files, zero-byte source files, BOM-only files, NUL bytes in text files, invalid UTF-8, and suspicious truncation.
- Detect case-insensitive path collisions.
- Report duplicate source basenames as review findings, then inspect imports, routing, build manifests, and call sites to determine whether they are legitimate or shadowing one another. Do not automatically delete or rename them.
- Resolve every workflow path, working-directory, composite action, generated output, UI asset path, and artifact path against the same repository root. Record paths that are expected by a workflow but absent from the target tree.
- Audit path filters against the files they are supposed to protect. A workflow not triggered for a relevant change is a coverage defect even if its last recorded run is green.
- Treat renamed or moved files as a lineage question: prove old path -> new path and update all references; do not assume a same-basename file is equivalent.

## 4. Recovery rules for damaged files

For every finding, preserve the original path, commit SHA, Git blob SHA, raw SHA-256, size, and classification before repair.

1. Prefer restoring the exact file bytes from a verified authoritative repository and commit.
2. Confirm both the path and blob/content hash before accepting the restoration.
3. If no authoritative copy is available, mark the file UNRECOVERED and block release-dependent claims. Do not invent source code from its filename or strip a BOM-only file and call it repaired.
4. For unexpected BOMs, compare the file with the authoritative blob first. Remove a BOM only when evidence shows it was introduced by corruption or tooling and the resulting content is validated.
5. For NUL bytes or suspected truncation, recover from provenance first; syntax repair alone is insufficient.
6. Record the before/after blob hashes and the reason for every intentional difference.

## 5. Workflow and gate completeness

For each applicable workflow:

- Confirm the trigger, branch filters, path filters, checkout ref, working directory, required inputs, and actual test command.
- Verify all referenced local composite actions and scripts exist at the exact checked-out revision.
- Identify optional/skipped tests and structural fallbacks. A skipped test surface must be reported as NOT TESTED, never treated as behavioral proof.
- Verify the gate's claims against its assertions. A check that only looks for a README keyword cannot certify runtime correctness.
- Pin external GitHub Actions to full commit SHAs and review nested actions in composite actions.
- Keep security/authorization tests fail-closed. Do not convert expected 401/403 denials into success merely to make logs green; use response bodies and assertions to diagnose unexpected denials.

## 6. UI/build/artifact lineage

The UI and every distributable artifact must expose or emit a provenance record containing:

- repository and canonical path;
- source commit SHA;
- build workflow/run ID;
- build input SHA and toolchain versions;
- artifact digest (SHA-256);
- environment/channel/platform;
- whether the artifact was rebuilt from the audited source or reused from cache.

Verify provenance by recomputing the artifact digest and matching it to the published evidence. Cache keys must include the relevant source identity or immutable lock/config inputs. A UI label or status badge alone is not source provenance.

## 7. M.2 evidence schema and decision

Each report must include:

- protocol_id, schema_version, repository, target SHA, checked-out SHA, and exact-SHA match;
- tracked file inventory and missing/unreadable files;
- path-collision and duplicate-basename findings;
- per-file byte hashes and Git blob SHAs for affected files;
- authoritative source/commit/blob references for every recovery;
- workflow coverage inventory, path-filter coverage, and skipped/optional checks;
- UI/build/artifact SHA lineage or explicit UNVERIFIED;
- findings with severity, evidence, owner/action, and recovery status.

Decision values:

- **PASS:** all mandatory checks are proven for the exact target revision.
- **FAIL:** at least one mandatory integrity, lineage, coverage, or validation assertion failed.
- **UNVERIFIED:** required source of truth or provenance is unavailable; this is not equivalent to PASS.
- **RECOVERED_PENDING_RETEST:** bytes restored with provenance, but all relevant tests and gates have not yet been rerun.

No protocol result by itself authorizes merge, deployment, or release. The applicable Final Gate remains authoritative.

## 8. Application to the current Drive-letter PR

Initial evidence at PR head e5f9317869430a30c5f258a18d9652238935ae3f:

- M.2 source-integrity report records exact target/checkout SHA equality, but reports 17 errors and 22 warnings; exact-SHA equality does not mean file integrity passed.
- CI Lite reports unexpected BOMs in 13 Python files and identifies tools/create_change_queue.py as BOM-only.
- V3.5 Master Final Gate expects render.yaml, render.staging.yaml, scripts/backup-research-os.ps1, and scripts/restore-research-os.ps1; the run fails immediately because render.yaml is absent from the checked-out PR merge tree.
- The current audit implementation explicitly states that workflow path-filter coverage, UI/build/artifact SHA lineage, and authoritative recovery are not yet independently proven.

Required next actions: recover affected files from verified source history; investigate the missing production-readiness assets and whether this source snapshot is meant to contain them; inspect all M.2 findings, including action SHA pin errors and duplicate paths; extend executable tests to cover the missing lineage/coverage checks; rerun the complete relevant gate set on one recorded target SHA. Do not merge while any mandatory item remains FAIL or UNVERIFIED.
