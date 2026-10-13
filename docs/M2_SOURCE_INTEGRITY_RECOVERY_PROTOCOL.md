# M.2 Source Integrity & Recovery Protocol

- **Protocol ID:** M2-SIRP-001
- **Version:** 1.0.0
- **Status:** ACTIVE — investigation protocol; not a recovery certification
- **Scope:** imported Research OS source snapshot, source/UI parity, workflow coverage, Git provenance, and damaged-file recovery
- **Authority:** M.2 audit produces findings and evidence only. It cannot authorize execution, merge, or release. The existing Final Gate remains the sole release authority.

## 1. Objective

Detect and explain source-integrity failures as a connected system, including:
1. tested SHA, checked-out SHA, source SHA, UI/build SHA, artifact SHA, and evidence SHA drift;
2. missing or rewritten Git history and unverifiable source lineage;
3. files omitted from workflow triggers or test/build scopes;
4. damaged files (NUL bytes, BOM-only files, unexpected BOMs, zero-byte/truncated files, invalid encoding, or source that no longer parses);
5. path collisions, accidental moves, wrong-path copies, duplicate basenames, and source files silently shadowed by another path;
6. UI assets or generated artifacts built from a different revision than the source under test.

A green individual workflow is not proof that the repository is whole. A missing workflow run is not a pass. Never repair evidence by weakening a gate.

## 2. Known incident register (evidence-backed, scoped to the current PR investigation)

| ID | Observation | Classification | Required response |
|---|---|---|---|
| SIR-001 | `tools/tests/test_aeos_assurance_universe_compiler.py` previously failed compilation with `source code string cannot contain null bytes`; commit `41f44b5348ccae453a685047e3fb7a5789cd395b` says it replaces the corrupted test. | Historical corruption; current repair requires re-verification | Re-run byte-level scan and compiler/test suite on exact head; preserve prior blob and diff evidence. |
| SIR-002 | The current CI Lite audit reported BOM in 14 files. | Confirmed current-head source-integrity finding | Record raw-byte hashes; compare each file with an authoritative source before repair. Strip BOM only when content otherwise matches trusted source. |
| SIR-003 | `tools/create_change_queue.py` fetched from the PR head decodes from Base64 as `77u/`, i.e. BOM only with no implementation body. | Confirmed empty/corrupt implementation | Do not “fix” by removing BOM. Recover from an identified, trusted source revision or leave blocked with a recovery finding. |
| SIR-004 | `current/BASELINE_TRUTH_CONTRACT.json` references production and canonical commits `565ab068d5a1540ea799b594ff031ba003e068af` and `fab39afc15739c3dc9952f6f21db46d26f54b683`; the Baseline Truth Gate failed because the verifier could not find the anchors in the checked-out Git object graph. | Confirmed provenance/history failure | Recover/verify the original objects from the authoritative repository or revise the contract only through an approved, evidence-backed lineage decision. Never replace anchors with the current HEAD just to pass. |
| SIR-005 | Prior audit history identified expected squash object `14750f63b0c1871b768874f36f6b7ee32e48cc99` as missing from the imported history. | Historical provenance gap; verify against authoritative remotes | Verify the object and its parent/tree relationships from authoritative Git history; record unavailable vs disproven distinctly. |
| SIR-006 | 84 workflow files were previously identified with action references that violated the repository policy requiring full-length commit-SHA pins. Current head contains examples of SHA-pinned actions, but complete policy compliance must be audited across all workflows and nested composite actions. | Historical workflow policy issue; current whole-tree state unproven | Enumerate every `uses:` including local composite actions; require immutable full SHA pins for external actions and validate nested action references. |
| SIR-007 | Several workflow definitions use `paths` filters, including Flutter CI and Production Certification. | Confirmed coverage risk, not proof of a specific skipped run | Build a changed-file-to-workflow coverage matrix. Required universal integrity checks must run for every PR, regardless of path filters. |
| SIR-008 | Source/UI revision mismatch and cross-path file swallowing were raised as historical failure modes, but this audit has not yet proved a specific mismatched UI artifact or overwritten path. | Open hypotheses; not confirmed findings | Require SHA-bound UI/build manifests and path/blob lineage checks before marking either hypothesis confirmed or ruled out. |

The list above is an incident seed, not an exhaustive claim that every historical failure has been discovered. Every new finding must include its evidence reference and exact target SHA.

## 3. Required evidence model

Every audit report must bind all evidence to:
- repository full name and PR number (when applicable);
- immutable target commit SHA and checked-out `git rev-parse HEAD`;
- source baseline repository/ref/commit and retrieval timestamp;
- path, Git blob SHA, byte length, raw-byte SHA-256, detected encoding/BOM/NUL state;
- workflow name, workflow file SHA, run ID, job ID, result, and changed-file coverage;
- UI source SHA, dependency/lockfile identity, build command/toolchain version, artifact SHA-256, and embedded/build manifest where available;
- recovery decision, authoritative source used, before/after hashes, reviewer, and regression tests.

Missing evidence is `UNKNOWN`, not `PASS`. If the source of truth cannot be reached, mark `BLOCKED_SOURCE_UNAVAILABLE`; do not invent a replacement.

## 4. One-pass audit protocol

1. **Freeze the target.** Resolve PR head once, check out that exact SHA, and assert `git rev-parse HEAD == TARGET_SHA`. Do not silently switch to default branch or a moving ref.
2. **Prove provenance.** Check expected source commits and squash objects exist; inspect ancestry, trees, and relevant blobs against authoritative remotes. Keep current work HEAD separate from production truth.
3. **Scan bytes before text.** Walk all tracked files and report NUL bytes, UTF-8 BOM, BOM-only/zero-byte files, invalid UTF-8 where UTF-8 is required, suspiciously truncated files, and parser/compiler errors. Do not rewrite files during the audit.
4. **Compare authoritative file lineage.** For every finding, compare path, mode, blob SHA, raw bytes, and file history against a trusted source commit. Never infer intended content from the filename or a nearby file.
5. **Audit path integrity.** Compare tree paths between baseline and target; detect additions/deletions/renames, case-only collisions, duplicate basenames in critical source/UI areas, and identical or conflicting content at multiple paths. A duplicate basename is a finding for review, not automatic proof of a bug.
6. **Audit workflow coverage.** Enumerate all changed files and all workflows. Evaluate path filters and job-level conditions; identify files with no required validation owner and workflows that were expected but did not run. Require a path-independent source-integrity gate on every PR.
7. **Bind UI and artifact lineage.** Ensure UI tests/builds use the same exact source SHA as the candidate. Record artifact hash and manifest; reject stale caches or artifacts whose source SHA cannot be proven.
8. **Repair by authoritative recovery.** Restore complete content from a verified blob/commit. If no trusted source exists, keep the file blocked; do not create a plausible substitute. Preserve original and recovered hashes and a minimal diff.
9. **Regression and independent verification.** Run parser/compiler, focused tests, repository-wide audit, UI tests/builds, workflow coverage checks, and lineage verification on the exact repaired SHA. Re-run the audit independently.
10. **Final decision.** Emit PASS only if all required checks ran and evidence is complete. Otherwise emit FAIL or BLOCKED with specific findings. No gate suppression, status fabrication, or authority escalation.

## 5. Required invariants

- `TARGET_SHA == checked_out_SHA == tested_source_SHA`.
- A release artifact must identify the same source SHA and have a verified artifact hash.
- A path/name match alone never establishes file identity; use Git blob SHA and raw-byte SHA-256.
- Missing historical Git objects cannot be “repaired” by changing a contract to point at an unrelated commit.
- Workflow not triggered, skipped, cancelled, or missing evidence is never treated as successful validation.
- File restoration must not cross project boundaries or replace another path without an explicit rename/move record.
- UI source and backend/API contract versions must be compatible and evidenced, not inferred from a successful compile alone.
- M.2 audit is evidence-producing and advisory; Final Gate retains release authority.

## 6. Exit criteria

The protocol is complete only when the incident register is updated with confirmed/resolved/blocked status; every repaired file has authoritative provenance; all changed files have validation coverage; source/UI/artifact SHAs reconcile; historical anchor availability is independently proven; and the exact target's required gates pass without weakening their assertions.

## 7. Latest evidence update — exact PR head `522057f6e4622535a085d7c55b053fe280a1ddb7`

Audit evidence: [M.2 Source Integrity run 38407689847](https://github.com/phakphum12345/Drive-letter/actions/runs/38407689847). The run checked out the exact PR head and returned **FAIL** with 20 errors and 22 warnings.

Confirmed byte findings:
- 17 files with unexpected UTF-8 BOM, plus the BOM-only `tools/create_change_queue.py` (18 BOM-affected files in total).
- `versions/v1.0.0-draft/docs/00_FOUNDATION/ANEF-001_PROJECT_OVERVIEW.md` contains NUL bytes and fails UTF-8 decoding. Its original bytes are not presumed to be ordinary Markdown; restore only from an authoritative blob.
- 22 duplicate-source-basename groups are review warnings. They are not automatically file collisions; compare Git blob IDs, imports, build targets, and ownership before moving or deleting any file.

Related exact-head failures:
- [CI Lite run 38407687735](https://github.com/phakphum12345/Drive-letter/actions/runs/38407687735) still fails the 6x6 file audit on the 14 Python files whose first character is U+FEFF.
- [Baseline Truth Gate run 38407688988](https://github.com/phakphum12345/Drive-letter/actions/runs/38407688988) cannot find the declared production/canonical history anchors in the checked-out object graph. This is a provenance failure, not permission to replace the anchors with the current head.
- [Production readiness job](https://github.com/phakphum12345/Drive-letter/actions/runs/38407689007/job/115332592608) expects `render.yaml`, `render.staging.yaml`, `scripts/backup-research-os.ps1`, and `scripts/restore-research-os.ps1`. The two render manifests are absent from both the PR head and its base commit, so the evidence points to a workflow/source-snapshot contract mismatch rather than a PR deletion. Do not create placeholder manifests to satisfy the check.

Implementation boundary: the current `tools/m2_source_integrity_audit.py` checks tracked-file bytes, exact checkout SHA, case-fold path collisions, duplicate source basenames, and external action SHA pins. It does **not yet** independently prove historical ancestry, workflow path-filter coverage, UI/build/artifact SHA lineage, or authoritative recovery. These remain open checks and cannot be reported PASS from the current audit.

## 8. Recovery event — ANEF-001 source restoration

The corrupted `ANEF-001_PROJECT_OVERVIEW.md` was restored in commit [`4837ee6ff890f26f5332c02b0f42f0b405fcbe70`](https://github.com/phakphum12345/Drive-letter/commit/4837ee6ff890f26f5332c02b0f42f0b405fcbe70) from the authoritative repository `phakphum12345/ENTERPRISE_API_ARCHITECTURE_LOGIC_TH`, commit `565ab068d5a1540ea799b594ff031ba003e068af`.

- Previous target blob: `1f393559390921bb5282c0a93da7cc208b10a971` (M.2 detected NUL and invalid UTF-8).
- Authoritative source blob: `b9a9e9c38300bb13ea9ca8afe32dc5e499af1fd0`.
- Restored target blob: `b9a9e9c38300bb13ea9ca8afe32dc5e499af1fd0` — exact Git blob SHA match.
- Disposition: **restored; independent exact-head re-audit pending**. This does not certify the remaining BOM files, missing source helpers, baseline gate, workflow coverage, UI SHA lineage, or path-shadow warnings.

## 9. Current disposition

**NOT CERTIFIED.**
