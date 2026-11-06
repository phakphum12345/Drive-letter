from decimal import Decimal
import os
import unittest
from unittest.mock import patch

from owner_special.research_os_friend.provider_settings import (
    GeminiProvider,
    OpenAICompatibleProvider,
    build_environment_provider,
)


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.last_url = None
        self.last_headers = None
        self.last_payload = None

    def get_json(self, url, *, headers, timeout):
        self.last_url = url
        self.last_headers = headers
        return {"data": [{"id": "llama3.2:3b"}]}

    def post_json(self, url, *, headers, payload, timeout):
        self.last_url = url
        self.last_headers = headers
        self.last_payload = payload
        return self.payload


class FriendProviderRuntimeTests(unittest.TestCase):
    def test_gemini_uses_native_generate_content_and_measured_usage(self):
        transport = FakeTransport({
            "modelVersion": "gemini-3-flash-preview",
            "candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "toolUsePromptTokenCount": 0,
                "cachedContentTokenCount": 0,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 10,
                "totalTokenCount": 130,
            },
        })
        provider = GeminiProvider(
            api_key="test-secret",
            model="gemini-3-flash-preview",
            transport=transport,
        )
        result = provider.complete(prompt="question", context=("memory",))

        self.assertEqual(result.text, "Gemini answer")
        self.assertEqual(result.usage, {"requests": 1, "tokens": 130})
        self.assertEqual(result.actual_cost, Decimal("0.00014"))
        self.assertIn("generateContent", transport.last_url)
        self.assertNotIn("test-secret", transport.last_url)
        self.assertEqual(transport.last_headers["x-goog-api-key"], "test-secret")
        self.assertEqual(
            transport.last_payload["contents"][0]["parts"][0]["text"],
            "Owner context:\nmemory\n\nquestion",
        )
        self.assertNotIn("test-secret", str(result.raw))

    def test_gemini_health_uses_models_get_and_secret_header(self):
        transport = FakeTransport({"name": "models/gemini-3-flash-preview"})
        provider = GeminiProvider(
            api_key="test-secret",
            model="gemini-3-flash-preview",
            transport=transport,
        )
        result = provider.test_connection()
        self.assertTrue(result["connected"])
        self.assertEqual(result["provider"], "gemini")
        self.assertNotIn("test-secret", transport.last_url)
        self.assertEqual(transport.last_headers["x-goog-api-key"], "test-secret")

    def test_gemini_missing_usage_does_not_invent_cost(self):
        transport = FakeTransport({
            "candidates": [{"content": {"parts": [{"text": "answer"}]}}],
        })
        result = GeminiProvider(
            api_key="test-secret",
            model="unknown-model",
            transport=transport,
        ).complete(prompt="question", context=())
        self.assertIsNone(result.actual_cost)
        self.assertEqual(result.usage, {"requests": 1})

    def test_gemini_cached_usage_fails_closed_for_cost_measurement(self):
        transport = FakeTransport({
            "candidates": [{"content": {"parts": [{"text": "answer"}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "cachedContentTokenCount": 80,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 0,
                "totalTokenCount": 120,
            },
        })
        result = GeminiProvider(
            api_key="test-secret",
            model="gemini-3-flash-preview",
            transport=transport,
        ).complete(prompt="question", context=())
        self.assertIsNone(result.actual_cost)

    def test_ollama_local_has_no_bearer_secret_and_no_api_charge(self):
        transport = FakeTransport({
            "choices": [{"message": {"content": "local answer"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13},
        })
        provider = OpenAICompatibleProvider(
            base_url="http://127.0.0.1:11434/v1",
            model="llama3.2:3b",
            api_key="",
            transport=transport,
            name="ollama-local",
            local=True,
        )
        result = provider.complete(prompt="question", context=())
        self.assertEqual(result.text, "local answer")
        self.assertEqual(result.usage, {"requests": 1, "tokens": 13})
        self.assertEqual(result.actual_cost, Decimal("0"))
        self.assertNotIn("Authorization", transport.last_headers)
        health = provider.test_connection()
        self.assertTrue(health["connected"])
        self.assertEqual("llama3.2:3b", health["model"])

    def test_gemini_mode_requires_existing_secret_without_exposing_it(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "gemini"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "credential is not configured"):
                build_environment_provider()

    def test_gemini_mode_selects_gemini_provider(self):
        with patch.dict(
            os.environ,
            {"RESEARCH_OS_PROVIDER": "gemini", "GEMINI_API_KEY": "test-secret"},
            clear=True,
        ):
            provider = build_environment_provider()
        self.assertEqual(provider.name, "gemini")

    def test_local_mode_selects_ollama_provider(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "local"}, clear=True):
            provider = build_environment_provider()
        self.assertEqual(provider.name, "ollama-local")
        self.assertTrue(provider.local)

    def test_mock_is_only_selected_explicitly(self):
        with patch.dict(os.environ, {"RESEARCH_OS_PROVIDER": "mock"}, clear=True):
            provider = build_environment_provider()
        self.assertEqual(provider.name, "owner-mock")


if __name__ == "__main__":
    unittest.main()
