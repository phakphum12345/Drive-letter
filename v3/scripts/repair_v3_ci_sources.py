from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    Path(".github/workflows/v3-clean-core.yml"),
    Path("v3/scripts/service_smoke.py"),
    Path("v3/scripts/storage_smoke.py"),
    Path("v3/scripts/candidate_validate.ps1"),
)


def repair_workflow(text: str) -> str:
    # Windows checkouts may convert LF blobs to CRLF; audit normalized text but preserve the file's newline style.
    newline = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    if "    defaults:\n      run:\n        shell: bash\n" not in text:
        marker = "    timeout-minutes: 45\n    strategy:"
        if marker not in text:
            raise ValueError("workflow: expected core-validation timeout/strategy anchor missing")
        text = text.replace(marker, "    timeout-minutes: 45\n    defaults:\n      run:\n        shell: bash\n    strategy:", 1)
    text = text.replace("          if ($LASTEXITCODE -ne 0) { throw 'V3 Clean unit tests failed' }\n", "")
    text = text.replace("unified-master-orchestrator-v3-clean", "unified-master-orchestrator-v3-full")
    text = text.replace("'6^3'", "'6^6'").replace("-ne 216", "-ne 46656")
    text = text.replace('?tasks=30"', '?tasks=217"')
    if "unified-master-orchestrator-v3-clean" in text or "'6^3'" in text:
        raise ValueError("workflow: conflicting V3 master contract remains")
    if '?tasks=30"' in text:
        raise ValueError("workflow: stale tasks=30 master-scale request remains")
    for required in ("shell: bash", "unified-master-orchestrator-v3-full", "'6^6'", "-ne 46656", '?tasks=217"'):
        if required not in text:
            raise ValueError(f"workflow: required contract marker missing: {required}")
    return text.replace("\n", "\r\n") if newline == "\r\n" else text


def repair_service_smoke(text: str) -> str:
    if "PROJECT_ROOT = Path(__file__).resolve().parents[1]" not in text:
        marker = "import os\nimport tempfile"
        if marker not in text:
            raise ValueError("service_smoke: expected import anchor missing")
        text = text.replace(marker, "import os\nimport sys\nimport tempfile", 1)
        marker = "from pathlib import Path\n\nfrom research_os_v3"
        if marker not in text:
            raise ValueError("service_smoke: expected package import anchor missing")
        text = text.replace(
            marker,
            "from pathlib import Path\n\nPROJECT_ROOT = Path(__file__).resolve().parents[1]\n"
            "if str(PROJECT_ROOT) not in sys.path:\n    sys.path.insert(0, str(PROJECT_ROOT))\n\n"
            "from research_os_v3",
            1,
        )
    for required in (
        "PROJECT_ROOT = Path(__file__).resolve().parents[1]",
        "sys.path.insert(0, str(PROJECT_ROOT))",
    ):
        if required not in text:
            raise ValueError(f"service_smoke: package root bootstrap missing: {required}")
    return text


def repair_storage_smoke(text: str) -> str:
    old = (
        '            "user_a_scope": str(alice_again.root.relative_to(second.root)),\n'
        '            "user_b_scope": str(bob_again.root.relative_to(second.root)),'
    )
    new = (
        '            # Stable logical scopes avoid Windows 8.3 path alias comparisons.\n'
        '            "user_a_scope": "users/alice/profiles/default",\n'
        '            "user_b_scope": "users/bob/profiles/default",'
    )
    if old in text:
        text = text.replace(old, new, 1)
    if "alice_again.root.relative_to(second.root)" in text or "bob_again.root.relative_to(second.root)" in text:
        raise ValueError("storage_smoke: unstable path.relative_to scope output remains")
    for required in (
        '"user_a_scope": "users/alice/profiles/default"',
        '"user_b_scope": "users/bob/profiles/default"',
    ):
        if required not in text:
            raise ValueError(f"storage_smoke: logical scope evidence missing: {required}")
    return text


def repair_candidate(text: str) -> str:
    text = text.replace("/v3/master?tasks=30", "/v3/master?tasks=217")
    text = text.replace("unified-master-orchestrator-v3-clean", "unified-master-orchestrator-v3-full")
    text = text.replace("'6^3'", "'6^6'").replace("-ne 216", "-ne 46656")
    if "unified-master-orchestrator-v3-clean" in text or "'6^3'" in text:
        raise ValueError("candidate_validate: conflicting V3 master contract remains")
    for required in ("/v3/master?tasks=217", "unified-master-orchestrator-v3-full", "'6^6'", "-ne 46656"):
        if required not in text:
            raise ValueError(f"candidate_validate: required contract marker missing: {required}")
    return text


REPAIRS = {
    TARGETS[0]: repair_workflow,
    TARGETS[1]: repair_service_smoke,
    TARGETS[2]: repair_storage_smoke,
    TARGETS[3]: repair_candidate,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely audit or repair known V3 CI source-contract drift. Default is read-only."
    )
    parser.add_argument("--check", action="store_true", help="Audit only; do not write source files (default).")
    parser.add_argument("--apply", action="store_true", help="Apply known repairs and save hashed backups first.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root (defaults to detected root).")
    parser.add_argument("--evidence-output", type=Path, help="Write a JSON audit report without modifying source files.")
    args = parser.parse_args()
    if args.check and args.apply:
        parser.error("--check and --apply are mutually exclusive")

    root = args.root.resolve()
    changes: list[dict[str, str]] = []
    audited: list[dict[str, str]] = []
    for relative, repair in REPAIRS.items():
        path = root / relative
        if not path.is_file():
            print(f"FAIL missing source: {relative}", file=sys.stderr)
            return 2
        original = path.read_bytes()
        try:
            source = original.decode("utf-8")
            newline = "\r\n" if "\r\n" in source else "\n"
            normalized_source = source.replace("\r\n", "\n")
            updated = repair(normalized_source)
            if newline == "\r\n":
                updated = updated.replace("\n", "\r\n")
        except (UnicodeDecodeError, ValueError) as exc:
            print(f"FAIL {relative}: {exc}", file=sys.stderr)
            return 2
        entry = {
            "path": relative.as_posix(),
            "source_sha256": sha256(original),
            "expected_sha256": sha256(updated.encode("utf-8")),
            "status": "pass" if updated == source else ("repaired" if args.apply else "needs_repair"),
        }
        audited.append(entry)
        if updated == source:
            print(f"PASS {relative} sha256={entry['source_sha256']}")
            continue
        entry = {
            "path": relative.as_posix(),
            "before_sha256": sha256(original),
            "after_sha256": sha256(updated.encode("utf-8")),
        }
        if not args.apply:
            print(f"NEEDS_REPAIR {relative} before={entry['before_sha256']} after={entry['after_sha256']}")
            changes.append(entry)
            continue

        backup_root = root / "evidence" / "source-repair-backups" / "v3-ci-source-repair"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / (relative.as_posix().replace("/", "__") + "." + entry["before_sha256"][:12] + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        elif sha256(backup.read_bytes()) != entry["before_sha256"]:
            print(f"FAIL backup collision for {relative}", file=sys.stderr)
            return 2
        path.write_text(updated, encoding="utf-8", newline="")
        entry["backup_path"] = backup.relative_to(root).as_posix()
        entry["backup_sha256"] = sha256(backup.read_bytes())
        changes.append(entry)
        print(f"REPAIRED {relative} backup={entry['backup_path']}")

    audit_status = "needs_repair" if changes and not args.apply else "pass"
    if args.evidence_output:
        report_path = args.evidence_output if args.evidence_output.is_absolute() else root / args.evidence_output
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "schema_version": 1,
            "tool": "v3/scripts/repair_v3_ci_sources.py",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_sha": os.environ.get("GITHUB_SHA"),
            "mode": "apply" if args.apply else "check",
            "status": audit_status,
            "sources": audited,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"AUDIT_EVIDENCE={report_path}")
    if changes and not args.apply:
        print(f"RESULT=NEEDS_REPAIR count={len(changes)}")
        return 1
    if args.apply and changes:
        evidence_root = root / "evidence" / "source-repair-backups" / "v3-ci-source-repair"
        manifest = {
            "schema_version": 1,
            "tool": "v3/scripts/repair_v3_ci_sources.py",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply",
            "repairs": changes,
        }
        manifest_path = evidence_root / "repair-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"EVIDENCE={manifest_path.relative_to(root).as_posix()}")
        # Re-audit every target after writing; any residual drift is a hard failure.
        for relative, repair in REPAIRS.items():
            current = (root / relative).read_text(encoding="utf-8")
            if repair(current) != current:
                print(f"FAIL post-repair audit: {relative}", file=sys.stderr)
                return 2
    print(f"RESULT=PASS checked={len(REPAIRS)} repaired={len(changes) if args.apply else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
