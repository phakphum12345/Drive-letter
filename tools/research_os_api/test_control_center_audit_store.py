from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import control_center_audit_store


class ControlCenterAuditStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {"RESEARCH_OS_DATA_DIR": self.temp.name})
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp.cleanup()

    def snapshot(self, audit_id: str = "audit-1") -> dict:
        return {
            "audit_id": audit_id,
            "observed_at": "2026-11-04T12:00:00Z",
            "status": "DEFERRED",
            "source": "Native Control Center",
            "checks": [
                {"check": "Runtime", "state": "PASS", "detail": "Observed"},
                {"check": "Release authority", "state": "DEFERRED", "detail": "Not exposed"},
            ],
        }

    def test_save_and_list_are_durable_and_user_scoped(self) -> None:
        control_center_audit_store.save_audit("user-a", self.snapshot())
        control_center_audit_store.save_audit("user-b", self.snapshot("audit-b"))

        self.assertEqual(["audit-1"], [x["audit_id"] for x in control_center_audit_store.list_audits("user-a")])
        self.assertEqual(["audit-b"], [x["audit_id"] for x in control_center_audit_store.list_audits("user-b")])
        path = Path(self.temp.name) / "sessions" / "control_center_audits.json"
        self.assertTrue(path.is_file())
        self.assertEqual("audit-1", json.loads(path.read_text(encoding="utf-8"))["users"]["user-a"][0]["audit_id"])

    def test_duplicate_audit_id_is_idempotent(self) -> None:
        control_center_audit_store.save_audit("user-a", self.snapshot())
        control_center_audit_store.save_audit("user-a", self.snapshot())
        self.assertEqual(1, len(control_center_audit_store.list_audits("user-a")))

    def test_rejects_invalid_identity_and_audit_payload(self) -> None:
        with self.assertRaises(ValueError):
            control_center_audit_store.list_audits("../other")
        with self.assertRaises(ValueError):
            control_center_audit_store.save_audit("user-a", {**self.snapshot(), "status": "APPROVED"})
        with self.assertRaises(ValueError):
            control_center_audit_store.save_audit("user-a", {**self.snapshot(), "checks": []})

    def test_limit_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            control_center_audit_store.list_audits("user-a", limit=101)


if __name__ == "__main__":
    unittest.main()
