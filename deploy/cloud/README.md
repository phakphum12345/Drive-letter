# Research OS API container

This is the production-oriented API image for the Cloud + Local architecture. It is separate from \`research-os/Dockerfile\`, which remains the example application image.

## Build and test

Run from the repository root:

\`\`\`bash
docker build -f deploy/cloud/Dockerfile.api -t research-os-api:local .
docker run --rm -p 8080:8080 \
  -e RESEARCH_OS_DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DB' \
  -e RESEARCH_OS_SESSION_SECRET='INJECT_A_SECRET_AT_RUNTIME' \
  research-os-api:local
\`\`\`

Do not put real credentials in the Dockerfile, compose files, GitHub workflow, or image build arguments. Inject them from a secret manager at runtime.

## Cloud-mode safety

- \`RESEARCH_OS_DATABASE_URL\` must reference PostgreSQL. Cloud mode fails closed instead of silently creating an ephemeral SQLite database.
- PostgreSQL driver and JSON Schema validator are pinned in-repository.
- The image runs as UID 10001 and exposes port 8080.
- \`/health\` is the container liveness endpoint.
- The \`/var/lib/research-os\` volume is retained for legacy API subsystems that still use local files. It must be mounted to durable, access-controlled storage before deployment; do not scale replicas while file-backed subsystems remain active.
- Cloud/AUTO jobs remain queued until a Cloud worker is deployed. Local Agent execution requires a separately packaged outbound-only Windows Agent.
- Existing OAuth, conversation, identity and legacy Agent JSON stores are not migrated by this image. Do not deploy this container to production until their persistence/backup and restore plan is reviewed.
- No Azure resources, Render database, network exposure or data migration is created by this PR.

## Current readiness

The container is buildable and runs the API. It is not an authorization to provision or deploy production infrastructure. PostgreSQL provisioning, secrets, durable volume, worker pool, Local Agent enrollment on Windows, checkpoint recovery and full end-to-end verification remain gated tasks.
