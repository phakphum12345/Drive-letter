import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.validate_release_authority import verify


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class ReleaseAuthorityValidationTest(unittest.TestCase):
    def fixture(self, root: Path, spine: Path, provenance: Path):
        target = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        source = subprocess.check_output(["git", "rev-parse", f"{target}^"], text=True).strip()
        tree = subprocess.check_output(["git", "show", "-s", "--format=%T", target], text=True).strip()
        archive = root / f"Research-OS-Platform-Windows-x64-{target}.zip"
        setup = root / "Research-OS-Owner-Special-Setup-1.3.1-x64.exe"
        owner_exe = b"owner executable"
        identity = {"passed": True, "commit": target, "sha256": hashlib.sha256(owner_exe).hexdigest()}
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("app/app.exe", b"app")
            package.writestr("owner_special/app/research_os_owner_special.exe", owner_exe)
            package.writestr("owner_special/app/OWNER_BUILD_IDENTITY.json", json.dumps(identity))
        setup.write_bytes(b"installer")
        files = [
            {"path": "app/app.exe", "sha256": hashlib.sha256(b"app").hexdigest(), "bytes": 3},
            {"path": "owner_special/app/research_os_owner_special.exe", "sha256": hashlib.sha256(owner_exe).hexdigest(), "bytes": len(owner_exe)},
            {"path": "owner_special/app/OWNER_BUILD_IDENTITY.json", "sha256": hashlib.sha256(json.dumps(identity).encode()).hexdigest(), "bytes": len(json.dumps(identity).encode())},
        ]
        manifest = {"schema_version": 1, "distribution": "Research OS Unified Windows", "source_sha": target, "file_count": len(files), "files": files}
        manifest_path = root / "DISTRIBUTION_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        manifest_sidecar = root / "DISTRIBUTION_MANIFEST.sha256"
        manifest_sidecar.write_text(f"{manifest_hash}  DISTRIBUTION_MANIFEST.json")
        with zipfile.ZipFile(archive, "a") as package:
            package.writestr("DISTRIBUTION_MANIFEST.json", manifest_path.read_bytes())
            package.writestr("DISTRIBUTION_MANIFEST.sha256", manifest_sidecar.read_bytes())
        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        (root / (archive.name + ".sha256")).write_text(f"{archive_hash}  {archive.name}")
        setup_hash = hashlib.sha256(setup.read_bytes()).hexdigest()
        release = {
            "source_sha": target, "release_authority": "FINAL_GATE", "installer_role": "OWNER_SPECIAL",
            "installation_payload": "RESEARCH_OS_PLATFORM_ZIP", "platform_zip": archive.name,
            "platform_zip_sha256": archive_hash, "owner_special_setup": setup.name,
            "owner_special_setup_sha256": setup_hash,
        }
        (root / "RELEASE_EVIDENCE.json").write_text(json.dumps(release), encoding="utf-8")
        install = {
            "source_sha": target, "release_authority": "FINAL_GATE", "manifest_sha256": manifest_hash,
            "manifest_hash_file": f"{manifest_hash}  DISTRIBUTION_MANIFEST.json",
            "platform_zip": archive.name, "platform_zip_sha256": archive_hash,
            "installer": setup.name, "installer_sha256": setup_hash, "checks": {"install": True, "uninstall": True},
        }
        (root / "WINDOWS_INSTALL_E2E_EVIDENCE.json").write_text(json.dumps(install), encoding="utf-8")

        provenance.mkdir()
        evidence = {
            "schema_version": "1.0", "evidence_id": f"EV-TARGET-{target[:12]}",
            "workflow": "Provenance Evidence Gate", "run_id": "102",
            "target_commit": target, "source_commit": source, "commit_tree": tree,
            "changed_paths": [], "recorded_at": "2026-01-01T00:00:00Z",
        }
        evidence_path = provenance / "TARGET_BOUND_EVIDENCE.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        attestation = {
            "entry_id": f"AT-TARGET-{target[:12]}", "sequence": 1, "recorded_at": evidence["recorded_at"],
            "actor_id": "github-actions:provenance-evidence-gate", "action": "attest_target_generation",
            "subject_type": "git-commit", "subject_id": target,
            "input_hashes": {"source_commit": {"algorithm": "git-sha1", "digest": source, "subject": "git-commit"}},
            "output_hashes": {
                "target_commit": {"algorithm": "git-sha1", "digest": target, "subject": "git-commit"},
                "evidence": {"algorithm": "sha256", "digest": evidence_hash, "subject": "artifact:target-provenance/TARGET_BOUND_EVIDENCE.json"},
            },
            "evidence_type": "attestation",
            "evidence": {"attestation_id": f"AT-TARGET-{target[:12]}", "subject_id": target,
                         "attester_id": "github-actions:provenance-evidence-gate", "statement": "Exact target observed.",
                         "evidence_ids": [], "issued_at": evidence["recorded_at"]},
            "previous_entry_hash": None,
        }
        attestation["entry_hash"] = hashlib.sha256(b"provenance-entry-v1\x00" + canonical(attestation)).hexdigest()
        ledger = {"contract_version": "1.1.0", "entries": [attestation]}
        (provenance / "TARGET_BOUND_PROVENANCE.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        roots = {
            "schema_version": "1.0", "target_commit": target, "source_commit": source,
            "evidence_root": evidence_hash, "provenance_root": hashlib.sha256(canonical(ledger)).hexdigest(),
            "evidence_file": "target-provenance/TARGET_BOUND_EVIDENCE.json",
            "provenance_file": "target-provenance/TARGET_BOUND_PROVENANCE.json",
        }
        (provenance / "TARGET_BOUND_ROOTS.json").write_text(json.dumps(roots, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (provenance / "TARGET_BOUND_VERIFICATION.json").write_text(json.dumps({"status": "PASS", "errors": [], "roots_verified": True}), encoding="utf-8")

        certification = {
            "schema": "research-os.release-spine.v1", "immutable": True, "commit": target, "run_id": 900,
            "gates": {key: True for key in ("SOURCE", "QUALITY", "BUILD", "IDENTITY", "PACKAGE", "INSTALL_E2E", "PROVENANCE", "LINEAGE", "CANDIDATE", "CERTIFICATION")},
            "run_refs": {"candidate": "100", "research_gate": "101", "provenance": "102", "lineage": "103"},
        }
        certification["gates"]["RELEASE"] = False
        certification["manifest_sha256"] = hashlib.sha256(canonical(certification)).hexdigest()
        spine.write_text(json.dumps(certification), encoding="utf-8")
        return target


    def refresh_archive_bindings(self, root: Path, archive: Path, refresh_manifest: bool = False):
        manifest_path = root / "DISTRIBUTION_MANIFEST.json"
        manifest_hash_path = root / "DISTRIBUTION_MANIFEST.sha256"
        if refresh_manifest:
            manifest = json.loads(manifest_path.read_text())
            with zipfile.ZipFile(archive) as package:
                for item in manifest["files"]:
                    payload = package.read(item["path"])
                    item["sha256"] = hashlib.sha256(payload).hexdigest()
                    item["bytes"] = len(payload)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            manifest_hash_path.write_text(f"{manifest_hash}  DISTRIBUTION_MANIFEST.json")

        rebuilt = archive.with_suffix(".rebuilt.zip")
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(rebuilt, "w") as destination:
            for info in source.infolist():
                if info.is_dir() or info.filename in {"DISTRIBUTION_MANIFEST.json", "DISTRIBUTION_MANIFEST.sha256"}:
                    continue
                destination.writestr(info, source.read(info.filename))
            destination.writestr("DISTRIBUTION_MANIFEST.json", manifest_path.read_bytes())
            destination.writestr("DISTRIBUTION_MANIFEST.sha256", manifest_hash_path.read_bytes())
        archive.write_bytes(rebuilt.read_bytes())
        rebuilt.unlink()

        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        (root / (archive.name + ".sha256")).write_text(f"{archive_hash}  {archive.name}")
        release_path = root / "RELEASE_EVIDENCE.json"
        release = json.loads(release_path.read_text())
        release["platform_zip_sha256"] = archive_hash
        release_path.write_text(json.dumps(release), encoding="utf-8")
        install_path = root / "WINDOWS_INSTALL_E2E_EVIDENCE.json"
        install = json.loads(install_path.read_text())
        install["platform_zip_sha256"] = archive_hash
        if refresh_manifest:
            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            install["manifest_sha256"] = manifest_hash
            install["manifest_hash_file"] = f"{manifest_hash}  DISTRIBUTION_MANIFEST.json"
        install_path.write_text(json.dumps(install), encoding="utf-8")

    def verify_fixture(self, root, spine, provenance, target):
        return verify(root, spine, target, "900", "100", provenance, "102")

    def test_accepts_complete_exact_sha_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"
            provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            result = self.verify_fixture(root, spine, provenance, target)
            self.assertEqual(result["target_sha"], target)
            self.assertEqual(result["provenance_run_id"], "102")

    def test_rejects_release_self_assertion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            data = json.loads(spine.read_text()); data["gates"]["RELEASE"] = True
            unsigned = dict(data); unsigned.pop("manifest_sha256")
            data["manifest_sha256"] = hashlib.sha256(canonical(unsigned)).hexdigest()
            spine.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "RELEASE is self-asserted"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_unmanifested_zip_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            archive = next(root.glob("Research-OS-Platform-Windows-x64-*.zip"))
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr("unmanifested/payload.bin", b"unexpected")
            self.refresh_archive_bindings(root, archive)
            with self.assertRaisesRegex(ValueError, "inventory differs from manifest"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_duplicate_zip_file_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            archive = next(root.glob("Research-OS-Platform-Windows-x64-*.zip"))
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr("app/app.exe", b"duplicate")
            self.refresh_archive_bindings(root, archive)
            with self.assertRaisesRegex(ValueError, "duplicate file entries"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_tampered_package_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            archive = next(root.glob("Research-OS-Platform-Windows-x64-*.zip"))
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("app/app.exe", b"tampered")
            self.refresh_archive_bindings(root, archive)
            with self.assertRaisesRegex(ValueError, "distribution ZIP file digest mismatch: app/app.exe"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_missing_provenance_run_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            data = json.loads(spine.read_text()); data["run_refs"]["provenance"] = ""
            unsigned = dict(data); unsigned.pop("manifest_sha256")
            data["manifest_sha256"] = hashlib.sha256(canonical(unsigned)).hexdigest()
            spine.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "run references are missing"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_owner_executable_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            archive = next(root.glob("Research-OS-Platform-Windows-x64-*.zip"))
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("app/app.exe", b"app")
                package.writestr("owner_special/app/research_os_owner_special.exe", b"altered")
                package.writestr("owner_special/app/OWNER_BUILD_IDENTITY.json", json.dumps({"passed": True, "commit": target, "sha256": "0" * 64}))
            self.refresh_archive_bindings(root, archive, refresh_manifest=True)
            with self.assertRaisesRegex(ValueError, "Owner build identity commit/EXE SHA256 provenance mismatch"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_provenance_root_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            target = self.fixture(root, spine, provenance)
            evidence = provenance / "TARGET_BOUND_EVIDENCE.json"
            data = json.loads(evidence.read_text()); data["target_commit"] = "f" * 40
            evidence.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "provenance evidence target/source commit mismatch"):
                self.verify_fixture(root, spine, provenance, target)

    def test_rejects_target_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"; root.mkdir()
            spine = Path(temp) / "spine.json"; provenance = Path(temp) / "provenance"
            self.fixture(root, spine, provenance)
            with self.assertRaisesRegex(ValueError, "target or product mismatch"):
                self.verify_fixture(root, spine, provenance, "c" * 40)


if __name__ == "__main__":
    unittest.main()
