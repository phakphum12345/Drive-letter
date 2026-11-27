from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.verify_windows_authenticode_release import verify_release, verify_signature


class AuthenticodeReleaseGateTests(unittest.TestCase):
    def fixture(self, root: Path):
        target = "a" * 40
        ca = root / "ca.pem"
        ca.write_text("test CA bundle", encoding="utf-8")
        setup = root / "Research-OS-Owner-Special-Setup-3.0.0-x64.exe"
        setup.write_bytes(b"MZsetup")
        archive = root / f"Research-OS-Platform-Windows-x64-{target}.zip"
        package_evidence = {
            "schema": "research-os.package-authenticode.v1",
            "source_sha": target,
            "status": "PASS",
            "executable_count": 2,
        }
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("app/research_os_flutter.exe", b"MZapp")
            package.writestr("service_host/ResearchOS.ServiceHost.exe", b"MZservice")
            package.writestr("CODE_SIGNING_EVIDENCE.json", json.dumps(package_evidence))
        evidence = {
            "schema": "research-os.authenticode-evidence.v1",
            "source_sha": target,
            "status": "PASS",
            "signer": {"subject": "CN=Research OS Publisher", "issuer": "CN=Public CA"},
            "package_executable_count": 2,
            "setup": {"name": setup.name, "sha256": __import__("hashlib").sha256(setup.read_bytes()).hexdigest()},
        }
        (root / "CODE_SIGNING_EVIDENCE.json").write_text(json.dumps(evidence), encoding="utf-8")
        return target, ca

    def test_release_workflow_requires_authenticode_before_publish(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
        gate = workflow.index("Require valid CA-trusted Authenticode signatures before publication")
        publish = workflow.index("Create GitHub Release")
        self.assertLess(gate, publish)
        self.assertIn("if: ${{ inputs.publish == true }}", workflow[gate:publish])
        self.assertIn("osslsigncode", workflow[gate:publish])
        self.assertIn("tools/verify_windows_authenticode_release.py", workflow[gate:publish])

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_accepts_exact_sha_signed_setup_and_every_zip_exe(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            verify_signature.return_value = ("CN=Research OS Publisher", "CN=Public CA")
            result = verify_release(root, target, ca)
            self.assertEqual("PASS", result["status"])
            self.assertEqual(3, result["verified_executable_count"])
            self.assertEqual(3, verify_signature.call_count)

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_mixed_signer_identities(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            verify_signature.side_effect = [
                ("CN=Publisher A", "CN=Public CA"),
                ("CN=Publisher B", "CN=Public CA"),
                ("CN=Publisher A", "CN=Public CA"),
            ]
            with self.assertRaisesRegex(ValueError, "one consistent CA signer identity"):
                verify_release(root, target, ca)

    @patch("tools.verify_windows_authenticode_release.subprocess.run")
    def test_signature_verifier_requires_trusted_non_self_issued_signer(self, run):
        from subprocess import CompletedProcess
        run.return_value = CompletedProcess(
            args=[], returncode=0,
            stdout="Subject: /CN=Publisher\\nIssuer: /CN=Public CA\\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exe = root / "test.exe"; exe.write_bytes(b"MZ")
            ca = root / "ca.pem"; ca.write_text("CA", encoding="utf-8")
            identity = verify_signature(exe, ca)
            self.assertEqual(("/CN=Publisher", "/CN=Public CA"), identity)

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_missing_signing_evidence(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            (root / "CODE_SIGNING_EVIDENCE.json").unlink()
            with self.assertRaisesRegex(ValueError, "expected exactly one external CODE_SIGNING_EVIDENCE.json"):
                verify_release(root, target, ca)
            verify_signature.assert_not_called()

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_non_pass_evidence(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            path = root / "CODE_SIGNING_EVIDENCE.json"
            data = json.loads(path.read_text())
            data["status"] = "NOT_SIGNED"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "not PASS"):
                verify_release(root, target, ca)
            verify_signature.assert_not_called()

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_self_signed_identity(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            path = root / "CODE_SIGNING_EVIDENCE.json"
            data = json.loads(path.read_text())
            data["signer"]["issuer"] = data["signer"]["subject"]
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "self-issued"):
                verify_release(root, target, ca)
            verify_signature.assert_not_called()

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_setup_evidence_hash_mismatch(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            path = root / "CODE_SIGNING_EVIDENCE.json"
            data = json.loads(path.read_text())
            data["setup"]["sha256"] = "0" * 64
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "does not bind the exact installer bytes"):
                verify_release(root, target, ca)
            verify_signature.assert_not_called()

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_package_executable_count_mismatch(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            path = root / "CODE_SIGNING_EVIDENCE.json"
            data = json.loads(path.read_text())
            data["package_executable_count"] = 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "count differs"):
                verify_release(root, target, ca)
            verify_signature.assert_called_once()

    @patch("tools.verify_windows_authenticode_release.verify_signature")
    def test_rejects_invalid_pe_even_if_extension_is_exe(self, verify_signature):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, ca = self.fixture(root)
            archive = root / f"Research-OS-Platform-Windows-x64-{target}.zip"
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr("bad.exe", b"not a PE")
            with self.assertRaisesRegex(ValueError, "not a Windows PE"):
                verify_release(root, target, ca)


if __name__ == "__main__":
    unittest.main()
