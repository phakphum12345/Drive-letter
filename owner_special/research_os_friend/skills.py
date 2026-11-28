from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

SkillHandler = Callable[[str], str]


@dataclass(frozen=True)
class Skill:
    name: str
    domain: str
    description: str
    handler: SkillHandler
    instructions: str = ""
    protocol_id: str = ""
    protocol_version: str = ""


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if not skill.name or skill.name in self._skills:
            raise ValueError(f"duplicate or empty skill: {skill.name}")
        self._skills[skill.name] = skill

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))

    def resolve(self, requested: tuple[str, ...]) -> tuple[Skill, ...]:
        missing = [name for name in requested if name not in self._skills]
        if missing:
            raise KeyError(f"unknown skills: {', '.join(missing)}")
        return tuple(self._skills[name] for name in requested)

    def describe(self) -> tuple[dict[str, str | bool], ...]:
        """Return read-only catalog metadata; never expose executable handlers."""
        return tuple(
            {
                "name": skill.name,
                "domain": skill.domain,
                "description": skill.description,
                "instructions_available": bool(skill.instructions),
                "protocol_id": skill.protocol_id,
                "protocol_version": skill.protocol_version,
            }
            for skill in (self._skills[name] for name in self.names())
        )

    def run(self, skill: Skill, text: str) -> str:
        return skill.handler(text)
