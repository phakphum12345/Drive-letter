from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIMULATOR = ROOT / "index.html"
STUDIO = ROOT / "studio.html"


class _Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self.tags.append((tag, dict(attrs)))


class AppSimulatorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.simulator = SIMULATOR.read_text(encoding="utf-8")
        cls.studio = STUDIO.read_text(encoding="utf-8")
        cls.simulator_markup = _Markup()
        cls.simulator_markup.feed(cls.simulator)
        cls.studio_markup = _Markup()
        cls.studio_markup.feed(cls.studio)

    def test_simulator_links_to_code_studio_and_exposes_core_controls(self) -> None:
        hrefs = {
            attrs.get("href")
            for tag, attrs in self.simulator_markup.tags
            if tag == "a"
        }
        ids = {
            attrs.get("id")
            for _, attrs in self.simulator_markup.tags
            if attrs.get("id")
        }
        self.assertIn("studio.html", hrefs)
        for element_id in ("platforms", "scenario", "runBtn", "resetBtn", "exportBtn"):
            self.assertIn(element_id, ids)
        for scenario in ('value="happy"', 'value="expired"', 'value="offline"', 'value="denied"'):
            self.assertIn(scenario, self.simulator)

    def test_simulator_evidence_never_claims_a_bound_source_sha(self) -> None:
        self.assertRegex(self.simulator, r"source_sha\s*:\s*null")
        self.assertIn("UNBOUND", self.simulator)
        self.assertIn("No real authentication", self.simulator)
        self.assertIn("QR is decorative mock data", self.simulator)

    def test_studio_uses_user_selected_html_and_downloads_a_new_file(self) -> None:
        file_inputs = [
            attrs for tag, attrs in self.studio_markup.tags
            if tag == "input" and attrs.get("type") == "file"
        ]
        self.assertEqual(len(file_inputs), 1)
        self.assertIn(".html", file_inputs[0].get("accept") or "")
        self.assertIn("f.size>2*1024*1024", self.studio)
        self.assertIn("await f.text()", self.studio)
        self.assertIn("a.download=base+'-edited.html'", self.studio)
        self.assertIn("ต้นฉบับจะไม่ถูกเขียนทับอัตโนมัติ", self.studio)

    def test_live_preview_is_sandboxed_without_same_origin_permission(self) -> None:
        frames = [
            attrs for tag, attrs in self.studio_markup.tags if tag == "iframe"
        ]
        self.assertEqual(len(frames), 1)
        self.assertIn("allow-scripts", frames[0].get("sandbox") or "")
        self.assertNotIn("allow-same-origin", frames[0].get("sandbox") or "")
        self.assertIn("srcdoc=value", self.studio)

    def test_studio_links_back_to_simulator(self) -> None:
        hrefs = {
            attrs.get("href")
            for tag, attrs in self.studio_markup.tags
            if tag == "a"
        }
        self.assertIn("index.html", hrefs)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed; JavaScript syntax check skipped")
    def test_inline_javascript_parses(self) -> None:
        for name, html in (("index.html", self.simulator), ("studio.html", self.studio)):
            scripts = re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script\\s*>", html, re.I | re.S)
            self.assertTrue(scripts, f"{name} should contain an inline script")
            for index, script in enumerate(scripts, start=1):
                with self.subTest(file=name, script=index):
                    completed = subprocess.run(
                        ["node", "--check", "-"],
                        input=script,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        f"{name} inline script {index} failed syntax check:\\n{completed.stderr}",
                    )


if __name__ == "__main__":
    unittest.main()
