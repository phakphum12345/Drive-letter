from __future__ import annotations

import re
import unittest
from pathlib import Path


class ResearchOSWebAPIOriginTests(unittest.TestCase):
    def test_web_frontend_defaults_to_the_render_public_api_origin(self):
        repository_root = Path(__file__).resolve().parents[2]
        app_script = (repository_root / "apps" / "research_os_web" / "app.js").read_text(encoding="utf-8")
        render_config = (repository_root / "render.yaml").read_text(encoding="utf-8")

        match = re.search(
            r"(?m)^\s*- key: RESEARCH_OS_PUBLIC_BASE_URL\s*\n\s*value: (https://[^\s]+)",
            render_config,
        )
        self.assertIsNotNone(match, "render.yaml must define the public API base URL")
        public_api_url = match.group(1)

        self.assertIn(f"window.RESEARCH_OS_API_BASE_URL||'{public_api_url}'", app_script)
        self.assertNotIn(".ts.net", app_script)


if __name__ == "__main__":
    unittest.main()
