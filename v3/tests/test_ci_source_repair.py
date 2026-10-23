from __future__ import annotations

import unittest

from scripts.repair_v3_ci_sources import (
    repair_candidate,
    repair_service_smoke,
    repair_storage_smoke,
    repair_workflow,
)


class V3CISourceRepairTests(unittest.TestCase):
    def test_workflow_shell_and_contract_repairs_are_idempotent(self) -> None:
        source = (
            "    timeout-minutes: 45\n    strategy:\n"
            "          if ($LASTEXITCODE -ne 0) { throw 'V3 Clean unit tests failed' }\n"
            '$master = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v3/master?tasks=30" -TimeoutSec 5\n'
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\n"
        )
        repaired = repair_workflow(source)
        self.assertIn("        shell: bash", repaired)
        self.assertNotIn("$LASTEXITCODE", repaired)
        self.assertIn("unified-master-orchestrator-v3-full", repaired)
        self.assertIn("'6^6'", repaired)
        self.assertIn("-ne 46656", repaired)
        self.assertIn('?tasks=217"', repaired)
        self.assertNotIn('?tasks=30"', repaired)
        self.assertEqual(repair_workflow(repaired), repaired)

    def test_workflow_audit_handles_windows_crlf_checkout(self) -> None:
        source = (
            "    timeout-minutes: 45\r\n    strategy:\r\n"
            '$master = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v3/master?tasks=30" -TimeoutSec 5\r\n'
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\r\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\r\n"
        )
        repaired = repair_workflow(source)
        self.assertIn("        shell: bash", repaired)
        self.assertIn('?tasks=217"', repaired)
        self.assertNotIn('?tasks=30"', repaired)
        self.assertIn("\r\n", repaired)
        self.assertNotIn("\n", repaired.replace("\r\n", ""))
        self.assertEqual(repair_workflow(repaired), repaired)

    def test_candidate_validation_requests_capacity_for_max_profile(self) -> None:
        source = (
            "Invoke-RestMethod -Uri http://127.0.0.1:$port/v3/master?tasks=30\n"
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\n"
        )
        repaired = repair_candidate(source)
        self.assertIn("/v3/master?tasks=217", repaired)
        self.assertIn("'6^6'", repaired)
        self.assertEqual(repair_candidate(repaired), repaired)

    def test_candidate_installer_failure_emits_sanitized_log_diagnostics(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("installer-logs", source)
        self.assertIn("Select-Object -Last 80", source)
        self.assertIn("[REDACTED]", source)
        self.assertIn("setup-$stage.log", source)

    def test_candidate_upgrade_waits_for_its_app_process_to_release_files(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("function Stop-CandidateApp", source)
        self.assertIn("CloseMainWindow()", source)
        self.assertIn("WaitForExit(10000)", source)
        self.assertIn("WaitForExit(15000)", source)
        self.assertIn("Refusing to stop app PID", source)
        self.assertIn("Stop-CandidateApp $app", source)

    def test_windows_service_cleanup_waits_for_service_and_listener(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "v3-clean-core.yml").read_text(encoding="utf-8")
        self.assertIn("WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))", source)
        self.assertIn("$attempt -lt 120", source)
        self.assertIn("OwningProcess", source)
        self.assertIn("$serviceListenerPids", source)
        self.assertIn("$serviceHostPid", source)
        self.assertIn("ParentProcessId", source)
        self.assertIn("Get-CimInstance Win32_Process", source)
        self.assertIn("$imagePath -ieq $expectedPython", source)
        self.assertIn("$commandLine.IndexOf($scriptPath", source)
        self.assertIn("Refusing to stop listener PID", source)
        self.assertIn("Stop-Process -Id $listenerPid -Force", source)
        self.assertIn("do not kill", source.lower())

    def test_windows_flutter_build_uses_valid_shared_package_target(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "v3-clean-core.yml").read_text(encoding="utf-8")
        self.assertIn("$packageTarget = Join-Path (Split-Path $work -Parent) 'packages\\research_os_contracts'", source)
        self.assertNotIn("Split-Path (Split-Path $work -Parent) -Parent", source)

    def test_service_host_signals_worker_cancellation_before_child_cleanup(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "windows_service" / "Program.cs").read_text(encoding="utf-8")
        stop = source.split("public override async Task StopAsync(CancellationToken cancellationToken)", 1)[1]
        stop = stop.split("public override void Dispose()", 1)[0]
        self.assertLess(stop.index("await base.StopAsync(cancellationToken)"), stop.index("await StopChildProcessAsync(CancellationToken.None)"))
        self.assertIn("ExecuteAsync owns the", stop)
        self.assertIn("worker stopped", stop)

    def test_service_shutdown_failure_records_lifecycle_diagnostics(self) -> None:
        from pathlib import Path

        service = (Path(__file__).resolve().parents[1] / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        candidate = (Path(__file__).resolve().parents[1] / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("service-lifecycle.log", service)
        self.assertIn("Remove-V3Service FAILED", service)
        self.assertIn("Service PID wait completed", service)
        self.assertIn("$lifecycleLog", candidate)
        self.assertIn("Service lifecycle diagnostics (sanitized)", candidate)

    def test_installer_waits_for_service_host_process_before_replacing_files(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        self.assertIn("$servicePid = if ($serviceInfo) { [int]$serviceInfo.ProcessId } else { 0 }", source)
        self.assertIn("$serviceProcessExited", source)
        self.assertIn("Win32_Process -Filter \"ProcessId=$servicePid\"", source)
        self.assertIn("$serviceProcessCreationDate", source)
        self.assertIn("$sameOwnedProcess", source)
        self.assertIn("$serviceStopped", source)
        self.assertIn("Stop-Process -Id $servicePid -Force", source)
        self.assertIn("stopped-state process identity could not be safely verified", source)
        self.assertIn("$serviceChildSnapshots", source)
        self.assertIn("$serviceEntrypointFullPath", source)
        self.assertIn("Stop-Process -Id ([int]$snapshot.ProcessId) -Force", source)
        self.assertIn("Refusing to stop captured child PID", source)
        self.assertIn("Captured child PID", source)
        self.assertIn("$attempt -lt 120", source)

    def test_service_smoke_bootstraps_v3_package_root(self) -> None:
        source = "import os\nimport tempfile\nfrom pathlib import Path\n\nfrom research_os_v3 import DataLayout\n"
        repaired = repair_service_smoke(source)
        self.assertIn("import sys", repaired)
        self.assertIn("PROJECT_ROOT = Path(__file__).resolve().parents[1]", repaired)
        self.assertIn("sys.path.insert(0, str(PROJECT_ROOT))", repaired)
        self.assertEqual(repair_service_smoke(repaired), repaired)

    def test_storage_evidence_uses_logical_scopes_not_relative_to(self) -> None:
        source = (
            '            "user_a_scope": str(alice_again.root.relative_to(second.root)),\n'
            '            "user_b_scope": str(bob_again.root.relative_to(second.root)),'
        )
        repaired = repair_storage_smoke(source)
        self.assertIn('"user_a_scope": "users/alice/profiles/default"', repaired)
        self.assertIn('"user_b_scope": "users/bob/profiles/default"', repaired)
        self.assertNotIn(".relative_to(", repaired)
        self.assertEqual(repair_storage_smoke(repaired), repaired)

    def test_audit_fails_closed_when_contract_assertions_are_missing(self) -> None:
        with self.assertRaises(ValueError):
            repair_candidate("Write-Output 'no contract assertion'")
        with self.assertRaises(ValueError):
            repair_workflow("    defaults:\n      run:\n        shell: bash\n")
        with self.assertRaises(ValueError):
            repair_storage_smoke("payload = {}")

    def test_candidate_contract_matches_full_implementation(self) -> None:
        source = (
            "Invoke-RestMethod -Uri http://127.0.0.1:$port/v3/master?tasks=30\n"
            "if ($master.contract -ne 'unified-master-orchestrator-v3-clean') {}\n"
            "if ($master.scale -ne '6^3' -or $capacity -ne 216) {}\n"
        )
        repaired = repair_candidate(source)
        self.assertIn("/v3/master?tasks=217", repaired)
        self.assertIn("unified-master-orchestrator-v3-full", repaired)
        self.assertIn("'6^6'", repaired)
        self.assertIn("-ne 46656", repaired)
        self.assertEqual(repair_candidate(repaired), repaired)

if __name__ == "__main__":
    unittest.main()
