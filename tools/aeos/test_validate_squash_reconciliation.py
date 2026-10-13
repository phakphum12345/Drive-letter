"""Regression tests ensuring unavailable history never becomes a false pass."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_squash_reconciliation.py")
VALID = {
    "schema": "aeos.squash-reconciliation.v1", "pr_number": 366,
    "base_sha": "0" * 40, "head_sha": "1" * 40, "merge_sha": "2" * 40,
    "merge_parent_sha": "0" * 40,
    "divergent_paths": ["src/conflict.py"],
    "canonical_conflict_evidence": {"src/conflict.py": {"stale_or_conflicting": True, "evidence": "independent comparison pending"}},
    "accepted_payload_paths": ["src/accepted.py"],
    "accepted_payload_digest": "2" * 40, "accepted_payload_digest_algorithm": "git_commit_sha",
    "independent_forensic_status": "PENDING", "merge_authority": False, "self_certification": False,
}

class ReconciliationValidationTests(unittest.TestCase):
    def invoke(self, payload: dict, stage: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=temp, check=True)
            return subprocess.run([sys.executable, str(SCRIPT), str(manifest), stage], cwd=temp, text=True, capture_output=True, check=False)

    def test_source_stage_fails_closed_when_historical_objects_are_missing(self) -> None:
        result = self.invoke(VALID, "source")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required historical Git commit is unavailable", result.stderr)

    def test_source_stage_rejects_digest_mismatch_before_git_validation(self) -> None:
        payload = dict(VALID, accepted_payload_digest="3" * 40)
        result = self.invoke(payload, "source")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted payload digest does not equal merge commit SHA", result.stderr)

    def test_forensic_stage_fails_closed_when_historical_objects_are_missing(self) -> None:
        payload = dict(VALID, independent_forensic_status="VERIFIED")
        result = self.invoke(payload, "forensic")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required historical Git commit is unavailable", result.stderr)

if __name__ == "__main__":
    unittest.main()
