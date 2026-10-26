"""Read-only developer-tool inventory for Research OS.

This module detects whether common developer executables are discoverable on PATH.
It does not launch tools, install packages, modify settings, or grant execution authority.
"""
from __future__ import annotations

import json
import platform
import shutil
from typing import Callable

TOOL_NAMES = (
    "git",
    "pwsh",
    "powershell",
    "wsl",
    "code",
    "dotnet",
    "flutter",
    "adb",
    "docker",
    "devenv",
    "msbuild",
)


def inspect_environment(which: Callable[[str], str | None] = shutil.which) -> dict:
    """Return a deterministic, read-only inventory of discoverable developer tools."""
    tools = []
    for name in TOOL_NAMES:
        executable = which(name)
        tools.append(
            {
                "name": name,
                "status": "PASS" if executable else "SKIPPED",
                "available": bool(executable),
                "path": executable if executable else None,
                "check": "PATH_DISCOVERY_ONLY",
            }
        )
    available = sum(item["available"] for item in tools)
    return {
        "schema_version": 1,
        "component": "research_os.developer_environment",
        "mode": "READ_ONLY",
        "platform": platform.system().lower(),
        "summary": {
            "status": "PASS" if available else "SKIPPED",
            "checked": len(tools),
            "available": available,
            "missing": len(tools) - available,
        },
        "tools": tools,
        "limitations": [
            "PATH discovery does not prove a tool is healthy or correctly configured.",
            "No executable was launched and no settings or files were changed.",
            "This inventory grants no authorization to build, install, deploy, or merge.",
        ],
    }


def main() -> int:
    print(json.dumps(inspect_environment(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
