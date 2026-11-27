#!/usr/bin/env python3
"""Fail-closed Authenticode verifier for a Research OS release candidate.

Requires osslsigncode on PATH and a CA bundle trusted by the release runner.
The build evidence is an additional binding, never a substitute for signature
verification of the actual PE bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def verify_signature(path: Path, ca_file: Path) -> tuple[str, str]:
    result = subprocess.run(
        ["osslsigncode", "verify", "-verbose", "-in", str(path), "-CAfile", str(ca_file), "-TSA-CAfile", str(ca_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0:
        raise ValueError(f"Authenticode verification failed for {path.name}: {detail[-3000:]}")
    subject = re.search(r"^\s*Subject:\s*(.+)$", detail, re.IGNORECASE | re.MULTILINE)
    issuer = re.search(r"^\s*Issuer:\s*(.+)$", detail, re.IGNORECASE | re.MULTILINE)
    if not subject or not issuer:
        raise ValueError(f"Authenticode signer identity is missing for {path.name}")
    subject_value, issuer_value = subject.group(1).strip(), issuer.group(1).strip()
    if subject_value == issuer_value:
        raise ValueError(f"Self-issued/self-signed certificate is forbidden for {path.name}")
    return subject_value, issuer_value


def verify_release(root: Path, target_sha: str, ca_file: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
        raise ValueError("target SHA must be a full lowercase 40-character commit")
    if not ca_file.is_file():
        raise ValueError(f"trusted CA bundle is missing: {ca_file}")
    evidence_matches = list(root.rglob("CODE_SIGNING_EVIDENCE.json"))
    if len(evidence_matches) != 1:
        raise ValueError(f"expected exactly one external CODE_SIGNING_EVIDENCE.json, found {len(evidence_matches)}")
    evidence_path = evidence_matches[0]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    if not isinstance(evidence, dict) or evidence.get("schema") != "research-os.authenticode-evidence.v1":
        raise ValueError("code-signing evidence schema mismatch")
    if evidence.get("source_sha") != target_sha or evidence.get("status") != "PASS":
        raise ValueError("code-signing evidence is not PASS for the exact target SHA")
    signer = evidence.get("signer", {})
    if not isinstance(signer, dict) or not signer.get("subject") or not signer.get("issuer"):
        raise ValueError("signer identity is incomplete")
    if signer["subject"] == signer["issuer"]:
        raise ValueError("self-issued/self-signed signing certificate is forbidden")

    setups = list(root.rglob("Research-OS-Owner-Special-Setup-*-x64.exe"))
    archives = list(root.rglob(f"Research-OS-Platform-Windows-x64-{target_sha}.zip"))
    if len(setups) != 1 or len(archives) != 1:
        raise ValueError("expected exactly one setup executable and exact-SHA platform ZIP")
    setup_evidence = evidence.get("setup", {})
    if (not isinstance(setup_evidence, dict) or
            setup_evidence.get("name") != setups[0].name or
            setup_evidence.get("sha256") != hashlib.sha256(setups[0].read_bytes()).hexdigest()):
        raise ValueError("setup signature evidence does not bind the exact installer bytes")

    setup_identity = verify_signature(setups[0], ca_file)
    verified = [setups[0].name]
    signer_identities = [setup_identity]
    with zipfile.ZipFile(archives[0]) as package:
        executable_names = sorted(
            info.filename for info in package.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".exe")
        )
        if not executable_names:
            raise ValueError("platform ZIP contains no executable payload")
        if evidence.get("package_executable_count") != len(executable_names):
            raise ValueError("package executable count differs from signed build evidence")
        try:
            package_evidence = json.loads(package.read("CODE_SIGNING_EVIDENCE.json").decode("utf-8-sig"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("embedded package Authenticode evidence is missing or invalid") from exc
        package_signer = package_evidence.get("signer", {}) if isinstance(package_evidence, dict) else {}
        package_executables = package_evidence.get("executables", []) if isinstance(package_evidence, dict) else []
        if (not isinstance(package_evidence, dict) or
                package_evidence.get("schema") != "research-os.package-authenticode.v1" or
                package_evidence.get("source_sha") != target_sha or
                package_evidence.get("status") != "PASS" or
                package_evidence.get("executable_count") != len(executable_names) or
                not isinstance(package_signer, dict) or
                package_signer.get("subject") != signer["subject"] or
                package_signer.get("issuer") != signer["issuer"] or
                not isinstance(package_executables, list) or
                len(package_executables) != len(executable_names)):
            raise ValueError("embedded package Authenticode evidence is not PASS for the exact executable inventory")
        with tempfile.TemporaryDirectory(prefix="research-os-authenticode-") as temp:
            temp_root = Path(temp)
            for index, name in enumerate(executable_names):
                payload = package.read(name)
                if not payload.startswith(b"MZ"):
                    raise ValueError(f"manifested .exe is not a Windows PE image: {name}")
                candidate = temp_root / f"{index:04d}.exe"
                candidate.write_bytes(payload)
                signer_identities.append(verify_signature(candidate, ca_file))
                verified.append(name)
    if len(set(signer_identities)) != 1:
        raise ValueError("release executables do not share one consistent CA signer identity")
    return {
        "status": "PASS",
        "target_sha": target_sha,
        "verified_executable_count": len(verified),
        "verified_executables": verified,
        "signer_subject": signer_identities[0][0],
        "signer_issuer": signer_identities[0][1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--ca-file", type=Path, default=Path("/etc/ssl/certs/ca-certificates.crt"))
    args = parser.parse_args()
    try:
        result = verify_release(args.artifact_dir, args.target_sha, args.ca_file)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"AUTHENTICODE_RELEASE_GATE=FAIL: {exc}", file=sys.stderr)
        return 1
    print("AUTHENTICODE_RELEASE_GATE=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
