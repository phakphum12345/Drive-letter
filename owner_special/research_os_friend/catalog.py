from __future__ import annotations

import json
import re
from pathlib import Path

from .skills import Skill, SkillRegistry
from .tools import Tool, ToolRegistry
from .schedule_generation.adapter import ScheduleGenerateTool
from .web_tool import install_web_tool
from tools.research_os_api.github_status import GitHubStatusError, dashboard as github_dashboard


DEFAULT_GITHUB_REPOSITORY = "phakphoum38-stack/ENTERPRISE_API_ARCHITECTURE_LOGIC_TH"
_REPOSITORY_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?![A-Za-z0-9_.-])")
APPLICATION_DEVELOPMENT_PROTOCOL_ID = "ROS-APP-DEV-001"
APPLICATION_DEVELOPMENT_PROTOCOL_VERSION = "1.0.0"
APPLICATION_DEVELOPMENT_PROTOCOL_MAX_CHARS = 32000


def _tag(label: str):
    def handler(text: str) -> str:
        return f"{label}: {text.strip()}"
    return handler


def _application_development_protocol() -> str:
    """Load the canonical protocol in source checkouts and its bundled copy in releases."""
    candidates = (
        Path(__file__).resolve().parents[2] / "docs" / "RESEARCH_OS_APPLICATION_DEVELOPMENT_PROTOCOL.md",
        Path(__file__).with_name("application_development_protocol.md"),
    )
    for candidate in candidates:
        if candidate.is_file():
            content = candidate.read_text(encoding="utf-8").strip()
            if not content:
                raise RuntimeError("Application Development Protocol is empty")
            if len(content) > APPLICATION_DEVELOPMENT_PROTOCOL_MAX_CHARS:
                raise RuntimeError("Application Development Protocol exceeds the runtime context limit")
            return content
    raise FileNotFoundError("Application Development Protocol is missing from source and runtime bundle")


def _github_repository_from_text(text: str) -> str:
    match = _REPOSITORY_RE.search(text or "")
    return match.group(1) if match else DEFAULT_GITHUB_REPOSITORY


def _github_repository_status(text: str) -> str:
    repository = _github_repository_from_text(text)
    try:
        payload = github_dashboard(repository)
    except (GitHubStatusError, ValueError) as exc:
        return json.dumps(
            {"repository": repository, "ok": False, "error": str(exc)},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "repository": payload.get("repository"),
            "default_branch": payload.get("default_branch"),
            "visibility": payload.get("visibility"),
            "url": payload.get("url"),
            "open_issues_count": payload.get("open_issues_count"),
            "pull_requests": payload.get("pull_requests", []),
            "workflow_runs": payload.get("workflow_runs", []),
            "artifacts": payload.get("artifacts", []),
            "credential_configured": payload.get("credential_configured"),
            "read_only": True,
            "ok": True,
        },
        ensure_ascii=False,
    )


def install_builtin_skills(registry: SkillRegistry) -> SkillRegistry:
    protocol = _application_development_protocol()
    definitions = (
        ("analysis", "reasoning", "Analyze goals, constraints, and evidence."),
        ("planning", "orchestration", "Turn a goal into reviewable execution steps."),
        ("coding", "engineering", "Design, implement, test, and review software changes."),
        (
            "application_development",
            "engineering",
            "Apply the governed Application Development Protocol from discovery and requirements through architecture, UX, implementation, security, testing, release, and maintenance.",
        ),
        ("research", "knowledge", "Gather and compare source-backed information."),
        ("data", "analytics", "Inspect structured data and produce quantitative findings."),
        ("documents", "artifacts", "Create and transform durable written artifacts."),
        ("automation", "operations", "Define repeatable scheduled or triggered workflows."),
        ("memory", "context", "Use owner-scoped context without cross-profile leakage."),
        ("security", "assurance", "Apply permission, secret, and isolation boundaries."),
        ("quality", "assurance", "Validate outputs with tests and evidence."),
        (
            "codex",
            "software-agent",
            "Work with Codex-style software engineering workflows: inspect a workspace, plan changes, edit code, run tests, review diffs, and prepare commits without exposing secrets.",
        ),
        (
            "vscode",
            "developer-tools",
            "Work with VS Code projects: understand workspace structure, settings, tasks, launch configurations, extensions, terminals, diagnostics, and reproducible developer workflows.",
        ),
        (
            "self_learning",
            "adaptive-learning",
            "Propose reusable skills from evidence through a bounded validation and approval loop without mutating core skills automatically.",
        ),
    )
    for name, domain, description in definitions:
        if name == "application_development":
            registry.register(
                Skill(
                    name,
                    domain,
                    description,
                    _tag(name),
                    instructions=protocol,
                    protocol_id=APPLICATION_DEVELOPMENT_PROTOCOL_ID,
                    protocol_version=APPLICATION_DEVELOPMENT_PROTOCOL_VERSION,
                )
            )
        else:
            registry.register(Skill(name, domain, description, _tag(name)))
    return registry


def install_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    registry.register(Tool("echo", "Deterministic local diagnostic tool.", _tag("tool:echo")))
    registry.register(Tool("summarize", "Local summary adapter for smoke/testing.", _tag("tool:summarize")))

    schedule_generate = ScheduleGenerateTool()
    registry.register(
        Tool(
            schedule_generate.name,
            schedule_generate.description,
            schedule_generate,
        )
    )
    registry.register(
        Tool(
            "github.repository_status",
            "Read-only GitHub repository status, branch, pull requests, Actions, and artifacts.",
            _github_repository_status,
        )
    )
    install_web_tool(registry)

    return registry
