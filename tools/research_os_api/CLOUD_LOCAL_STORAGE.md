# Cloud + Local runtime storage

`cloud_local_store.py` is the transactional persistence boundary for Cloud + Local jobs, Local Agents, one-time enrollment grants, leases and append-only evidence.

- Local development and tests use SQLite.
- Cloud deployments must set `RESEARCH_OS_DATABASE_URL` to a PostgreSQL URL and install `cloud-local-requirements.txt`.
- PostgreSQL claims use row-level `FOR UPDATE SKIP LOCKED`; Local Agents can claim only `LOCAL` and `HYBRID` jobs owned by the same principal.
- Enrollment grants and Agent bearer tokens are stored only as SHA-256 fingerprints. The Agent token is returned once at enrollment.
- Job idempotency is scoped by owner. All reads, claims and mutations carry owner scope.
- This storage layer does not itself grant execution authority. HTTP routes must authenticate the user/Agent and validate the v1 JSON Schemas before calling it.

Run local tests with `python -m unittest tools.research_os_api.test_cloud_local_store -v`.
