from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "tools" / "research_os_agent"
PROGRAM = (AGENT / "Program.cs").read_text(encoding="utf-8")
PROJECT = (AGENT / "ResearchOS.LocalAgent.csproj").read_text(encoding="utf-8")
INSTALL = (ROOT / "scripts" / "research-os-agent-service.ps1").read_text(encoding="utf-8")


class ResearchOSLocalAgentSafetyTests(unittest.TestCase):
    def test_agent_is_a_windows_service_with_no_inbound_listener(self):
        self.assertIn('UseWindowsService(options => options.ServiceName = "ResearchOSLocalAgent")', PROGRAM)
        for forbidden in ("HttpListener", "TcpListener", "WebApplication", "Kestrel", "HttpServer"):
            self.assertNotIn(forbidden, PROGRAM)

    def test_agent_credentials_are_protected_by_machine_dpapi(self):
        self.assertIn("ProtectedData.Protect", PROGRAM)
        self.assertIn("ProtectedData.Unprotect", PROGRAM)
        self.assertIn("DataProtectionScope.LocalMachine", PROGRAM)
        self.assertIn("agent-config.dpapi", PROGRAM)
        self.assertIn("ReadSecret()", PROGRAM)

    def test_agent_requires_https_except_loopback_development(self):
        self.assertIn("Uri.UriSchemeHttps", PROGRAM)
        self.assertIn("uri.IsLoopback", PROGRAM)
        self.assertIn("uri.Host.Equals(\"localhost\"", PROGRAM)

    def test_agent_never_runs_arbitrary_shell_commands(self):
        self.assertIn("UseShellExecute = false", PROGRAM)
        self.assertIn("start.ArgumentList.Add(argument)", PROGRAM)
        self.assertIn('["rev-parse", "--show-toplevel"]', PROGRAM)
        self.assertIn('["rev-parse", "HEAD"]', PROGRAM)
        self.assertIn('["status", "--porcelain", "--untracked-files=no"]', PROGRAM)
        for forbidden in ("cmd.exe", "powershell.exe", "ProcessStartInfo(\"cmd", "Invoke-Expression"):
            self.assertNotIn(forbidden, PROGRAM)

    def test_agent_task_allowlist_and_source_sha_fence_are_explicit(self):
        self.assertIn('"repo.audit"', PROGRAM)
        self.assertIn("source_sha_mismatch", PROGRAM)
        self.assertIn("repository.inspect", PROGRAM)
        self.assertIn("No arbitrary", PROGRAM + (AGENT / "README.md").read_text(encoding="utf-8"))

    def test_service_install_defaults_to_manual_start_and_local_system(self):
        self.assertIn("'start= demand'", INSTALL)
        self.assertIn("'obj= LocalSystem'", INSTALL)
        self.assertIn("SYSTEM:(OI)(CI)F", INSTALL)


if __name__ == "__main__":
    unittest.main()
