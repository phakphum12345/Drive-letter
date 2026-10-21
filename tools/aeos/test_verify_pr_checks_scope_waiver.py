"""Regression tests for exact-HEAD scope evidence in AEOS check verification."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.aeos import verify_pr_checks


HEAD = "a" * 40


def check(name: str, conclusion: str, *, sha: str = HEAD) -> dict:
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": sha,
        "details_url": "https://github.com/phakphum12345/Drive-letter/actions/runs/1",
    }


class ScopeVerifiedWindowsSkipTests(unittest.TestCase):
    def fetch(self, check_runs: list[dict]) -> list[dict]:
        with patch.object(verify_pr_checks, "paginate", side_effect=[check_runs, []]):
            return verify_pr_checks.fetch_external_checks(
                "phakphum12345/Drive-letter", HEAD, "999"
            )

    def test_skipped_windows_check_requires_exact_head_scope_waiver(self) -> None:
        results = self.fetch([
            check("Flutter Windows build analyze test", "skipped"),
            check("Flutter Windows validation not applicable (scope-verified)", "success"),
        ])
        windows = next(c for c in results if c["name"] == "Flutter Windows build analyze test")
        self.assertEqual(windows["bucket"], "not_applicable")
        self.assertIn("exact-HEAD", windows["reason_code"])

    def test_skipped_windows_check_without_waiver_remains_unproven(self) -> None:
        results = self.fetch([check("Flutter Windows build analyze test", "skipped")])
        windows = next(c for c in results if c["name"] == "Flutter Windows build analyze test")
        self.assertEqual(windows["bucket"], "unproven")

    def test_stale_head_waiver_does_not_authorize_skip(self) -> None:
        results = self.fetch([
            check("Flutter Windows build analyze test", "skipped"),
            check("Flutter Windows validation not applicable (scope-verified)", "success", sha="b" * 40),
        ])
        windows = next(c for c in results if c["name"] == "Flutter Windows build analyze test")
        self.assertEqual(windows["bucket"], "unproven")

    def test_failed_scope_waiver_does_not_authorize_skip(self) -> None:
        results = self.fetch([
            check("Flutter Windows build analyze test", "skipped"),
            check("Flutter Windows validation not applicable (scope-verified)", "failure"),
        ])
        windows = next(c for c in results if c["name"] == "Flutter Windows build analyze test")
        self.assertEqual(windows["bucket"], "unproven")

    def test_existing_push_image_exception_is_unchanged(self) -> None:
        results = self.fetch([check("push-image", "skipped")])
        image = next(c for c in results if c["name"] == "push-image")
        self.assertEqual(image["bucket"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
