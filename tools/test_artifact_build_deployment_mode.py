from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "artifacts-build.yml"


class ArtifactDeploymentModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_dispatch_exposes_only_local_and_render_modes(self):
        self.assertIn("deployment_mode:", self.workflow)
        self.assertIn("type: choice", self.workflow)
        self.assertIn("          - local\n          - render", self.workflow)
        self.assertIn("default: local", self.workflow)

    def test_mode_selects_explicit_endpoint(self):
        self.assertIn("inputs.deployment_mode == 'render'", self.workflow)
        self.assertIn("https://research-os-api-phakphoum.onrender.com", self.workflow)
        self.assertIn("http://127.0.0.1:8787", self.workflow)

    def test_all_flutter_artifacts_compile_selected_endpoint(self):
        self.assertIn('flutter build web --release --dart-define=RESEARCH_OS_API_BASE_URL="$API_BASE_URL"', self.workflow)
        self.assertIn('flutter build windows --release --dart-define=RESEARCH_OS_API_BASE_URL="$env:API_BASE_URL"', self.workflow)
        self.assertIn('flutter build ios --release --no-codesign --dart-define=RESEARCH_OS_API_BASE_URL="$API_BASE_URL"', self.workflow)

    def test_manifests_record_mode_and_endpoint(self):
        self.assertIn('"deployment_mode":os.environ["DEPLOYMENT_MODE"]', self.workflow)
        self.assertIn('"api_base_default":os.environ["API_BASE_URL"]', self.workflow)
        self.assertIn("deployment-manifest.json", self.workflow)
        self.assertIn("target_sha = $env:TARGET_SHA", self.workflow)

    def test_local_mode_does_not_change_render_backend_blueprint(self):
        render_blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("name: research-os-api-phakphoum", render_blueprint)
        self.assertIn("startCommand: cd tools/research_os_api && python render_server.py", render_blueprint)


if __name__ == "__main__":
    unittest.main()
