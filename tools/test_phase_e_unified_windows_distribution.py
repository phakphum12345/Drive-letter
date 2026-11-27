"""Tests for Phase E unified Windows distribution governance."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools import validate_phase_e_unified_windows_distribution as validator


class PhaseEUnifiedWindowsDistributionTests(unittest.TestCase):
    def test_platform_matrix_is_required_by_distribution_contract(self) -> None:
        contract = validator.json.loads(
            validator.CONTRACT.read_text(encoding="utf-8")
        )
        self.assertIn(validator.PLATFORM_MATRIX_PATH, validator.REQUIRED_PACKAGE_PATHS)
        self.assertIn(validator.PLATFORM_MATRIX_PATH, contract["required_package_paths"])
        self.assertTrue(contract["install_e2e"]["platform_matrix_required"])

    def test_platform_matrix_source_is_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.assertEqual(
                (f"required Platform Matrix source is missing: {validator.PLATFORM_MATRIX_PATH}",),
                validator._platform_matrix_source_errors(root),
            )
            matrix = root / validator.PLATFORM_MATRIX_PATH
            matrix.parent.mkdir(parents=True)
            matrix.write_text("# Platform Matrix\\n", encoding="utf-8")
            self.assertEqual((), validator._platform_matrix_source_errors(root))

    def test_platform_matrix_is_staged_zipped_and_verified_after_install(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn(
            'Copy-Item "docs\\RESEARCH_OS_SYSTEM_PLATFORM_MATRIX.md" "$p\\docs\\RESEARCH_OS_SYSTEM_PLATFORM_MATRIX.md" -Force',
            workflow,
        )
        self.assertIn("'docs/RESEARCH_OS_SYSTEM_PLATFORM_MATRIX.md'", workflow)
        self.assertIn("'docs\\RESEARCH_OS_SYSTEM_PLATFORM_MATRIX.md'", workflow)
        self.assertIn("$matrixManifestEntry", workflow)
        self.assertIn("$checks['platform_matrix_manifest_binding'] = $true", workflow)

    def test_windows_distribution_validation_runs_api_identity_regressions(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("Install API regression test dependencies", workflow)
        self.assertIn("Run Research OS API identity and route regression tests", workflow)
        self.assertIn('python -m unittest discover -s tools/research_os_api -p "test_api.py" -v', workflow)
        self.assertIn("tools/research_os_api/contract-requirements.txt", workflow)

    def test_distribution_signing_is_explicit_and_fail_closed(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("CODE_SIGNING_EVIDENCE.json", validator.REQUIRED_PACKAGE_PATHS)
        self.assertIn("CODE_SIGNING_EVIDENCE.json", validator.json.loads(validator.CONTRACT.read_text(encoding="utf-8"))["required_package_paths"])
        self.assertIn("authorize_signing:", workflow)
        self.assertIn("inputs.authorize_signing == true", workflow)
        self.assertIn("environment:", workflow)
        self.assertIn("code-signing", workflow)
        self.assertIn("WINDOWS_CODESIGN_CERT_BASE64", workflow)
        self.assertIn("WINDOWS_CODESIGN_CERT_PASSWORD", workflow)
        self.assertIn("signtool verify /pa /all /v", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("Only the repository owner may authorize code signing.", workflow)
        self.assertIn('if [ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ]; then', workflow)
        self.assertIn("Self-issued/self-signed signing certificates are forbidden.", workflow)
        self.assertIn("CODE_SIGNING_EVIDENCE.json", workflow)
        self.assertIn("status = 'NOT_SIGNED'", workflow)
        self.assertIn("tools.test_verify_windows_authenticode_release", workflow)
        self.assertIn("Sign staged distribution executables with authorized CA certificate", workflow)
        self.assertIn("Sign and verify Owner Special Setup.exe", workflow)


    def test_installer_uses_compatible_zip_extraction_overload(self) -> None:
        installer = (
            validator.ROOT
            / "owner_special"
            / "installer"
            / "install-platform-zip.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "[System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $staging)",
            installer,
        )
        self.assertNotIn("Expand-Archive -LiteralPath $ZipPath", installer)

    def test_contract_reconciles(self) -> None:
        self.assertEqual((), validator.validate())

    def test_installer_e2e_is_bound(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("Installer install run uninstall E2E", workflow)
        self.assertIn("WINDOWS_INSTALL_E2E_EVIDENCE.json", workflow)

    def test_installer_e2e_requires_uninstall(self) -> None:
        original = validator.json.loads(
            validator.CONTRACT.read_text(encoding="utf-8")
        )
        original["install_e2e"]["uninstall_required"] = False
        with patch.object(validator, "json") as mocked_json:
            mocked_json.loads.return_value = original
            self.assertIn(
                "installer E2E invariant missing: uninstall_required",
                validator.validate(),
            )

    def test_distribution_cannot_replace_release_authority(self) -> None:
        original = validator.json.loads(
            validator.CONTRACT.read_text(encoding="utf-8")
        )
        original["authority"]["final_gate_remains_release_authority"] = False
        with patch.object(validator, "json") as mocked_json:
            mocked_json.loads.return_value = original
            self.assertIn(
                "authority invariant missing: final_gate_remains_release_authority",
                validator.validate(),
            )

    def test_uninstall_run_uses_native_powershell_and_unique_ids(self) -> None:
        installer = (
            validator.ROOT
            / "owner_special/installer/owner-special-platform.iss"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'Filename: "{sys}\\WindowsPowerShell\\v1.0\\powershell.exe"',
            installer,
        )
        self.assertIn(
            'Flags: 64bit runhidden waituntilterminated; '
            'RunOnceId: "ResearchOSOwnerFriendServiceUninstall"',
            installer,
        )
        self.assertIn(
            'Flags: 64bit runhidden waituntilterminated; '
            'RunOnceId: "ResearchOSServiceUninstall"',
            installer,
        )
    def test_windows_service_uses_canonical_api_entrypoint(self) -> None:
        source = (
            validator.ROOT
            / "tools"
            / "research_os_service"
            / "Program.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("server.py", source)
        self.assertNotIn("render_server.py", source)

    def test_installer_e2e_runs_for_relevant_pull_requests(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("  pull_request:", workflow)
        self.assertIn("      - main", workflow)
        self.assertIn('"tools/**"', workflow)

    def test_bundled_api_import_smoke_is_required(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("Bundled API import smoke test", workflow)
        self.assertIn("BUNDLED_API_IMPORT=PASS", workflow)
        self.assertIn("import server; print('BUNDLED_API_IMPORT=PASS')", workflow)

    def test_windows_installer_e2e_uses_explicit_mock_provider_without_changing_defaults(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("WINDOWS_INSTALLER_E2E_PROVIDER=mock", workflow)
        self.assertIn("RESEARCH_OS_PROVIDER=mock", workflow)
        self.assertIn("ResearchOSOwnerFriendService", workflow)
        self.assertIn("ResearchOSService", workflow)
        installer = (validator.ROOT / "owner_special/scripts/install-owner-service.ps1").read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('mock')][string]$TestProvider", installer)
        self.assertIn("$binary += ' --provider ' + $TestProvider", installer)
        self.assertIn("-TestProvider mock", workflow)
        self.assertIn("FRIEND_SERVICE_HOST_PATH=", workflow)
        self.assertIn("/owner/provider/health", workflow)
        self.assertIn("friend_memory_survives_service_restart", workflow)
        self.assertNotIn("Set-ItemProperty -Path $friendServiceKey -Name ImagePath", workflow)

    def test_api_readiness_requires_health_and_packaged_ui(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("/health", workflow)
        self.assertIn("apiHealth.status -eq 'ok'", workflow)
        self.assertIn("apiHealth.ui -eq $true", workflow)

    def test_owner_friend_lifecycle_health_monitor_tolerates_transient_latency(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("$consecutiveHealthFailures -ge 3", workflow)
        self.assertIn("http://127.0.0.1:8787/health' -TimeoutSec 5", workflow)
        self.assertIn("http://127.0.0.1:8787/health' -TimeoutSec 10", workflow)
        self.assertIn("$checks['owner_friend_lifecycle_api_final_health'] = $true", workflow)

    def test_service_start_failure_collects_runtime_and_event_diagnostics(self) -> None:
        workflow = validator._read_phase_e_workflow(validator.ROOT)
        self.assertIn("Get-WinEvent", workflow)
        self.assertIn("INSTALLED_API_IMPORT_EXIT=", workflow)
        self.assertIn("Research OS service did not reach Running state after install.", workflow)

    def test_workflow_must_bind_owner_special(self) -> None:
        with patch.object(validator, "_read_phase_e_workflow", return_value=""):
            self.assertIn(
                "Phase E workflow missing required marker: research_os_owner_special.exe",
                validator.validate(),
            )

    def test_final_gate_hook_is_required(self) -> None:
        with patch.object(validator, "_read_unified_final_gate", return_value=""):
            self.assertIn(
                "Unified Final Gate is missing the Phase E distribution test",
                validator.validate(),
            )

    def test_contract_requires_exact_sha(self) -> None:
        original = validator.json.loads(
            validator.CONTRACT.read_text(encoding="utf-8")
        )
        original["provenance"]["source_sha_required"] = False
        with patch.object(validator, "json") as mocked_json:
            mocked_json.loads.return_value = original
            self.assertIn(
                "provenance invariant missing: source_sha_required",
                validator.validate(),
            )


if __name__ == "__main__":
    unittest.main()
