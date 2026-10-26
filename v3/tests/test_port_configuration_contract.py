from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FlexiblePortContractTests(unittest.TestCase):
    def test_installer_selects_available_loopback_port_and_records_it(self) -> None:
        service = (ROOT / "v3" / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        self.assertIn("Find-AvailableLoopbackPort", service)
        self.assertIn("Test-LoopbackPortAvailable", service)
        self.assertIn("host = '127.0.0.1'", service)
        self.assertIn("port = $selectedPort", service)
        self.assertIn("service.json", service)
        self.assertIn("UTF8Encoding]::new($false)", service)

    def test_stuck_service_host_cleanup_requires_stopped_service_and_same_process_identity(self) -> None:
        service = (ROOT / "v3" / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        self.assertIn("$serviceProcessCreationDate", service)
        self.assertIn("$sameOwnedProcess", service)
        self.assertIn("$serviceStopped", service)
        self.assertIn("Stop-Process -Id $servicePid -Force", service)
        self.assertIn("Win32_Service", service)
        self.assertIn("Targeted service-host cleanup completed", service)

        # The fallback may target only the captured service-host PID after the
        # SCM stopped-state and process identity checks; never kill by port.
        self.assertNotIn("Stop-Process -Id $listener.OwningProcess", service)

    def test_installer_never_kills_processes_by_port(self) -> None:
        paths = [
            ROOT / "v3" / "scripts" / "v3-service.ps1",
            ROOT / "v3" / "scripts" / "candidate_validate.ps1",
            ROOT / ".github" / "workflows" / "v3-candidate.yml",
            ROOT / ".github" / "workflows" / "v3-clean-core.yml",
        ]
        forbidden = "Stop-Process -Id $listener.OwningProcess"
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"))

    def test_flutter_reads_configured_port_but_keeps_loopback_binding(self) -> None:
        main = (ROOT / "v3" / "flutter_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("ResearchOSV3\\\\service.json", main)
        self.assertIn("return 'http://127.0.0.1:$port';", main)
        self.assertNotIn("decoded['host']", main)

    def test_candidate_e2e_exercises_default_port_conflict(self) -> None:
        candidate = (ROOT / "v3" / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("defaultPortReservation", candidate)
        self.assertIn("default_port_fallback", candidate)
        self.assertIn("Installer did not select a fallback port", candidate)


if __name__ == "__main__":
    unittest.main()
