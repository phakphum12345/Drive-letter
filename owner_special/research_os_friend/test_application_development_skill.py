from __future__ import annotations

import unittest

from owner_special.research_os_friend.catalog import (
    APPLICATION_DEVELOPMENT_PROTOCOL_MAX_CHARS,
    install_builtin_skills,
)
from owner_special.research_os_friend.skills import SkillRegistry
from owner_special.research_os_friend import FriendRequest, FriendRuntime
from owner_special.research_os_friend.providers import ProviderResult


class _CapturingProvider:
    name = "application-development-test-provider"

    def __init__(self) -> None:
        self.context: tuple[str, ...] = ()

    def complete(self, *, prompt: str, context: tuple[str, ...]) -> ProviderResult:
        self.context = context
        return ProviderResult(text="captured")


class ApplicationDevelopmentSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = install_builtin_skills(SkillRegistry())

    def test_application_development_is_registered_as_core_skill(self) -> None:
        self.assertIn("application_development", self.registry.names())

    def test_skill_resolves_with_engineering_domain_and_protocol_description(self) -> None:
        (skill,) = self.registry.resolve(("application_development",))
        self.assertEqual(skill.domain, "engineering")
        self.assertIn("requirements", skill.description)
        self.assertIn("security", skill.description)
        self.assertIn("release", skill.description)
        self.assertEqual(skill.protocol_id, "ROS-APP-DEV-001")
        self.assertEqual(skill.protocol_version, "1.0.0")
        self.assertIn("DISCOVER", skill.instructions)
        self.assertIn("Definition of Done", skill.instructions)
        self.assertLessEqual(
            len(skill.instructions),
            APPLICATION_DEVELOPMENT_PROTOCOL_MAX_CHARS,
        )

    def test_skill_handler_is_deterministic_and_preserves_request(self) -> None:
        (skill,) = self.registry.resolve(("application_development",))
        self.assertEqual(
            self.registry.run(skill, "Build a cross-platform application"),
            "application_development: Build a cross-platform application",
        )

    def test_catalog_exposes_metadata_without_handlers(self) -> None:
        entries = self.registry.describe()
        application = next(item for item in entries if item["name"] == "application_development")
        self.assertEqual(application["domain"], "engineering")
        self.assertTrue(application["instructions_available"])
        self.assertEqual(application["protocol_id"], "ROS-APP-DEV-001")
        self.assertNotIn("handler", application)

    def test_selected_skill_protocol_is_injected_into_provider_context(self) -> None:
        runtime = FriendRuntime.create_owner_special("phakphum")
        provider = _CapturingProvider()
        runtime.orchestrator.providers.set_primary(provider)

        response = runtime.ask(
            FriendRequest(
                owner_id="phakphum",
                text="Plan a secure desktop application",
                requested_skills=("application_development",),
            )
        )

        protocol_context = next(
            item for item in provider.context
            if "[Research OS Skill: application_development;" in item
        )
        self.assertIn("DISCOVER", protocol_context)
        self.assertIn("Identity → Role → Permission → Tools → Skills → Data Scope", protocol_context)
        self.assertEqual(
            response.metadata["skill_protocols"],
            [{
                "name": "application_development",
                "protocol_id": "ROS-APP-DEV-001",
                "version": "1.0.0",
                "instructions_loaded": True,
            }],
        )

    def test_unselected_skill_protocol_is_not_injected(self) -> None:
        runtime = FriendRuntime.create_owner_special("phakphum")
        provider = _CapturingProvider()
        runtime.orchestrator.providers.set_primary(provider)

        runtime.ask(FriendRequest(owner_id="phakphum", text="Hello"))

        self.assertFalse(any("ROS-APP-DEV-001" in item for item in provider.context))

    def test_existing_core_skills_remain_registered(self) -> None:
        expected = {
            "analysis",
            "planning",
            "coding",
            "research",
            "data",
            "documents",
            "automation",
            "memory",
            "security",
            "quality",
            "codex",
            "vscode",
            "self_learning",
        }
        self.assertTrue(expected.issubset(set(self.registry.names())))


if __name__ == "__main__":
    unittest.main()
