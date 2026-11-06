from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tools.research_os_api.api_platform.management_http import ManagementHTTP
from tools.research_os_api.api_platform.management_service import JsonManagementStore, ManagementService


class AdminConsoleManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        service = ManagementService(JsonManagementStore(Path(self.temp.name) / "management.json"))
        self.http = ManagementHTTP(service, lambda headers: headers.get("principal"))
        self.owner = {"principal": {"user_id": "owner-1", "role": "OWNER"}}
        self.user = {"principal": {"user_id": "user-1", "role": "USER"}}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def dispatch(self, method: str, path: str, headers=None, body=None):
        return self.http.dispatch(method, path, headers or {}, body or {})

    def test_non_owner_cannot_create_or_change_api_lifecycle(self) -> None:
        status, payload = self.dispatch(
            "POST", "/platform/v1/organizations", self.user,
            {"organization_id": "org-1", "name": "Org"},
        )
        self.assertEqual(403, status)
        self.assertEqual("owner_required", payload["error"])

        status, payload = self.dispatch(
            "POST", "/platform/v1/apis/api-1/disable", self.user, {},
        )
        self.assertEqual(403, status)
        self.assertEqual("owner_required", payload["error"])

    def test_owner_can_create_related_resources_and_lifecycle_is_persisted_and_audited(self) -> None:
        resources = (
            ("/platform/v1/organizations", {"organization_id": "org-1", "name": "Org"}),
            ("/platform/v1/projects", {"project_id": "project-1", "organization_id": "org-1", "name": "Project"}),
            ("/platform/v1/applications", {"application_id": "app-1", "project_id": "project-1", "name": "App"}),
            ("/platform/v1/apis", {"api_id": "api-1", "project_id": "project-1", "name": "API"}),
        )
        for path, body in resources:
            status, payload = self.dispatch("POST", path, self.owner, body)
            self.assertEqual(201, status, payload)

        status, published = self.dispatch(
            "POST", "/platform/v1/apis/api-1/publish", self.owner, {},
        )
        self.assertEqual(200, status)
        self.assertEqual("active", published["lifecycle"])

        status, disabled = self.dispatch(
            "POST", "/platform/v1/apis/api-1/disable", self.owner, {},
        )
        self.assertEqual(200, status)
        self.assertEqual("disabled", disabled["lifecycle"])

        status, audit = self.dispatch("GET", "/platform/v1/audit", self.owner)
        self.assertEqual(200, status)
        actions = [item["action"] for item in audit["items"]]
        self.assertIn("create", actions)
        self.assertIn("publish", actions)
        self.assertIn("disable", actions)

        # A fresh service instance proves the metadata survived process-local memory.
        restored = ManagementService(JsonManagementStore(Path(self.temp.name) / "management.json"))
        self.assertEqual("disabled", restored.get("apis", "api-1")["lifecycle"])

    def test_lifecycle_and_api_key_actions_reject_non_post_methods(self) -> None:
        status, _ = self.dispatch(
            "POST", "/platform/v1/organizations", self.owner,
            {"organization_id": "org-guard", "name": "Guard Organization"},
        )
        self.assertEqual(201, status)
        status, _ = self.dispatch(
            "POST", "/platform/v1/projects", self.owner,
            {"project_id": "project-guard", "organization_id": "org-guard", "name": "Guard Project"},
        )
        self.assertEqual(201, status)
        status, _ = self.dispatch(
            "POST", "/platform/v1/apis", self.owner,
            {"api_id": "api-method-guard", "project_id": "project-guard", "name": "Guarded API"},
        )
        self.assertEqual(201, status)

        status, payload = self.dispatch(
            "GET", "/platform/v1/apis/api-method-guard/disable", self.owner, {},
        )
        self.assertEqual(405, status)
        self.assertEqual("method_not_allowed", payload["error"])
        restored = self.http.service.get("apis", "api-method-guard")
        self.assertNotEqual("disabled", restored["lifecycle"])

        status, payload = self.dispatch(
            "GET", "/platform/v1/applications/app-1/keys/key-1/revoke", self.owner, {},
        )
        self.assertEqual(405, status)
        self.assertEqual("method_not_allowed", payload["error"])

    def test_metadata_and_audit_are_committed_by_one_atomic_store_write(self) -> None:
        store = JsonManagementStore(Path(self.temp.name) / "atomic.json")
        with patch.object(store, "_write", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                store.put_with_audit(
                    "organizations",
                    "org-failed",
                    {"organization_id": "org-failed", "name": "No partial write"},
                    actor="owner-1",
                    action="create",
                )
        snapshot = store.snapshot()
        self.assertNotIn("org-failed", snapshot["resources"]["organizations"])
        self.assertEqual([], snapshot["audit"])

    def test_failed_commit_does_not_leave_unpersisted_resource_in_memory(self) -> None:
        service = ManagementService(JsonManagementStore(Path(self.temp.name) / "rollback.json"))
        with patch.object(service.store, "_write", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                service.create(
                    "organizations",
                    {"organization_id": "org-rollback", "name": "Rollback"},
                    actor="owner-1",
                )
        self.assertEqual([], service.list("organizations"))

    def test_failed_lifecycle_commit_keeps_metadata_and_audit_unchanged(self) -> None:
        service = ManagementService(JsonManagementStore(Path(self.temp.name) / "lifecycle-rollback.json"))
        service.create(
            "organizations",
            {"organization_id": "org-1", "name": "Org"},
            actor="owner-1",
        )
        service.create(
            "projects",
            {"project_id": "project-1", "organization_id": "org-1", "name": "Project"},
            actor="owner-1",
        )
        service.create(
            "apis",
            {"api_id": "api-1", "project_id": "project-1", "name": "API"},
            actor="owner-1",
        )
        before = service.store.snapshot()
        with patch.object(service.store, "_write", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                service.lifecycle("apis", "api-1", "disable", actor="owner-1")
        self.assertEqual("active", service.get("apis", "api-1")["lifecycle"])
        after = service.store.snapshot()
        self.assertEqual(before, after)
        self.assertFalse(any(item["action"] == "disable" for item in after["audit"]))

    def test_web_admin_mutations_are_owner_gated_and_confirmed(self) -> None:
        root = Path(__file__).resolve().parents[2]
        source = (root / "apps" / "research_os_web" / "app.js").read_text(encoding="utf-8")
        markup = (root / "apps" / "research_os_web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("state.account?.role", source)
        self.assertIn("window.confirm('Create this '", source)
        self.assertIn("window.confirm('Confirm '", source)
        self.assertIn("request('/platform/v1/'+type", source)
        self.assertIn("request('/platform/v1/apis/'+encodeURIComponent(apiId)+'/'+action", source)
        self.assertIn('id="adminCreateForm"', markup)
        self.assertIn('data-admin-only', markup)


if __name__ == "__main__":
    unittest.main()
