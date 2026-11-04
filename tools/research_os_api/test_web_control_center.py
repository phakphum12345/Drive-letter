from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "research_os_web"


class ResearchOSControlCenterWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (WEB / "index.html").read_text(encoding="utf-8")
        cls.js = (WEB / "app.js").read_text(encoding="utf-8")
        cls.css = (WEB / "app.css").read_text(encoding="utf-8")

    def test_home_is_the_default_navigation_and_chat_remains_available(self):
        self.assertIn('data-view="home"', self.html)
        self.assertIn('id="homeView"', self.html)
        self.assertIn('id="chatView" hidden', self.html)
        self.assertIn("setPlatformView('home')", self.js)
        self.assertIn("setPlatformView('chat')", self.js)

    def test_dashboard_reads_live_owner_scoped_api_data(self):
        self.assertIn("request('/api/v1/jobs?limit=20')", self.js)
        self.assertIn("request('/api/v1/agents')", self.js)
        self.assertIn("request('/api/v1/jobs/'+encodeURIComponent(job.job_id)+'/evidence')", self.js)
        self.assertIn("credentials:'include'", self.js)
        self.assertIn("refreshControlCenter", self.js)

    def test_dashboard_does_not_replace_missing_runtime_data_with_mock_values(self):
        self.assertIn("Storage not configured — no demo data is shown.", self.js)
        self.assertIn("Cloud worker ยังไม่เปิดใช้งาน", self.js)
        self.assertIn('id="homeCloudStatus">Not deployed</strong>', self.html)
        self.assertIn("homeStatus", self.js)

    def test_security_and_human_gate_states_are_visible_and_explicit(self):
        self.assertIn("Owner-scoped access", self.html)
        self.assertIn("LOCAL_ONLY data to Cloud/AUTO", self.html)
        self.assertIn("Consent required", self.html)
        self.assertIn("Human approval workflow", self.html)
        self.assertIn("Not connected", self.html)

    def test_remote_job_and_agent_fields_are_rendered_as_text(self):
        self.assertIn("heading.textContent=title||'Untitled'", self.js)
        self.assertIn("detail.textContent=meta||''", self.js)
        self.assertNotIn("homeJobs.innerHTML", self.js)

    def test_admin_console_is_owner_only_and_uses_management_api(self):
        self.assertIn('data-view="admin" data-admin-only hidden', self.html)
        self.assertIn('id="adminView" hidden', self.html)
        self.assertIn("document.querySelectorAll('[data-admin-only]')", self.js)
        self.assertIn("role!=='OWNER'", self.js)
        self.assertIn("request('/platform/v1/organizations')", self.js)
        self.assertIn("request('/platform/v1/audit')", self.js)
        self.assertIn("read-only inventory", self.html)

    def test_chat_history_is_account_scoped_and_saved_locally(self):
        self.assertIn('id="chatHistory"', self.html)
        self.assertIn('id="newChatSession"', self.html)
        self.assertIn('id="chatHistoryStatus"', self.html)
        self.assertIn("research-os-chat-history:", self.js)
        self.assertIn("localStorage.setItem(key,JSON.stringify(state.chatSessions))", self.js)
        self.assertIn("restoreLocalChatHistory()", self.js)
        self.assertIn("state.chatSessions.slice(0,50)", self.js)
        self.assertIn("message.meta.route", self.js)
        self.assertIn("result.provider", self.js)
        self.assertIn("result.model", self.js)

    def test_chat_history_is_restored_after_otp_and_cleared_from_memory_on_signout(self):
        self.assertIn("if(state.account)restoreLocalChatHistory();panel.hidden=true", self.js)
        self.assertIn("clearChatStateForSignedOut()", self.js)
        self.assertIn("state.chatSessions=[];\\n  state.messages=[];\\n  state.sessionId=null", self.js)
        self.assertIn("else clearChatStateForSignedOut()", self.js)
        self.assertIn("Sign in to view local conversation history.", self.js)
        self.assertIn("renderLocalChatHistory", self.js) if "renderLocalChatHistory" in self.js else self.assertIn("restoreLocalChatHistory()", self.js)

    def test_primary_workspace_destinations_use_live_api_backed_views(self):
        self.assertIn('data-view="workspace" data-module="Projects & Files"', self.html)
        self.assertIn('data-view="workspace" data-module="History & Activity"', self.html)
        self.assertIn('data-view="workspace" data-module="Settings & Account"', self.html)
        self.assertIn('id="workspaceView"', self.html)
        self.assertIn("!['registry','workspace'].includes(selected)", self.js)
        self.assertIn("request('/v1/projects')", self.js)
        self.assertIn("request('/v2/workspaces')", self.js)
        self.assertIn("request('/api/v1/jobs?limit=50')", self.js)
        self.assertIn("request('/v1/agents/orchestrations?limit=50')", self.js)
        self.assertIn("request('/v1/auth/status')", self.js)
        self.assertIn("request('/v1/ai/connections')", self.js)
        self.assertIn("ยังไม่มี API binding", self.js)
        self.assertIn("credentials:'include'", self.js)

    def test_dashboard_has_mobile_responsive_layout(self):
        self.assertIn(".home-view", self.css)
        self.assertIn(".home-metrics", self.css)
        self.assertIn("@media(max-width:760px)", self.css)
        self.assertIn("@media(max-width:430px)", self.css)

    def test_chat_wide_mode_is_toggleable_persistent_and_preserves_conversation(self):
        self.assertIn('id="chatLayoutToggle"', self.html)
        self.assertIn("localStorage.setItem('research-os-chat-layout'", self.js)
        self.assertIn("localStorage.getItem('research-os-chat-layout')", self.js)
        self.assertIn("chat-wide-mode", self.js)
        self.assertIn(".chat-wide-mode .sidebar", self.css)
        self.assertIn("state.messages.length===0", self.js)
        self.assertNotIn("state.messages=[];addMessage('user',prompt)", self.js)


if __name__ == "__main__":
    unittest.main()
