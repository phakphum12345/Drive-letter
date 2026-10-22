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
