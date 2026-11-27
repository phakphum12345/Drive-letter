#!/usr/bin/env python3
"""Fail-closed Authenticode verifier for a Research OS release candidate.

Requires osslsigncode on PATH and a CA bundle trusted by the release runner.
The build evidence is an additional binding, never a substitute for signature
verification of the actual PE bytes.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def verify_signature(path: Path, ca_file: Path) -> None:
    result = subprocess.run(
        ["osslsigncode", "verify", "-verbose", "-in", str(path), "-CAfile", str(ca_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0:
        raise ValueError(f"Authenticode verification failed for {path.name}: {detail[-3000:]}")
    subject = re.search(r"^\\s*Subject:\\s*(.+)$", detail, re.IGNORECASE | re.MULTILINE)
    issuer = re.search(r"^\\s*Issuer:\\s*(.+)$", detail, re.IGNORECASE | re.MULTILINE)
    if not subject or not issuer:
        raise ValueError(f"Authenticode signer identity is missing for {path.name}")
    if subject.group(1).strip() == issuer.group(1).strip():
        raise ValueError(f"Self-issued/self-signed certificate is forbidden for {path.name}")


def verify_release(root: Path, target_sha: str, ca_file: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
        raise ValueError("target SHA must be a full lowercase 40-character commit")
    if not ca_file.is_file():
        raise ValueError(f"trusted CA bundle is missing: {ca_file}")
    evidence_path = root / "CODE_SIGNING_EVIDENCE.json"
    if not evidence_path.is_file():
        raise ValueError("CODE_SIGNING_EVIDENCE.json is missing")
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

    verify_signature(setups[0], ca_file)
    verified = [setups[0].name]
    with zipfile.ZipFile(archives[0]) as package:
        executable_names = sorted(
            info.filename for info in package.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".exe")
        )
        if not executable_names:
            raise ValueError("platform ZIP contains no executable payload")
        with tempfile.TemporaryDirectory(prefix="research-os-authenticode-") as temp:
            temp_root = Path(temp)
            for index, name in enumerate(executable_names):
                payload = package.read(name)
                if not payload.startswith(b"MZ"):
                    raise ValueError(f"manifested .exe is not a Windows PE image: {name}")
                candidate = temp_root / f"{index:04d}.exe"
                candidate.write_bytes(payload)
                verify_signature(candidate, ca_file)
                verified.append(name)
    return {
        "status": "PASS",
        "target_sha": target_sha,
        "verified_executable_count": len(verified),
        "verified_executables": verified,
        "signer_subject": signer["subject"],
        "signer_issuer": signer["issuer"],
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
