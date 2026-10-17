from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "diagnose_windows_service_runtime.ps1"


class WindowsServiceRuntimeDiagnosticsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_diagnostic_script_exists_and_declares_versioned_evidence_contract(self) -> None:
        self.assertIn("research-os.windows-service-diagnostics/v1", self.source)
        self.assertIn("COLLECTED_NOT_CERTIFIED", self.source)
        self.assertIn("read_only = $true", self.source)

    def test_collects_service_process_socket_http_log_and_event_evidence(self) -> None:
        for marker in (
            "Win32_Service",
            "Win32_Process",
            "Get-NetTCPConnection",
            "research_os_api_health",
            "owner_friend_health",
            "Get-Content -LiteralPath $file.FullName -Tail $LogTailLines",
            "Get-WinEvent",
            "parent_process_id",
            "command_line",
            "SHARED_RUNTIME_IN_USE",
            "service_process_ownership",
            "SERVICE_PID_NOT_IN_INVENTORY",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_owner_friend_cleanup_scopes_processes_to_exact_entrypoint(self) -> None:
        installer = (
            ROOT.parent
            / "owner_special"
            / "scripts"
            / "install-owner-service.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("run_friend_service.py", installer)
        self.assertIn("CommandLine.IndexOf($entrypoint", installer)
        self.assertIn("[StringComparison]::OrdinalIgnoreCase", installer)
        self.assertIn(
            "The bundled interpreter is shared by API and Owner Friend",
            installer,
        )
        # A shared python.exe path must never be the sole process selector.
        self.assertNotIn(
            "return @(" + "Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {\n"
            "        $_.Name -ieq 'python.exe' -and $_.ExecutablePath -and\n"
            "        ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq $pythonPath)\n"
            "    })",
            installer,
        )

    def test_collector_does_not_stop_processes_or_mutate_services(self) -> None:
        forbidden = (
            "Stop-Process",
            "Stop-Service",
            "Start-Service",
            "Restart-Service",
            "Remove-Service",
            "sc.exe delete",
            "Set-Service",
            "New-Service",
            "Win32_Process).Terminate",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker.lower(), self.source.lower())

    def test_process_command_line_redacts_common_inline_credentials(self) -> None:
        self.assertIn("Protect-CommandLine", self.source)
        self.assertIn("<REDACTED>", self.source)
        self.assertNotIn("Get-ChildItem Env:", self.source)
        self.assertNotIn("Get-Item Env:", self.source)

    def test_optional_output_path_is_explicit_and_report_does_not_claim_pass(self) -> None:
        self.assertIn("if ($OutputPath)", self.source)
        self.assertIn("DIAGNOSTIC_STATUS=COLLECTED_NOT_CERTIFIED", self.source)
        self.assertNotIn("FINAL_GATE=PASS", self.source)
        self.assertNotIn("RELEASE_CERTIFIED=TRUE", self.source)


if __name__ == "__main__":
    unittest.main()
