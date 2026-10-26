from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FlexiblePortContractTests(unittest.TestCase):
    def test_installer_selects_and_persists_available_loopback_port(self) -> None:
        service = (ROOT / "v3" / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        self.assertIn("Find-AvailableLoopbackPort", service)
        self.assertIn("Test-LoopbackPortAvailable", service)
        self.assertIn("host = '127.0.0.1'", service)
        self.assertIn("port = $Port", service)
        self.assertIn("service.json", service)
        self.assertIn("UTF8Encoding]::new($false)", service)

    def test_service_cleanup_preserves_ownership_and_process_identity_checks(self) -> None:
        service = (ROOT / "v3" / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")
        self.assertIn("Assert-V3ServiceOwnership", service)
        self.assertIn("Test-V3ProcessDescendant", service)
        self.assertIn("CreationDate", service)
        self.assertIn("$sameProcess", service)
        self.assertIn("Stop-Process -Id ([int]$snapshot.ProcessId)", service)
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

    def test_flutter_reads_saved_port_but_forces_loopback(self) -> None:
        main = (ROOT / "v3" / "flutter_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("service.json", main)
        self.assertIn("127.0.0.1:$port", main)
        self.assertNotIn("decoded['host']", main)

    def test_candidate_e2e_reserves_default_port_and_checks_fallback(self) -> None:
        candidate = (ROOT / "v3" / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("$defaultPortReservation", candidate)
        self.assertIn("default_port_fallback", candidate)
        self.assertIn("Installer did not select fallback port", candidate)
        self.assertIn("service.json", candidate)


if __name__ == "__main__":
    unittest.main()
