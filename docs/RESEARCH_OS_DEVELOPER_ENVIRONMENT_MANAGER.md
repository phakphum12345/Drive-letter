# Research OS Developer Environment Manager

**Document ID:** RESEARCH-OS-DEVENV-001  
**Version:** 1.0.0  
**Status:** Candidate  
**Authority:** FINAL_GATE  
**Mode:** Read-only inventory

## Purpose

Provide a safe first step for integrating the local developer environment into Research OS. The initial capability discovers common developer executables through PATH and returns a machine-readable JSON report.

## Scope

- Detect Git, PowerShell, WSL, VS Code CLI, .NET, Flutter, Android Debug Bridge, Docker, and Visual Studio build tools when discoverable on PATH.
- Report per-tool `PASS` or `SKIPPED`, aggregate counts, and explicit limitations.
- Keep the inventory deterministic and testable by injecting the PATH lookup function.
- Never launch discovered executables, install dependencies, edit Visual Studio settings, modify services/registry, or change environment variables.

## Non-goals

- Does not prove version, health, license, SDK completeness, emulator readiness, or MCP server connectivity.
- Does not read or expose credential values or MCP configuration contents.
- Does not authorize builds, deployments, merges, or privileged operations.

## Integration contract

- Module: `tools/developer_environment.py`
- Test: `tools/test_developer_environment.py`
- Output schema version: `1`
- Mode: `READ_ONLY`
- `PASS` means PATH discovery succeeded only.
- `SKIPPED` means the executable was not found; it is not silently treated as a test pass.
- Release or execution decisions remain outside this module and must use the existing authorization and Final Gate workflow.

## Validation

Run from the repository root:

```powershell
python -m unittest tools.test_developer_environment -v
python tools/developer_environment.py
```

These commands are candidate validation instructions. A passing result must be recorded from CI or an actual test run; file presence alone is not evidence of validation.
