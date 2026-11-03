# Cloud + Local runtime storage

`cloud_local_store.py` is the transactional persistence boundary for Cloud + Local jobs, Local Agents, one-time enrollment grants, leases and append-only evidence.

- Local development and tests use SQLite.
- Cloud deployments must set `RESEARCH_OS_DATABASE_URL` to a PostgreSQL URL and install `cloud-local-requirements.txt`.
- PostgreSQL claims use row-level `FOR UPDATE SKIP LOCKED`; Local Agents can claim only `LOCAL` and `HYBRID` jobs owned by the same principal.
- Enrollment grants and Agent bearer tokens are stored only as SHA-256 fingerprints. The Agent token is returned once at enrollment.
- Job idempotency is scoped by owner. All reads, claims and mutations carry owner scope.
- The primary API now exposes authenticated `/api/v1` routes for jobs, Agent enrollment/heartbeat/claim/revocation, lease renewal/transitions and evidence. User identity and owner scope are derived from the verified session; Agent routes require a bearer token.
- Job and Agent payloads are validated against the v1 JSON Schemas. LOCAL_ONLY data is denied from CLOUD/AUTO; INTERNAL and CONFIDENTIAL data are denied from Cloud/Hybrid/Auto until an explicit upload-consent policy exists.
- Cloud mode fails closed without PostgreSQL. Existing Render runtime will return 503 for these new routes until `RESEARCH_OS_DATABASE_URL` is configured; no ephemeral SQLite fallback is permitted in cloud mode.
- Cloud worker dispatch, checkpoint API/persistence, lease recovery, Windows Agent service transport, and end-to-end deployment remain follow-up work. This layer does not authorize arbitrary side effects or release actions.
- No existing JSON stores are migrated or deleted.

Run local tests with `python -m unittest tools.research_os_api.test_cloud_local_store -v`.
