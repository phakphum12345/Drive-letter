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

    def test_dashboard_has_mobile_responsive_layout(self):
        self.assertIn(".home-view", self.css)
        self.assertIn(".home-metrics", self.css)
        self.assertIn("@media(max-width:760px)", self.css)
        self.assertIn("@media(max-width:430px)", self.css)


if __name__ == "__main__":
    unittest.main()
