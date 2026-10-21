# Research OS Root Server + Git Remote + Local + BIOS Architecture

- **Document ID:** RESEARCH-OS-ROOT-REMOTE-LOCAL-BIOS-ARCH
- **Version:** 1.0.0
- **Status:** PROPOSED — evidence-first review required
- **Authority:** `FINAL_GATE` remains the only release authority
- **Baseline repository:** `phakphum12345/Drive-letter`
- **Baseline main SHA inspected:** `ad88d8d33f0c14deae2c7770328d336f217cc76f`
- **Created on branch:** `docs/root-server-git-remote-local-bios-architecture`

## 1. Purpose and non-goals

Define the boundaries, trust relationships, and evidence needed to operate Research OS across a canonical Git remote, a root/runtime server, local Windows development/recovery, and the host's BIOS/UEFI/hardware layer.

This document is an architecture proposal and an audit plan. It does **not** claim the current machine, BIOS, root server, service installation, or artifact has been freshly verified. It does not authorize deployment, merge, service lifecycle actions, disk repair, firmware changes, or deletion.

## 2. Target architecture

```text
                   GOVERNANCE / FINAL_GATE
              policy + authorization + evidence
                              |
                              v
                   CANONICAL GIT REMOTE
                phakphum12345/Drive-letter
                 immutable commit SHA + PR
                              |
                  reviewed build + artifact
                              |
              +---------------+---------------+
              |                               |
              v                               v
       ROOT / RUNTIME SERVER           LOCAL WINDOWS WORKSPACE
       deployed immutable release      checkout / test / staging
       loopback or approved ingress    isolated candidate validation
       durable app data                recovery evidence / backups
              |                               |
              +---------------+---------------+
                              |
                              v
                    HOST BIOS / UEFI / HW
             boot mode, Secure Boot, disk health,
             firmware entries, device inventory
```

### Trust boundaries

1. **Git remote is source authority, not runtime health authority.** Record repository, branch, full commit SHA, workflow run, and artifact digest separately.
2. **Build output is not a release by itself.** Require exact-SHA validation, package manifest verification, hashes, required tests, and the repository's existing Final Gate.
3. **Root Server is a runtime role, not an assumed physical host.** Its hostname, operating system, identity, ingress, data path, and service inventory must be discovered before configuration.
4. **Local is a separate environment.** Do not treat a local extracted ZIP, a Git checkout, a service installation, and an Actions runner as the same runtime.
5. **BIOS/UEFI is a hardware trust layer.** Inspect it read-only first. Firmware configuration is not managed by Git and must not be changed by a repository workflow.
6. **Persistent data is independent of application binaries.** Preserve `C:\\ProgramData\\ResearchOS` and any discovered user data. Never point a migration at an unverified or default data directory.

## 3. Responsibilities by layer

| Layer | Responsibility | Required evidence | Forbidden assumption |
|---|---|---|---|
| Canonical Git remote | Source, branches, PRs, review history | repository URL, exact SHA, diff, checks | branch name proves artifact provenance |
| CI/build | Reproducible validation and packaging | run ID, checked-out SHA, job outcomes, artifact digest, manifest | successful build means production ready |
| Root/runtime server | Run approved services and expose approved endpoints | host identity, service config, PID, port binding, health response, logs | a server exists or is reachable without evidence |
| Local Windows | Checkout, isolated test, staging, recovery | Git status, free space, volume health, archive hash, manifest comparison | extracted files are complete because extraction returned |
| BIOS/UEFI/hardware | Boot/security/storage foundation | BIOS vendor/version, boot mode, Secure Boot result, disk/volume health, firmware entries | duplicate boot entries are safe to delete |
| Durable data | Sessions, database, artifacts, backups, owner-friend state | inventory, backup verification, data-root configuration | reinstall may reset or replace the data directory |
| Final Gate | Sole release authority | required checks tied to the same candidate SHA | skipped/unknown checks count as passing |

## 4. Network and service-binding policy

- Default to loopback-only API listeners unless a documented requirement explicitly authorizes network exposure.
- Use `127.0.0.1` for local API binding and test endpoints on `127.0.0.1`; do not silently use `0.0.0.0`.
- If remote access is required, specify the ingress boundary, authentication, TLS, firewall policy, and allowed client identities before enabling it.
- Inventory listeners and owning process IDs before service actions. Do not terminate unrelated processes or GitHub Actions runners.
- Service lifecycle operations (`install`, `uninstall`, `start`, `stop`, `restart`) are writes and require a reviewed plan. A read-only status/health check must precede them.
- Avoid exposing credentials in command lines, logs, PRs, or evidence artifacts.

## 5. Artifact identity and promotion contract

A candidate artifact is identifiable only by a linked evidence tuple:

```text
repository + source SHA + workflow run ID
+ artifact name + downloaded artifact digest
+ inner package SHA256 + manifest SHA256
+ manifest file count + per-file size/hash verification
+ required check outcomes + Final Gate decision
```

Do not compare the digest of an outer GitHub Actions artifact archive directly with the SHA256 of an inner platform ZIP; they are different byte sequences. Downloaded bytes must be hashed locally and compared to the correct digest for that exact object.

### Existing evidence observed during the initial investigation

- Main SHA at the time of inspection: `ad88d8d33f0c14deae2c7770328d336f217cc76f`.
- Distribution run `39620902471` built source SHA `6502b0e15218c9f4be1578aed56b9b78b4561dd9`; the connector reported `validate` and `build` as successful.
- That run's outer artifact was named `Research-OS-Unified-Windows-x64-a44d7d89ef1240e40892263dc0de652969af02b3`, with reported archive digest `sha256:888033d2fd171510f1145719361b760191d03120212a59afb93e559c0b66e59a`.
- The previously inspected local platform ZIP was named with source SHA `e101d3e2c45f745d0d2c6f969892d7f03ca63105` and had SHA256 `663BFE14E8F0E4AB0B8139E14FCE514E7261AC113FFA48EE918F5024DA16E79F`.
- These source SHAs differ. The run above does **not** prove that the previously inspected local ZIP came from that run. Artifact contents and embedded release evidence must be downloaded and compared before promotion.
- Prior local inspection reported a staging directory with zero-byte files and a successful one-file extraction test. Those facts are reasons to perform a complete, isolated archive/manifest audit; they are not evidence that a full restore succeeded.

These are dated investigation observations, not claims of current host state. Re-check the live branch, run, and artifact before any decision.

## 6. Evidence-first audit sequence

### Gate A — Source and PR integrity (read-only)
- Record current main SHA and clean/dirty local Git status.
- Verify canonical remote URL and all configured remotes; do not rename or overwrite remotes during discovery.
- Inventory open PRs and overlapping architecture/recovery work to avoid duplicate implementations.
- Confirm that the candidate branch is based on the intended main SHA and that its diff contains only the proposed scope.

### Gate B — Root Server discovery (read-only)
- Establish whether the root server is a physical machine, VM, container host, or logical service role.
- Record hostname, OS/build, identity context, route/interface inventory, service names, listener addresses, ports, process IDs, health responses, and recent relevant logs.
- Do not assume localhost on the developer workstation is the same host as the root server.

### Gate C — Local and storage safety (read-only)
- Record disk/volume health, free space, current install-root contents, service registrations, and listeners.
- Inventory durable data without copying secrets into logs.
- Hash the source archive before extraction; extract only into a new, uniquely named staging directory after verifying sufficient space.
- Verify every manifest entry for existence, exact size, and SHA256; detect missing, duplicate, and unlisted entries. Any zero-byte file where the manifest expects nonzero bytes is a hard failure.
- Never use a script that continues after errors or prints PASS after a failed verification.

### Gate D — BIOS/UEFI discovery (read-only)
- Collect manufacturer/model, BIOS vendor/version/date, Secure Boot state when supported, boot entries, partition style, and disk health.
- If a query is unsupported (for example, Secure Boot query on a non-UEFI boot), record it as unavailable rather than infer a value.
- Do not change Secure Boot, boot order, EFI entries, firmware settings, partitions, or repair state as part of this PR.

### Gate E — Isolated candidate validation
- Validate the exact source SHA and artifact tuple.
- Test package completeness in an isolated staging path that does not overlap production or persistent data.
- Check API host binding, port ownership, service paths, runtime dependencies, and health endpoints.
- Run applicable automated tests and capture each outcome as PASS, FAIL, SKIPPED/NOT APPLICABLE with justification, or BLOCKED_EVIDENCE.
- Never convert missing or skipped evidence into a pass.

### Gate F — Promotion proposal
Promotion remains blocked until the package's exact source and hashes match, all required checks are tied to the same candidate SHA, persistent data is protected, network binding is approved, and Final Gate passes. Merge and installation are separate decisions.

## 7. Suggested evidence record

Each audit record should include:

- `evidence_id`, `observed_at_utc`, `operator`, `host_id`
- `repository`, `base_sha`, `candidate_sha`, `workflow_run_id`
- `artifact_name`, `artifact_digest`, `inner_package_sha256`, `manifest_sha256`
- `scope`, `command_or_check`, `result`, `exit_code`
- `evidence_location`, `limitations`, `next_action`
- immutable reference to the original output; redact secrets and personal identifiers

Allowed results: `PASS`, `FAIL`, `SKIPPED_JUSTIFIED`, `BLOCKED_EVIDENCE`, `NOT_RUN`. The record itself grants no execution, merge, or release authority.

## 8. Rollout and rollback design

1. Capture a pre-change inventory and verify a restorable backup of persistent data.
2. Validate a release in isolated staging.
3. Produce a reviewable change plan including data paths, service names, ports, rollback trigger, and exact rollback artifact.
4. Obtain explicit approval before any production write, service lifecycle action, firewall change, or firmware change.
5. Promote only after the existing Final Gate has passed on the exact candidate.
6. Post-deploy, verify service state, PID stability, listener binding, health endpoints, logs, and data continuity.
7. On failure, stop promotion and preserve evidence. Roll back binaries/configuration to the known artifact; do not delete or replace persistent data as a rollback shortcut.

## 9. Acceptance criteria for this proposal

- [ ] No implementation is duplicated; existing Research OS contracts and service scripts are reused.
- [ ] Source SHA, workflow run, artifact digest, inner ZIP hash, and manifest are cross-linked and verified.
- [ ] Root Server identity and local host identity are explicit.
- [ ] Runtime listeners are loopback-only unless approved ingress is documented.
- [ ] BIOS/UEFI evidence is read-only and has no firmware mutations.
- [ ] Persistent data paths are inventoried and protected.
- [ ] Missing, skipped, stale, or mismatched evidence blocks promotion.
- [ ] Required tests and Final Gate results refer to one exact candidate SHA.
- [ ] PR is reviewed and validated before merge; this proposal does not authorize merging itself.

## 10. References

- Repository: https://github.com/phakphum12345/Drive-letter
- Main baseline observed: https://github.com/phakphum12345/Drive-letter/commit/ad88d8d33f0c14deae2c7770328d336f217cc76f
- Distribution workflow run: https://github.com/phakphum12345/Drive-letter/actions/runs/39620902471
- Distribution workflow source: `.github/workflows/research-os-phase-e-unified-windows-distribution.yml`
- Existing service launcher: `scripts/research-os-service.ps1`
- Existing local launcher: `scripts/start-research-os-local.ps1`
- Existing distribution contract: `current/RESEARCH_OS_PHASE_E_UNIFIED_WINDOWS_DISTRIBUTION_CONTRACT.json`
- Repository rulebook: `README.md`

## Revision history

- 1.0.0 — Initial evidence-first architecture proposal; no machine, service, disk, or firmware changes performed.
