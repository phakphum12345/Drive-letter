"""Regression tests for exact-HEAD scope evidence in AEOS check verification."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.aeos import verify_pr_checks


REPOSITORY = "phakphum12345/Drive-letter"
HEAD = "a" * 40
BASE = "b" * 40


def skipped_check() -> dict:
    return {
        "name": "Flutter Windows build analyze test",
        "status": "completed",
        "conclusion": "skipped",
        "head_sha": HEAD,
        "details_url": f"https://github.com/{REPOSITORY}/actions/runs/100/job/200",
    }


def scope_run(*, sha: str = HEAD, conclusion: str = "success", path: str = ".github/workflows/research-os-final-gate.yml") -> dict:
    return {
        "name": "Research OS Final Gate",
        "path": path,
        "event": "pull_request",
        "head_sha": sha,
        "conclusion": conclusion,
    }


def scope_job(*, conclusion: str = "success") -> dict:
    return {
        "name": "Decide whether legacy Flutter Windows validation is relevant",
        "run_id": "100",
        "conclusion": conclusion,
    }


class ScopeVerifiedWindowsSkipTests(unittest.TestCase):
    def prove(
        self,
        *,
        run: dict | None = None,
        job: dict | None = None,
        pr_head: str = HEAD,
        files: list[dict] | None = None,
    ) -> dict:
        pr = {"head": {"sha": pr_head}, "base": {"sha": BASE}}
        with (
            patch.object(
                verify_pr_checks,
                "request_json",
                side_effect=[(run or scope_run(), {}), (
                    {"run_id": "100", "name": "Flutter Windows build analyze test", "status": "completed", "conclusion": "skipped"}, {}
                ), (pr, {})],
            ),
            patch.object(verify_pr_checks, "paginate", return_value=[job or scope_job()]),
            patch.object(
                verify_pr_checks,
                "paginate_array",
                return_value=files if files is not None else [{"filename": "docs/README.md"}],
            ),
        ):
            return verify_pr_checks.prove_flutter_scope_skip(
                skipped_check(),
                {"bucket": "unproven", "state": "SKIPPED", "name": "Flutter Windows build analyze test"},
                REPOSITORY,
                "999",
                HEAD,
            )

    def test_unrelated_files_need_successful_exact_head_scope_evidence(self) -> None:
        result = self.prove()
        self.assertEqual(result["bucket"], "not_applicable")
        self.assertEqual(result["source"], "check_run+exact_scope_evidence")
        self.assertIn("exact-SHA Research OS Final Gate passed", result["reason_code"])

    def test_stale_final_gate_sha_does_not_authorize_skip(self) -> None:
        result = self.prove(run=scope_run(sha="c" * 40))
        self.assertEqual(result["bucket"], "unproven")

    def test_stale_pr_head_does_not_authorize_skip(self) -> None:
        result = self.prove(pr_head="c" * 40)
        self.assertEqual(result["bucket"], "unproven")

    def test_failed_scope_detector_does_not_authorize_skip(self) -> None:
        result = self.prove(job=scope_job(conclusion="failure"))
        self.assertEqual(result["bucket"], "unproven")

    def test_failed_final_gate_does_not_authorize_skip(self) -> None:
        result = self.prove(run=scope_run(conclusion="failure"))
        self.assertEqual(result["bucket"], "unproven")

    def test_changed_flutter_path_does_not_authorize_skip(self) -> None:
        result = self.prove(files=[{"filename": "v3/flutter_app/lib/main.dart"}])
        self.assertEqual(result["bucket"], "unproven")

    def test_untrusted_workflow_path_does_not_authorize_skip(self) -> None:
        result = self.prove(run=scope_run(path=".github/workflows/other.yml"))
        self.assertEqual(result["bucket"], "unproven")

    def test_missing_pr_head_does_not_authorize_skip(self) -> None:
        result = self.prove(pr_head="")
        self.assertEqual(result["bucket"], "unproven")


if __name__ == "__main__":
    unittest.main()
