# Research OS Cloud + Local Contract v1

**Contract set:** ROS-CL-CONTRACT  
**Version:** 1.0.0-draft  
**Status:** Proposed; no production endpoint consumes these schemas yet  
**Parent architecture:** ROS-CL-00 through ROS-CL-03

## 01. Files

| No. | File | Purpose |
|---:|---|---|
| 01 | `job.schema.json` | Canonical job envelope, execution mode, state and locality constraints |
| 02 | `agent.schema.json` | Registered Local Agent identity, capabilities and lifecycle |
| 03 | `checkpoint.schema.json` | Compact resumable stage state and source lineage |
| 04 | `evidence.schema.json` | Append-oriented execution evidence and provenance |
| 05 | `../../../../tools/research_os_api/tests/fixtures/cloud_local/` | Golden compatibility fixtures |

## 02. Compatibility rules

1. `contract_version` is explicit and versioned.
2. Unknown execution modes, job states, agent lifecycle states and data classifications are rejected.
3. `owner_id` is mandatory. The server must derive/authorize it from the authenticated actor; payload ownership is never trusted by itself.
4. A `LOCAL_ONLY` job cannot be assigned to a Cloud execution mode.
5. Credential material, OAuth tokens, enrollment secrets and bearer tokens are forbidden from contract payloads.
6. Job payloads reference inputs and outputs; they do not embed arbitrary local file contents.
7. Checkpoints contain compact workflow state and references, not chat transcripts or model reasoning.
8. These schemas describe data shape only. They do not authorize an action, approve a side effect, grant execution authority or permit release.

## 03. Validation

The JSON Schemas use JSON Schema Draft 2020-12. Golden fixtures and negative compatibility tests are validated in the Research OS API Spine CI workflow.

Local command:

```bash
python -m pip install -r tools/research_os_api/contract-requirements.txt
python -m unittest tools.research_os_api.test_cloud_local_contract -v
```

## 04. Deliberately not included

- No API routes or runtime dispatch implementation.
- No credential issuance or Local Agent enrollment flow.
- No database, broker, cloud resource or storage migration.
- No public network listener or change to Owner Friend.
- No production compatibility guarantee until a separate implementation PR adds contract negotiation and endpoint tests.
