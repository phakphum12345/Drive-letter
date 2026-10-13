# M.2 Source Integrity Recovery Protocol

**Protocol ID:** M2-SOURCE-INTEGRITY-RECOVERY-001  
**Applies to:** source imports, recovery branches, UI bundles, CI workflows, and generated evidence  
**Authority:** M.2 is diagnostic; only the existing Final Gate may authorize release/merge.  
**Default decision:** HOLD when provenance or completeness cannot be proven.

## Purpose

Prevent recurrence of mismatched source SHAs, UI/runtime version drift, incomplete workflow coverage, and files silently omitted, overwritten, or mapped to the wrong path during import/recovery.

## Required invariants

1. **Immutable source identity.** Record the source repository, full source commit SHA, target repository, full target commit SHA, and import operation ID. Never infer production truth from the current branch head.
2. **One evidence SHA.** Every audit report, UI artifact manifest, test result, and workflow evidence must state the exact commit SHA it tested. A result for a different SHA is stale evidence, not a pass.
3. **Path-preserving inventory.** Compare canonical relative paths, not basenames. Detect case-fold collisions, duplicate basenames across directories, path renames, missing paths, unexpected paths, and file-count changes. A same basename is a review finding, not proof of a collision by itself.
4. **Content integrity.** For every tracked file record byte length and SHA-256. Detect NUL bytes, UTF-8 BOMs, zero-byte files, whitespace-only files, invalid UTF-8 in text assets, and unexpectedly truncated files. Do not repair a file by stripping markers if that leaves it empty or changes its meaning.
5. **Source-backed restoration.** Restore damaged files only from a trusted source revision or a verified recovery artifact. If source provenance is unavailable, preserve the file as quarantined evidence and fail closed; never invent replacement code.
6. **UI/runtime alignment.** Bind the UI source, API contract, generated assets, and packaged artifact to the same declared release/source identity. Compare declared version, API schema/contract digest, and artifact source SHA; do not accept a green UI-only check as proof of backend alignment.
7. **Workflow coverage.** Inventory all workflows and their path filters, triggers, checkout refs, and required jobs. Detect changed source paths that are not covered by any relevant test/audit workflow. A workflow that checks out main, a moving branch, or a different SHA does not prove the PR head unless that is explicitly intended and independently reconciled.
8. **Fail closed.** Missing provenance, missing source files, inconsistent SHA, ambiguous path mapping, or skipped required checks yields HOLD/FAIL; do not disable a Gate, weaken its assertion, or reinterpret missing evidence as PASS.
9. **Recovery is a new evidence event.** After restoring or rewriting files, regenerate the path/hash manifest, rerun affected unit tests, compile checks, UI/API compatibility tests, workflow coverage audit, and all applicable Final Gates against the exact new SHA.

## Required audit outputs

Each run must emit machine-readable evidence containing:

- protocol ID and protocol version;
- source repository and source commit SHA (or explicit UNKNOWN, which forces HOLD);
- target repository, branch, tested commit SHA, and parent SHA;
- sorted path inventory with path, byte size, SHA-256, and file classification;
- missing/unexpected paths, case-fold path collisions, duplicate-basename review findings;
- BOM/NUL/empty/truncation findings and their dispositions;
- UI, API-contract, and artifact version/source-SHA comparison;
- workflow inventory, trigger/path-filter coverage, checkout SHA/ref, and required-check results;
- restoration provenance for every repaired file;
- final decision (PASS, FAIL, or HOLD) and reasons.

## One-pass recovery sequence

1. Freeze the candidate SHA; do not amend files while evidence is being collected.
2. Resolve the trusted source revision and build a full path + SHA-256 inventory from it.
3. Compare source and target inventories by full path; classify missing, extra, renamed, duplicate/case-colliding, and content-different files.
4. Scan bytes for BOM, NUL, empty/whitespace-only content, decoding errors, and obvious truncation.
5. Reconcile UI/runtime/API contract versions and artifact provenance.
6. Map every changed path to at least one relevant test/audit workflow and verify checkout SHA semantics.
7. Restore only from trusted source, preserving exact path and file bytes where appropriate.
8. Run focused regression tests, then the complete applicable CI/Gates on the resulting exact SHA.
9. Independently read back the final manifest and run evidence. Any unresolved finding remains HOLD; no merge or release is implied by this protocol.

## Initial findings attached to this protocol

The PR #1 candidate at 41f44b5348ccae453a685047e3fb7a5789cd395b has these evidence-backed findings:

- tools/create_change_queue.py contains only UTF-8 BOM bytes (EF BB BF) both at this commit and its parent b5bbc82813a32aa979b5477e523a6dbe348ec14d; this predates the latest compiler-test repair and must be restored from a trusted source, not guessed.
- The prior CI Lite run reported a Python source-integrity failure from NUL bytes in tools/tests/test_aeos_assurance_universe_compiler.py; a later commit replaced that test file, but this alone does not establish that all imported files are intact.
- CI Lite still fails on the candidate due to BOM/source-integrity findings. Baseline Truth Gate also fails because the contract references source-history commit anchors that the target checkout cannot verify. The gate must not be made green by replacing those anchors with the candidate SHA.
- V3.5 Master Final Gate fails at production-readiness evidence validation; its security-boundary, API/contract, code-generation, and E2E jobs passed. This is a distinct evidence gap, not a reason to bypass the failed job.
- Exact-SHA gate passing only proves its own assertion. It does not prove that every workflow, UI artifact, or file inventory used that same SHA.

These are starting findings, not a claim that every historical SHA/path/UI incident has already been exhaustively identified. The protocol requires the complete inventory and evidence comparisons before closure.
