from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'artifacts-build.yml'

class ArtifactDeploymentModeTests(unittest.TestCase):
    def test_mode_switch_and_endpoint_lineage(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('deployment_mode:', text)
        self.assertIn('          - local\n          - render', text)
        self.assertIn('default: local', text)
        self.assertIn('https://research-os-api-phakphoum.onrender.com', text)
        self.assertIn('http://127.0.0.1:8787', text)
        self.assertIn('flutter build web --release --dart-define=RESEARCH_OS_API_BASE_URL="$API_BASE_URL"', text)
        self.assertIn('flutter build windows --release --dart-define=RESEARCH_OS_API_BASE_URL="$env:API_BASE_URL"', text)
        self.assertIn('flutter build ios --release --no-codesign --dart-define=RESEARCH_OS_API_BASE_URL="$API_BASE_URL"', text)
        self.assertIn('deployment-manifest.json', text)

if __name__ == '__main__':
    unittest.main()
