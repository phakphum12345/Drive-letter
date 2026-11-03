from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from .cloud_local_http import CloudLocalHTTP
    from .cloud_local_store import CloudLocalStore
except ImportError:  # pragma: no cover - direct unittest discovery
    from cloud_local_http import CloudLocalHTTP
    from cloud_local_store import CloudLocalStore


class CloudLocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CloudLocalStore(sqlite_path=Path(self.temp.name) / "runtime.sqlite3")

        def resolve(headers):
            user_id = headers.get("X-Test-User")
            if not user_id:
                raise ValueError("missing session")
            return {"user_id": user_id, "email": user_id + "@example.test", "role": "OWNER"}

        self.api = CloudLocalHTTP(self.store, resolve)
        self.user_headers = {"X-Test-User": "user-a"}

    def tearDown(self):
        self.temp.cleanup()

    def request(self, method, path, headers=None, body=None):
        return self.api.dispatch(method, path, headers or {}, body or {})

    def create_local_job(self, **overrides):
        body = {
            "execution_mode": "LOCAL",
            "data_classification": "LOCAL_ONLY",
            "task_type": "repo.audit",
            "required_capabilities": ["repository.inspect"],
            "idempotency_key": "idempotency-key-00000001",
            "source_sha": "a" * 40,
            "owner_id": "attacker-controlled",
        }
        body.update(overrides)
        status, result = self.request("POST", "/api/v1/jobs", self.user_headers, body)
        self.assertEqual(201, status, result)
        return result["job"]

    def enroll_agent(self, capabilities=None):
        status, grant = self.request(
            "POST", "/api/v1/agents/enrollment-grants", self.user_headers, {"ttl_seconds": 600}
        )
        self.assertEqual(201, status, grant)
        status, enrolled = self.request(
            "POST", "/api/v1/agents/enroll", {},
            {
                "enrollment_token": grant["enrollment_token"],
                "device_id": "device-1",
                "protocol_versions": ["1.0"],
                "capabilities": capabilities if capabilities is not None else [{"name": "repository.inspect", "version": "1"}],
                "os_name": "Windows",
                "os_version": "11",
                "agent_version": "1.0.0",
            },
        )
        self.assertEqual(201, status, enrolled)
        return enrolled["agent"], {"Authorization": "Bearer " + enrolled["agent_token"]}

    def test_job_owner_and_actor_are_derived_from_session(self):
        job = self.create_local_job()
        self.assertEqual("user-a", job["owner_id"])
        self.assertEqual("user-a", job["actor"]["principal_id"])
        status, result = self.request("GET", "/api/v1/jobs/" + job["job_id"], self.user_headers)
        self.assertEqual(200, status)
        self.assertEqual(job["job_id"], result["job"]["job_id"])
        status, _ = self.request("GET", "/api/v1/jobs/" + job["job_id"], {"X-Test-User": "user-b"})
        self.assertEqual(404, status)

    def test_local_only_job_is_rejected_for_cloud_or_auto(self):
        for mode in ("CLOUD", "AUTO"):
            status, result = self.request(
                "POST", "/api/v1/jobs", self.user_headers,
                {
                    "execution_mode": mode, "data_classification": "LOCAL_ONLY",
                    "task_type": "repo.audit", "idempotency_key": "key-for-mode-" + mode + "-0001",
                    "source_sha": "a" * 40,
                },
            )
            self.assertEqual(403, status)
            self.assertEqual("locality_policy_denied", result["error"])

    def test_repo_audit_requires_source_sha_and_adds_repository_capability(self):
        status, missing = self.request(
            "POST", "/api/v1/jobs", self.user_headers,
            {"execution_mode": "LOCAL", "data_classification": "LOCAL_ONLY",
             "task_type": "repo.audit", "idempotency_key": "repo-audit-key-00000001"},
        )
        self.assertEqual(400, status)
        self.assertIn("source_sha", missing["detail"])
        status, created = self.request(
            "POST", "/api/v1/jobs", self.user_headers,
            {"execution_mode": "LOCAL", "data_classification": "LOCAL_ONLY",
             "task_type": "repo.audit", "idempotency_key": "repo-audit-key-00000002",
             "source_sha": "d" * 40},
        )
        self.assertEqual(201, status, created)
        self.assertIn("repository.inspect", created["job"]["required_capabilities"])

    def test_cloud_execution_requires_public_data_until_upload_consent_exists(self):
        for classification in ("INTERNAL", "CONFIDENTIAL"):
            status, result = self.request(
                "POST", "/api/v1/jobs", self.user_headers,
                {
                    "execution_mode": "CLOUD", "data_classification": classification,
                    "task_type": "repo.audit", "idempotency_key": "consent-key-" + classification.lower() + "-0001",
                    "source_sha": "a" * 40,
                },
            )
            self.assertEqual(403, status)
            self.assertEqual("cloud_data_consent_required", result["error"])

    def test_user_authentication_is_required_for_job_creation(self):
        status, result = self.request(
            "POST", "/api/v1/jobs", {},
            {"execution_mode": "LOCAL", "data_classification": "LOCAL_ONLY",
             "task_type": "repo.audit", "idempotency_key": "idempotency-key-00000002",
             "source_sha": "a" * 40},
        )
        self.assertEqual(401, status)
        self.assertEqual("authentication_required", result["error"])

    def test_agent_enrollment_heartbeat_claim_and_lease_transition(self):
        self.create_local_job()
        agent, agent_headers = self.enroll_agent()
        status, heartbeat = self.request("POST", "/api/v1/agents/heartbeat", agent_headers, {})
        self.assertEqual(200, status)
        self.assertEqual("ACTIVE", heartbeat["agent"]["lifecycle_state"])

        status, claim = self.request("POST", "/api/v1/agents/claim", agent_headers, {})
        self.assertEqual(200, status)
        job = claim["job"]
        self.assertEqual(agent["agent_id"], job["assigned_worker_id"])
        lease = job["lease_token"]

        status, running = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/transition", agent_headers,
            {"lease_token": lease, "status": "RUNNING", "stage_id": "repo.audit"},
        )
        self.assertEqual(200, status, running)
        self.assertEqual("RUNNING", running["job"]["status"])

        status, renewed = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/lease/renew", agent_headers,
            {"lease_token": lease, "lease_seconds": 120},
        )
        self.assertEqual(200, status, renewed)
        self.assertTrue(renewed["job"]["lease_expires_at"])

        status, completed = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/transition", agent_headers,
            {"lease_token": lease, "status": "COMPLETED", "stage_id": "repo.audit"},
        )
        self.assertEqual(200, status, completed)
        self.assertEqual("COMPLETED", completed["job"]["status"])
        self.assertIsNone(completed["job"]["lease_id"])
        self.assertEqual("job.completed", completed["evidence"]["event_type"])
        status, evidence_list = self.request(
            "GET", f"/api/v1/jobs/{job['job_id']}/evidence", self.user_headers
        )
        self.assertEqual(200, status)
        self.assertCountEqual(["job.started", "job.completed"], [item["event_type"] for item in evidence_list["evidence"]])


    def test_agent_without_repository_inspect_cannot_claim_repo_audit(self):
        self.create_local_job()
        _, headers = self.enroll_agent(capabilities=[{"name": "filesystem.read", "version": "1"}])
        status, claim = self.request("POST", "/api/v1/agents/claim", headers, {})
        self.assertEqual(200, status, claim)
        self.assertIsNone(claim["job"])

    def test_agent_token_is_required_and_grant_is_single_use(self):
        status, grant = self.request(
            "POST", "/api/v1/agents/enrollment-grants", self.user_headers, {}
        )
        self.assertEqual(201, status)
        enrollment = {
            "enrollment_token": grant["enrollment_token"], "device_id": "device-1",
            "protocol_versions": ["1.0"], "capabilities": [],
            "os_name": "Windows", "agent_version": "1.0.0",
        }
        status, enrolled = self.request("POST", "/api/v1/agents/enroll", {}, enrollment)
        self.assertEqual(201, status)
        self.assertNotIn("agent_token", enrolled["agent"])
        status, duplicate = self.request("POST", "/api/v1/agents/enroll", {}, enrollment)
        self.assertEqual(401, status)
        self.assertEqual("enrollment_grant_invalid_or_expired", duplicate["error"])
        status, result = self.request("POST", "/api/v1/agents/claim", {}, {})
        self.assertEqual(401, status)
        self.assertEqual("agent_authentication_required", result["error"])

    def test_agent_evidence_is_server_scoped_and_append_only(self):
        job = self.create_local_job()
        agent, headers = self.enroll_agent()
        status, claim = self.request("POST", "/api/v1/agents/claim", headers, {})
        self.assertEqual(200, status)
        status, result = self.request(
            "POST", "/api/v1/evidence", headers,
            {"job_id": job["job_id"], "stage_id": "stage-1",
             "event_type": "job.started", "result": "INFO"},
        )
        self.assertEqual(201, status, result)
        evidence = result["evidence"]
        self.assertEqual("user-a", evidence["owner_id"])
        self.assertEqual(agent["agent_id"], evidence["actor_id"])
        self.assertEqual("a" * 40, evidence["source_sha"])
        status, listing = self.request(
            "GET", f"/api/v1/jobs/{job['job_id']}/evidence", self.user_headers
        )
        self.assertEqual(200, status)
        self.assertEqual([evidence], listing["evidence"])

    def test_checkpoint_create_list_and_resume_preflight(self):
        job = self.create_local_job()
        agent, headers = self.enroll_agent()
        status, claim = self.request("POST", "/api/v1/agents/claim", headers, {})
        self.assertEqual(200, status)
        lease = claim["job"]["lease_token"]
        status, running = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/transition", headers,
            {"lease_token": lease, "status": "RUNNING"},
        )
        self.assertEqual(200, status, running)
        status, saved = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/checkpoints", headers,
            {"lease_token": lease, "stage_id": "stage-1", "workflow_state": "PAUSED",
             "next_action": "resume after review", "evidence_refs": []},
        )
        self.assertEqual(201, status, saved)
        checkpoint_id = saved["checkpoint"]["checkpoint_id"]
        self.assertEqual(agent["agent_id"], saved["checkpoint"]["created_by"])
        status, listing = self.request(
            "GET", f"/api/v1/jobs/{job['job_id']}/checkpoints", self.user_headers
        )
        self.assertEqual(200, status)
        self.assertEqual(1, listing["count"])
        status, resume = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/checkpoints/{checkpoint_id}/resume", self.user_headers, {}
        )
        self.assertEqual(200, status)
        self.assertEqual("READY", resume["resume"]["status"])

    def test_owner_can_revoke_agent_and_revoked_token_stops_working(self):
        agent, headers = self.enroll_agent()
        status, result = self.request(
            "POST", f"/api/v1/agents/{agent['agent_id']}/revoke", self.user_headers, {}
        )
        self.assertEqual(200, status)
        status, denied = self.request("POST", "/api/v1/agents/heartbeat", headers, {})
        self.assertEqual(401, status)
        self.assertEqual("agent_authentication_required", denied["error"])



    def test_evidence_recovery_is_provenance_labeled_and_idempotent(self):
        job = self.create_local_job()
        agent, headers = self.enroll_agent()
        status, claim = self.request("POST", "/api/v1/agents/claim", headers, {})
        self.assertEqual(200, status)
        lease = claim["job"]["lease_token"]
        status, started = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/transition", headers,
            {"lease_token": lease, "status": "RUNNING"},
        )
        self.assertEqual(200, status, started)
        status, checkpoint = self.request(
            "POST", f"/api/v1/jobs/{job['job_id']}/checkpoints", headers,
            {"lease_token": lease, "stage_id": "stage-recovery", "workflow_state": "PAUSED",
             "next_action": "resume", "evidence_refs": []},
        )
        self.assertEqual(201, status, checkpoint)
        path = f"/api/v1/jobs/{job['job_id']}/evidence/recover"
        payload = {"stage_id": "stage-recovery", "event_type": "artifact.committed"}
        status, recovered = self.request("POST", path, self.user_headers, payload)
        self.assertEqual(201, status, recovered)
        self.assertEqual("RECOVERED", recovered["recovery_status"])
        self.assertEqual("RECOVERED", recovered["evidence"]["evidence_class"])
        self.assertEqual("artifact.committed", recovered["evidence"]["recovered_event_type"])
        self.assertIn(checkpoint["checkpoint"]["checkpoint_id"], recovered["evidence"]["recovery_sources"])
        status, again = self.request("POST", path, self.user_headers, payload)
        self.assertEqual(200, status, again)
        self.assertTrue(again["reused"])
        self.assertEqual(recovered["evidence"]["evidence_id"], again["evidence"]["evidence_id"])
        status, resolved = self.request("GET", f"/api/v1/jobs/{job['job_id']}/evidence/resolve?stage_id=stage-recovery&event_type=artifact.committed", self.user_headers)
        self.assertEqual(200, status, resolved)
        self.assertEqual("EVIDENCE_FALLBACK", resolved["resolution"]["route"])
        self.assertTrue(resolved["audit_id"])
        audit = self.store.list_recovery_audit("user-a", job["job_id"])
        self.assertEqual(1, len(audit))
        self.assertEqual("EVIDENCE_FALLBACK", audit[0]["selected_route"])
        self.assertEqual("artifact.committed", audit[0]["requested_event_type"])
        self.assertNotIn("lease_token", audit[0])
        status, audit_response = self.request(
            "GET", f"/api/v1/jobs/{job['job_id']}/evidence/recovery-audit", self.user_headers
        )
        self.assertEqual(200, status, audit_response)
        self.assertEqual(1, audit_response["count"])
        status, foreign_audit = self.request(
            "GET", f"/api/v1/jobs/{job['job_id']}/evidence/recovery-audit",
            {"X-Test-User": "user-b"},
        )
        self.assertEqual(404, status)
        # Exact original wins over a checkpoint-only recovery route.
        status, empty = self.request("GET", f"/api/v1/jobs/{job['job_id']}/evidence/resolve?stage_id=stage-missing&event_type=artifact.committed", self.user_headers)
        self.assertEqual(200, status, empty)
        self.assertEqual("MISSING", empty["resolution"]["status"])

    def test_evidence_resolver_never_crosses_owner_job_or_source_sha(self):
        try:
            from .evidence_recovery import resolve_evidence
        except ImportError:
            from evidence_recovery import resolve_evidence
        records = [{"evidence_id": "foreign", "owner_id": "user-b", "job_id": "job-x",
                    "stage_id": "stage-1", "event_type": "job.completed", "source_sha": "a" * 40,
                    "evidence_class": "ORIGINAL"}]
        result = resolve_evidence(records, owner_id="user-a", job_id="job-x",
                                  stage_id="stage-1", event_type="job.completed", source_sha="a" * 40)
        self.assertEqual("MISSING", result["status"])
        self.assertIsNone(result["evidence"])

    def test_evidence_resolver_does_not_trust_unverified_replica(self):
        try:
            from .evidence_recovery import resolve_evidence
        except ImportError:
            from evidence_recovery import resolve_evidence
        replica = {
            "evidence_id": "replica-unverified", "owner_id": "user-a", "job_id": "job-x",
            "stage_id": "stage-1", "event_type": "job.completed", "source_sha": "b" * 40,
            "evidence_class": "REPLICA",
        }
        result = resolve_evidence([replica], owner_id="user-a", job_id="job-x",
                                  stage_id="stage-1", event_type="job.completed",
                                  source_sha="b" * 40)
        self.assertEqual("MISSING", result["status"])
        self.assertIsNone(result["evidence"])

    def test_evidence_resolver_prefers_original_then_fallback(self):
        try:
            from .evidence_recovery import resolve_evidence
        except ImportError:
            from evidence_recovery import resolve_evidence
        base = {"owner_id": "user-a", "job_id": "job-x", "stage_id": "stage-1",
                "event_type": "job.completed", "source_sha": "b" * 40}
        recovered = dict(base, evidence_id="recovered", event_type="evidence.recovered",
                         recovered_event_type="job.completed", evidence_class="RECOVERED",
                         recovery_sources=["cp-verified"], recovery_reason="verified checkpoint fallback",
                         recovery_key="c" * 64)
        original = dict(base, evidence_id="original", evidence_class="ORIGINAL")
        self.assertEqual("EVIDENCE_FALLBACK", resolve_evidence([recovered], owner_id="user-a",
            job_id="job-x", stage_id="stage-1", event_type="job.completed",
            source_sha="b" * 40)["route"])
        self.assertEqual("PRIMARY", resolve_evidence([recovered, original], owner_id="user-a",
            job_id="job-x", stage_id="stage-1", event_type="job.completed",
            source_sha="b" * 40)["route"])



    def test_resolver_switches_to_verified_checkpoint_when_primary_evidence_missing(self):
        try:
            from .evidence_recovery import resolve_evidence
        except ImportError:
            from evidence_recovery import resolve_evidence
        checkpoint = {"checkpoint_id": "cp-1", "owner_id": "owner-1", "job_id": "job-1",
                      "stage_id": "stage-1", "source_sha": "c" * 40}
        result = resolve_evidence([], owner_id="owner-1", job_id="job-1",
                                  stage_id="stage-1", event_type="artifact.committed",
                                  source_sha="c" * 40, checkpoints=[checkpoint])
        self.assertEqual("RECOVERY_AVAILABLE", result["status"])
        self.assertEqual("CHECKPOINT_FALLBACK", result["route"])
        self.assertEqual("cp-1", result["checkpoint_id"])

    def test_recovery_rejects_checkpoint_from_another_stage(self):
        try:
            from .evidence_recovery import build_recovered_evidence
        except ImportError:
            from evidence_recovery import build_recovered_evidence
        job = {"owner_id": "owner-1", "job_id": "job-1", "source_sha": "d" * 40,
               "policy_decision_id": "policy-1", "correlation_id": "corr-1"}
        checkpoint = {"checkpoint_id": "cp-other", "owner_id": "owner-1", "job_id": "job-1",
                      "stage_id": "stage-other", "source_sha": "d" * 40}
        result = build_recovered_evidence(job=job, checkpoints=[checkpoint], evidence=[],
            owner_id="owner-1", stage_id="stage-requested", event_type="artifact.committed",
            checkpoint=checkpoint, actor_id="owner-1")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
