#!/usr/bin/env python3
"""Fail-closed verifier for the exact-SHA Research OS release evidence chain."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name}, found {len(matches)}")
    return matches[0]


def load(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"required evidence missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence must be a JSON object: {path}")
    return value


def verify(root: Path, spine: Path, target: str, spine_run: str, candidate_run: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError("target SHA must be a full 40-character lowercase commit")
    manifest_path = one(root, "DISTRIBUTION_MANIFEST.json")
    manifest_hash_path = one(root, "DISTRIBUTION_MANIFEST.sha256")
    manifest = load(manifest_path)
    manifest_hash = sha256(manifest_path)
    declared_hash = manifest_hash_path.read_text(encoding="utf-8-sig").strip().split()[0].lower()
    if declared_hash != manifest_hash:
        raise ValueError("distribution manifest SHA256 mismatch")
    if manifest.get("source_sha") != target or manifest.get("distribution") != "Research OS Unified Windows":
        raise ValueError("distribution manifest target or product mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or manifest.get("file_count") != len(files):
        raise ValueError("distribution manifest file inventory mismatch")
    if not files or any(not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) for item in files):
        raise ValueError("distribution manifest contains invalid file digest")

    release = load(one(root, "RELEASE_EVIDENCE.json"))
    install = load(one(root, "WINDOWS_INSTALL_E2E_EVIDENCE.json"))
    if release.get("source_sha") != target or install.get("source_sha") != target:
        raise ValueError("release or installation evidence target SHA mismatch")
    if release.get("release_authority") != "FINAL_GATE" or install.get("release_authority") != "FINAL_GATE":
        raise ValueError("final gate authority binding missing")
    if release.get("installer_role") != "OWNER_SPECIAL" or release.get("installation_payload") != "RESEARCH_OS_PLATFORM_ZIP":
        raise ValueError("canonical installer role or payload mismatch")
    hash_file_value = str(install.get("manifest_hash_file", "")).split()
    if install.get("manifest_sha256") != manifest_hash or not hash_file_value or hash_file_value[0].lower() != manifest_hash:
        raise ValueError("installed E2E evidence is not bound to the distribution manifest")

    archive = one(root, f"Research-OS-Platform-Windows-x64-{target}.zip")
    setups = list(root.rglob("Research-OS-Owner-Special-Setup-*-x64.exe"))
    if len(setups) != 1:
        raise ValueError(f"expected exactly one Owner Special Setup.exe, found {len(setups)}")
    setup = setups[0]
    archive_hash, setup_hash = sha256(archive), sha256(setup)
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        for item in files:
            name = str(item.get("path", ""))
            if not name or name not in names:
                raise ValueError(f"distribution ZIP is missing manifest file: {name}")
            if hashlib.sha256(package.read(name)).hexdigest() != item["sha256"]:
                raise ValueError(f"distribution ZIP file digest mismatch: {name}")
    if release.get("platform_zip") != archive.name or release.get("platform_zip_sha256") != archive_hash:
        raise ValueError("platform ZIP identity or SHA256 mismatch")
    if release.get("owner_special_setup") != setup.name or release.get("owner_special_setup_sha256") != setup_hash:
        raise ValueError("Owner Special installer identity or SHA256 mismatch")
    if install.get("platform_zip") != archive.name or install.get("platform_zip_sha256") != archive_hash:
        raise ValueError("installation E2E platform ZIP mismatch")
    if install.get("installer") != setup.name or install.get("installer_sha256") != setup_hash:
        raise ValueError("installation E2E installer mismatch")
    checks = install.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise ValueError("Windows installation E2E checks are incomplete or not all PASS")

    certification = load(spine)
    if certification.get("schema") != "research-os.release-spine.v1" or certification.get("immutable") is not True:
        raise ValueError("release spine certification schema or immutability mismatch")
    if certification.get("commit") != target or str(certification.get("run_id")) != str(spine_run):
        raise ValueError("release spine certification is not bound to the requested target/run")
    supplied_hash = certification.get("manifest_sha256")
    unsigned = dict(certification)
    unsigned.pop("manifest_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    if supplied_hash != hashlib.sha256(canonical).hexdigest():
        raise ValueError("release spine certification manifest hash mismatch")
    gates = certification.get("gates", {})
    required = ("SOURCE", "QUALITY", "BUILD", "IDENTITY", "PACKAGE", "INSTALL_E2E", "PROVENANCE", "LINEAGE", "CANDIDATE", "CERTIFICATION")
    if any(gates.get(key) is not True for key in required) or gates.get("RELEASE") is not False:
        raise ValueError("release spine gates are incomplete or RELEASE is self-asserted")
    refs = certification.get("run_refs", {})
    expected = ("candidate", "research_gate", "provenance", "lineage")
    if any(not str(refs.get(key, "")).isdigit() for key in expected):
        raise ValueError("release spine constituent workflow run references are missing")
    if str(refs["candidate"]) != str(candidate_run):
        raise ValueError("candidate run ID differs from certified release spine")
    return {f"{key}_run_id": str(refs[key]) for key in expected if key != "candidate"} | {
        "target_sha": target, "spine_run_id": str(spine_run),
        "distribution_manifest_sha256": manifest_hash, "platform_zip_sha256": archive_hash,
        "owner_setup_sha256": setup_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--spine", type=Path, required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--spine-run-id", required=True)
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.artifact_dir, args.spine, args.target_sha, args.spine_run_id, args.candidate_run_id)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"RELEASE_AUTHORITY_VALIDATION=FAIL: {exc}")
        return 1
    print("RELEASE_AUTHORITY_VALIDATION=PASS")
    for key, value in result.items():
        print(f"{key}={value}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            for key, value in result.items():
                stream.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
