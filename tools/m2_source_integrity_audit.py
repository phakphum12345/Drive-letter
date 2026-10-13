#!/usr/bin/env python3
"""M.2 source-integrity audit: byte-level checks bound to an exact Git SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {
    ".py", ".pyi", ".dart", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".md",
    ".txt", ".ps1", ".psm1", ".psd1", ".sh", ".bash", ".bat", ".cmd",
    ".xml", ".gradle", ".properties", ".php", ".sql", ".ini", ".cfg",
    ".conf", ".workflow", ".lock", ".gitignore",
}
SOURCE_SUFFIXES = {".py", ".pyi", ".dart", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".php", ".ps1", ".psm1", ".sh", ".bash"}
EXEMPT_EMPTY_NAMES = {".gitkeep", ".keep"}
EXTERNAL_ACTION_RE = re.compile(r"^\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)", re.MULTILINE)


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def classify_bytes(path: str, raw: bytes) -> list[dict[str, str]]:
    """Return byte-integrity findings without attempting to mutate or repair the file."""
    p = Path(path)
    suffix = p.suffix.lower()
    findings: list[dict[str, str]] = []
    is_text = suffix in TEXT_SUFFIXES or p.name in {".gitignore", ".gitattributes", ".editorconfig"}
    if is_text and b"\x00" in raw:
        findings.append({"severity": "error", "code": "TEXT_NUL_BYTE", "path": path, "message": "text/source file contains NUL bytes"})
    if is_text and raw.startswith(b"\xef\xbb\xbf"):
        if raw == b"\xef\xbb\xbf":
            findings.append({"severity": "error", "code": "BOM_ONLY_EMPTY_FILE", "path": path, "message": "file contains only a UTF-8 BOM; restore from authoritative source"})
        else:
            findings.append({"severity": "error", "code": "UTF8_BOM", "path": path, "message": "unexpected UTF-8 BOM; compare raw bytes with authoritative source before repair"})
    if is_text and not raw and p.name not in EXEMPT_EMPTY_NAMES:
        findings.append({"severity": "error", "code": "ZERO_BYTE_TEXT_FILE", "path": path, "message": "tracked text/source file is zero bytes"})
    if is_text and raw and not raw.startswith(b"\xef\xbb\xbf"):
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append({"severity": "error", "code": "INVALID_UTF8", "path": path, "message": f"UTF-8 decode failed at byte {exc.start}"})
    return findings


def tracked_paths(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if output.returncode:
        raise RuntimeError(output.stderr.decode("utf-8", "replace").strip() or "git ls-files failed")
    return [item.decode("utf-8", "surrogateescape") for item in output.stdout.split(b"\x00") if item]


def audit(root: Path, expected_sha: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    head = run_git(root, "rev-parse", "HEAD")
    expected = (expected_sha or os.environ.get("TARGET_SHA") or head).strip()
    findings: list[dict[str, str]] = []
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        findings.append({"severity": "error", "code": "INVALID_TARGET_SHA", "path": ".", "message": "TARGET_SHA must be a full 40-character lowercase Git commit SHA"})
    elif head != expected:
        findings.append({"severity": "error", "code": "CHECKOUT_SHA_MISMATCH", "path": ".", "message": f"expected {expected}, checked out {head}"})

    paths = tracked_paths(root)
    casefold_paths: dict[str, list[str]] = defaultdict(list)
    basename_sources: dict[str, list[str]] = defaultdict(list)
    raw_sha256: dict[str, str] = {}
    scanned = 0
    for rel in paths:
        file_path = root / rel
        try:
            raw = file_path.read_bytes()
        except OSError as exc:
            findings.append({"severity": "error", "code": "TRACKED_FILE_UNREADABLE", "path": rel, "message": str(exc)})
            continue
        scanned += 1
        raw_sha256[rel] = hashlib.sha256(raw).hexdigest()
        findings.extend(classify_bytes(rel, raw))
        casefold_paths[rel.casefold()].append(rel)
        if Path(rel).suffix.lower() in SOURCE_SUFFIXES:
            basename_sources[Path(rel).name.casefold()].append(rel)

    for folded, members in sorted(casefold_paths.items()):
        if len(members) > 1:
            findings.append({"severity": "error", "code": "CASEFOLD_PATH_COLLISION", "path": ";".join(sorted(members)), "message": "multiple tracked paths collapse to the same case-insensitive path"})
    for basename, members in sorted(basename_sources.items()):
        if len(members) > 1:
            findings.append({"severity": "warning", "code": "DUPLICATE_SOURCE_BASENAME_REVIEW", "path": ";".join(sorted(members)), "message": "duplicate source basename across paths; review import/reference resolution; not automatically a defect"})

    action_files = [
        p for p in paths
        if (p.startswith(".github/workflows/") and Path(p).suffix.lower() in {".yml", ".yaml"})
        or (p.startswith(".github/actions/") and Path(p).name in {"action.yml", "action.yaml"})
    ]
    action_refs: list[dict[str, str]] = []
    for rel in action_files:
        try:
            content = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in EXTERNAL_ACTION_RE.finditer(content):
            action, ref = match.group(1), match.group(2)
            item = {"path": rel, "action": action, "ref": ref}
            action_refs.append(item)
            if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
                findings.append({"severity": "error", "code": "ACTION_NOT_PINNED_TO_FULL_SHA", "path": rel, "message": f"{action}@{ref} is not pinned to a full 40-character commit SHA"})

    counts: dict[str, int] = defaultdict(int)
    for item in findings:
        counts[item["severity"]] += 1
    status = "FAIL" if counts.get("error", 0) else "PASS"
    return {
        "schema_version": "1.0.0",
        "protocol_id": "M2-SIRP-001",
        "contract": "M2_SOURCE_INTEGRITY_RECOVERY",
        "repository_root": str(root),
        "target_sha": expected,
        "checked_out_sha": head,
        "exact_sha_match": head == expected,
        "files_scanned": scanned,
        "workflow_and_composite_action_files_scanned": len(action_files),
        "external_action_references_scanned": len(action_refs),
        "finding_counts": dict(sorted(counts.items())),
        "status": status,
        "findings": findings,
        "raw_sha256_by_path": raw_sha256,
        "limitations": [
            "This first implementation checks tracked-file bytes, exact checkout SHA, case-fold path collisions, duplicate source basenames, and external action SHA pins.",
            "It does not independently prove historical Git ancestry, workflow trigger coverage, UI/artifact SHA lineage, or authoritative recovery. Those remain separate required protocol checks.",
            "A clean byte scan does not certify semantic correctness or authorize release."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sha", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        report = audit(args.root, args.expected_sha)
    except (OSError, RuntimeError) as exc:
        print(f"M2_SOURCE_INTEGRITY_AUDIT=BLOCKED: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    print(f"M2_SOURCE_INTEGRITY_AUDIT={report['status']}")
    return 1 if report["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
