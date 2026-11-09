# Research OS — iPhone over Tailscale

## Purpose

Research OS API, Friend, and Developer API bind to loopback using OS-assigned ports. The actual API endpoint is published atomically to:

`%ProgramData%\\ResearchOS\\runtime\\api.json`

The iPhone does not connect to a Windows loopback address. It reaches the Windows host through Tailscale Serve over HTTPS.

## Windows setup

Run an elevated PowerShell session on the Research OS Windows machine:

```powershell
& "<Research OS install root>\\scripts\\configure-research-os-tailscale.ps1"
```

The helper:

1. reads and validates the current generated API port from `runtime/api.json`;
2. verifies `http://127.0.0.1:<GENERATED_API_PORT>/health`;
3. reads the Windows device's Tailscale MagicDNS name;
4. configures Tailscale Serve to proxy HTTPS to that generated loopback port;
5. prints the private HTTPS API base URL and Google OAuth callback URLs.

No API port is hard-coded. If the API service restarts and receives a new OS-assigned port, rerun the helper to refresh the Tailscale Serve target.

To also place the HTTPS callback URLs into the Research OS Windows Service environment:

```powershell
& "<Research OS install root>\\scripts\\configure-research-os-tailscale.ps1" -ConfigureGoogleRedirects
```

The callback URLs must also be registered in the Google OAuth client configuration before Google sign-in can complete through the Tailscale endpoint.

## iPhone connectivity

The iPhone must remain connected to the same Tailscale tailnet.

Verify the API from Safari using the HTTPS URL printed by the helper, followed by:

`/health`

Expected response is the normal Research OS health JSON.

## iOS IPA

The iOS workflow supports a manual API endpoint override.

In GitHub Actions, run **Research OS iOS IPA** with:

`api_base_url=https://<windows-device>.<tailnet>.ts.net`

The resulting IPA embeds that endpoint through `RESEARCH_OS_API_BASE_URL`.

## Security model

Do **not** change the Windows Research OS API service to bind directly to `0.0.0.0` just to support the iPhone.

The intended private path is:

`iPhone → Tailscale HTTPS → Tailscale Serve → 127.0.0.1:<GENERATED_API_PORT> → Research OS API`

Tailscale Serve provides the private HTTPS bridge while the API itself remains loopback-bound.

## Operational checks

On Windows, inspect the current generated endpoint:

```powershell
Get-Content "$env:ProgramData\\ResearchOS\\runtime\\api.json" -Raw | ConvertFrom-Json
tailscale serve status
```

Do not use `Get-NetTCPConnection -LocalPort 8787` or any other remembered port as the source of truth. Read the current port from the registry record.
