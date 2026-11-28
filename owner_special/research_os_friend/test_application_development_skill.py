from __future__ import annotations

import unittest

from owner_special.research_os_friend.catalog import install_builtin_skills
from owner_special.research_os_friend.skills import SkillRegistry


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

    def test_skill_handler_is_deterministic_and_preserves_request(self) -> None:
        (skill,) = self.registry.resolve(("application_development",))
        self.assertEqual(
            self.registry.run(skill, "Build a cross-platform application"),
            "application_development: Build a cross-platform application",
        )

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
