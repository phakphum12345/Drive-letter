"""Unit tests for the read-only Crowdin API adapter; all HTTP is mocked."""
import json
import unittest
from unittest.mock import Mock

from tools.mcp_engine.crowdin_adapter import CrowdinAdapter, CrowdinAdapterError, MAX_RESPONSE_BYTES


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


class CrowdinAdapterTests(unittest.TestCase):
    def adapter_for(self, payload):
        opener = Mock(return_value=FakeResponse(payload))
        return CrowdinAdapter("test-token-do-not-log", opener=opener), opener

    def test_list_projects_uses_fixed_get_and_redacts_token(self):
        payload = json.dumps({"data": [{"data": {
            "id": 123, "name": "Research OS", "identifier": "research-os",
            "sourceLanguageId": "en", "targetLanguageIds": ["th"]
        }}]}).encode()
        adapter, opener = self.adapter_for(payload)
        result = adapter.list_projects()
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.crowdin.com/api/v2/projects?limit=25")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token-do-not-log")
        self.assertEqual(result["operation"], "READ_ONLY")
        self.assertEqual(result["count"], 1)
        self.assertNotIn("test-token-do-not-log", json.dumps(result))

    def test_project_files_validates_id_before_network(self):
        adapter, opener = self.adapter_for(b'{"data":[]}')
        for project_id in ("", "0", "../1", "1?limit=100", "١"):
            with self.subTest(project_id=project_id):
                with self.assertRaises(CrowdinAdapterError):
                    adapter.list_project_files(project_id)
        opener.assert_not_called()

    def test_missing_token_fails_closed(self):
        with self.assertRaisesRegex(CrowdinAdapterError, "not configured"):
            CrowdinAdapter(" ")

    def test_invalid_json_is_rejected(self):
        adapter, _ = self.adapter_for(b"not-json")
        with self.assertRaisesRegex(CrowdinAdapterError, "invalid JSON"):
            adapter.list_projects()

    def test_oversized_response_is_rejected(self):
        adapter, _ = self.adapter_for(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(CrowdinAdapterError, "exceeds the 1 MiB limit"):
            adapter.list_projects()


if __name__ == "__main__":
    unittest.main()
