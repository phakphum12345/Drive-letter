import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_release_authority import verify


class ReleaseAuthorityValidationTest(unittest.TestCase):
    def fixture(self, root: Path, spine: Path):
        target = "a" * 40
        archive = root / f"Research-OS-Platform-Windows-x64-{target}.zip"
        setup = root / "Research-OS-Owner-Special-Setup-1.3.1-x64.exe"
        archive.write_bytes(b"platform archive")
        setup.write_bytes(b"installer")
        manifest = {
            "schema_version": 1, "distribution": "Research OS Unified Windows",
            "source_sha": target, "file_count": 1,
            "files": [{"path": "app/app.exe", "sha256": "b" * 64, "bytes": 1}],
        }
        manifest_path = root / "DISTRIBUTION_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        (root / "DISTRIBUTION_MANIFEST.sha256").write_text(f"{manifest_hash}  DISTRIBUTION_MANIFEST.json")
        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
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
        certification = {
            "schema": "research-os.release-spine.v1", "immutable": True, "commit": target, "run_id": 900,
            "gates": {key: True for key in ("SOURCE", "QUALITY", "BUILD", "IDENTITY", "PACKAGE", "INSTALL_E2E", "PROVENANCE", "LINEAGE", "CANDIDATE", "CERTIFICATION")},
            "run_refs": {"candidate": "100", "research_gate": "101", "provenance": "102", "lineage": "103"},
        }
        certification["gates"]["RELEASE"] = False
        certification["manifest_sha256"] = hashlib.sha256(json.dumps(certification, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        spine.write_text(json.dumps(certification), encoding="utf-8")
        return target

    def test_accepts_complete_exact_sha_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"
            root.mkdir()
            spine = Path(temp) / "spine.json"
            target = self.fixture(root, spine)
            result = verify(root, spine, target, "900", "100")
            self.assertEqual(result["target_sha"], target)
            self.assertEqual(result["provenance_run_id"], "102")

    def test_rejects_release_self_assertion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"
            root.mkdir()
            spine = Path(temp) / "spine.json"
            target = self.fixture(root, spine)
            data = json.loads(spine.read_text())
            data["gates"]["RELEASE"] = True
            unsigned = dict(data)
            unsigned.pop("manifest_sha256")
            data["manifest_sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            spine.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "RELEASE is self-asserted"):
                verify(root, spine, target, "900", "100")

    def test_rejects_target_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "candidate"
            root.mkdir()
            spine = Path(temp) / "spine.json"
            self.fixture(root, spine)
            with self.assertRaisesRegex(ValueError, "target SHA mismatch|target or product mismatch"):
                verify(root, spine, "c" * 40, "900", "100")


if __name__ == "__main__":
    unittest.main()
