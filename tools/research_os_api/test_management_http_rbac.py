from __future__ import annotations

import unittest


try:
    from .api_platform.management_http import ManagementHTTP
except ImportError:  # pragma: no cover - direct unittest discovery
    from api_platform.management_http import ManagementHTTP


class _Store:
    def audit(self):
        return [{"action": "create", "resource": "projects", "outcome": "success"}]


class _Service:
    def __init__(self):
        self.store = _Store()
        self.calls = []

    def list(self, resource):
        self.calls.append(("list", resource))
        return [{"id": "sample"}]

    def get(self, resource, identifier):
        self.calls.append(("get", resource, identifier))
        return {"id": identifier}


class ManagementHTTPAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.service = _Service()
        self.http = ManagementHTTP(self.service, lambda headers: headers.get("principal"))

    def test_unauthenticated_management_access_is_denied(self):
        status, payload = self.http.dispatch("GET", "/platform/v1/projects", {})
        self.assertEqual(401, status)
        self.assertEqual("invalid_session", payload["error"])
        self.assertEqual([], self.service.calls)

    def test_non_owner_cannot_read_or_mutate_management_resources(self):
        headers = {"principal": {"user_id": "user-1", "role": "USER"}}
        for method, path, body in (
            ("GET", "/platform/v1/", {}),
            ("GET", "/platform/v1/projects", {}),
            ("POST", "/platform/v1/projects", {"project_id": "x"}),
            ("PATCH", "/platform/v1/projects/x", {"name": "changed"}),
        ):
            status, payload = self.http.dispatch(method, path, headers, body)
            self.assertEqual(403, status)
            self.assertEqual("owner_required", payload["error"])
        self.assertEqual([], self.service.calls)

    def test_owner_can_read_management_inventory_and_audit(self):
        headers = {"principal": {"user_id": "owner-1", "email": "owner@example.test", "role": "OWNER"}}
        status, projects = self.http.dispatch("GET", "/platform/v1/projects", headers)
        self.assertEqual(200, status)
        self.assertEqual(1, projects["count"])
        status, audit = self.http.dispatch("GET", "/platform/v1/audit", headers)
        self.assertEqual(200, status)
        self.assertEqual(1, audit["count"])


if __name__ == "__main__":
    unittest.main()
