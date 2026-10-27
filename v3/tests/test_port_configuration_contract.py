from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FlexiblePortContractTests(unittest.TestCase):
    def test_service_binds_os_assigned_port_and_publishes_atomic_registry(self) -> None:
        service = (ROOT / "v3" / "research_os_v3" / "service.py").read_text(encoding="utf-8")
        runner = (ROOT / "v3" / "scripts" / "run_service.py").read_text(encoding="utf-8")
        host = (ROOT / "v3" / "windows_service" / "Program.cs").read_text(encoding="utf-8")
        installer = (ROOT / "v3" / "scripts" / "v3-service.ps1").read_text(encoding="utf-8")

        self.assertIn("ThreadingHTTPServer((self.host, self.port), Handler)", service)
        self.assertIn("self.port = int(server.server_address[1])", service)
        self.assertIn("tempfile.mkstemp", runner)
        self.assertIn("os.replace(temp_path, registry_path)", runner)
        self.assertIn('"schema_version": 1', runner)
        self.assertIn('"process_id": os.getpid()', runner)
        self.assertIn("port is < 0 or > 65535", host)
        self.assertIn('RESEARCH_OS_V3_SERVICE_NAME', host)
        self.assertIn("$Port = 0", installer)
        self.assertIn("$registryReady", installer)
        self.assertIn("registry.host -eq '127.0.0.1'", installer)
        self.assertIn("Test-V3ProcessDescendant", installer)
        self.assertNotIn("Find-AvailableLoopbackPort -StartPort", installer)
        self.assertNotIn("Test-LoopbackPortAvailable", installer)

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

    def test_candidate_e2e_reserves_default_port_and_checks_os_assignment(self) -> None:
        candidate = (ROOT / "v3" / "scripts" / "candidate_validate.ps1").read_text(encoding="utf-8")
        self.assertIn("$defaultPortReservation", candidate)
        self.assertIn("default_port_fallback", candidate)
        self.assertIn("Installer did not select fallback port", candidate)
        self.assertIn("service.json", candidate)


if __name__ == "__main__":
    unittest.main()
