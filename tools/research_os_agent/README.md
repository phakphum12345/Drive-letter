# Research OS Windows Local Agent

The Local Agent is a separate Windows Service. It initiates outbound HTTPS requests to the Research OS API and does not open an inbound listener.

## Initial supported task

- \`repo.audit\`: read-only inspection of the configured Git repository root.
- Advertises only \`repository.inspect\` when a workspace root is configured.
- Verifies the checked-out HEAD matches the job \`source_sha\`.
- Runs fixed Git commands through \`ProcessStartInfo.ArgumentList\` with shell execution disabled.
- Sends only a SHA-256 digest of the Git status summary; filenames and file contents remain on the PC.
- Rejects unsupported task types. It never runs arbitrary shell, PowerShell, scripts, or remote code.

## Install and configure

Run an elevated PowerShell session from the extracted Research OS package:

\`\`\`powershell
.\\scripts\\research-os-agent-service.ps1 -Action install
.\\agent_service\\ResearchOS.LocalAgent.exe --configure
\`\`\`

The interactive configuration asks for the API HTTPS URL, a one-time enrollment grant from the signed-in user's Research OS account, and an optional Git repository root. The enrollment grant and subsequent Agent bearer token are encrypted with Windows DPAPI LocalMachine under ProgramData. The bearer token is never written to logs.

To remove the service:

\`\`\`powershell
.\\scripts\\research-os-agent-service.ps1 -Action uninstall
\`\`\`

Uninstall preserves the encrypted Agent configuration and local data directory. Delete that directory separately only when the owner explicitly wants to revoke and remove local Agent state.

## Safety boundaries

- No inbound HTTP server, port listener, remote desktop or file-share endpoint.
- HTTPS required; HTTP is accepted only for localhost development.
- Agent token revocation stops work; re-enrollment requires a new owner-issued one-time grant.
- Only \`LOCAL\` and \`HYBRID\` jobs can be claimed by the Local Agent.
- A stale lease or source SHA mismatch prevents job completion.
- Cloud execution, file upload, filesystem write, process execution and arbitrary task plugins are not implemented.
