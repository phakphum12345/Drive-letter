from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from .cloud_local_store import CloudLocalStore
except ImportError:  # pragma: no cover - direct unittest discovery
    from cloud_local_store import CloudLocalStore


def sample_job(owner="user-a", job_id="job-1", key="idempotency-key-0001"):
    return {
        "contract_version": "1.0", "request_id": "req-1", "correlation_id": "corr-1",
        "created_at": "2026-11-03T00:00:00Z",
        "actor": {"principal_type": "user", "principal_id": owner},
        "owner_id": owner, "job_id": job_id, "execution_mode": "LOCAL",
        "status": "WAITING_FOR_LOCAL_AGENT", "task_type": "repo.audit",
        "required_capabilities": ["filesystem.read"], "data_classification": "LOCAL_ONLY",
        "idempotency_key": key, "input_refs": [], "output_refs": [],
        "policy_decision_id": "cloud-local.local-only.v1", "attempt": 0,
    }


class CloudLocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CloudLocalStore(sqlite_path=Path(self.temp.name) / "runtime.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def enroll(self):
        grant = self.store.create_enrollment_grant("user-a")
        return self.store.enroll_agent(
            grant, owner_id="user-a", device_id="device-1", protocol_versions=["1.0"],
            capabilities=[{"name": "filesystem.read", "version": "1"}],
            os_name="Windows", os_version="11", agent_version="1.0.0",
        )

    def test_job_idempotency_and_owner_scope(self):
        first, replay = self.store.create_job(sample_job())
        second, replayed = self.store.create_job(sample_job(job_id="job-duplicate"))
        self.assertFalse(replay)
        self.assertTrue(replayed)
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertIsNone(self.store.get_job("user-b", first["job_id"]))
        self.assertEqual(1, len(self.store.list_jobs("user-a")))

    def test_enrollment_grant_is_single_use_and_token_is_not_in_contract(self):
        grant = self.store.create_enrollment_grant("user-a")
        agent, token = self.store.enroll_agent(
            grant, owner_id="user-a", device_id="device-1", protocol_versions=["1.0"],
            capabilities=[], os_name="Windows", agent_version="1.0.0",
        )
        self.assertNotIn("token", agent)
        self.assertIsNotNone(self.store.authenticate_agent(token))
        with self.assertRaisesRegex(ValueError, "enrollment_grant_invalid_or_expired"):
            self.store.enroll_agent(
                grant, owner_id="user-a", device_id="device-2", protocol_versions=["1.0"],
                capabilities=[], os_name="Windows", agent_version="1.0.0",
            )

    def test_grant_cannot_cross_owner_boundary(self):
        grant = self.store.create_enrollment_grant("user-a")
        with self.assertRaisesRegex(ValueError, "enrollment_grant_invalid_or_expired"):
            self.store.enroll_agent(
                grant, owner_id="user-b", device_id="device-2", protocol_versions=["1.0"],
                capabilities=[], os_name="Windows", agent_version="1.0.0",
            )

    def test_local_agent_claims_only_matching_local_jobs(self):
        agent, _ = self.enroll()
        self.store.create_job(sample_job())
        claimed = self.store.claim_local_job("user-a", agent["agent_id"])
        self.assertEqual("ASSIGNED", claimed["status"])
        self.assertEqual(agent["agent_id"], claimed["assigned_worker_id"])
        self.assertTrue(claimed["lease_token"])
        self.assertIsNone(self.store.claim_local_job("user-a", agent["agent_id"]))

    def test_lease_is_fenced_by_agent_and_token(self):
        agent, _ = self.enroll()
        self.store.create_job(sample_job())
        claimed = self.store.claim_local_job("user-a", agent["agent_id"])
        self.assertIsNone(self.store.renew_lease("user-a", "other-agent", claimed["job_id"], claimed["lease_token"]))
        renewed = self.store.renew_lease("user-a", agent["agent_id"], claimed["job_id"], claimed["lease_token"])
        self.assertIsNotNone(renewed)
        self.assertEqual(claimed["lease_token"], renewed["lease_id"])

    def test_revoked_agent_cannot_authenticate_or_claim(self):
        agent, token = self.enroll()
        self.assertTrue(self.store.revoke_agent("user-a", agent["agent_id"]))
        self.assertIsNone(self.store.authenticate_agent(token))
        with self.assertRaisesRegex(ValueError, "agent_not_active"):
            self.store.claim_local_job("user-a", agent["agent_id"])

    def test_checkpoints_are_lease_fenced_append_only_and_owner_scoped(self):
        agent, _ = self.enroll()
        source_job = sample_job()
        source_job["source_sha"] = "b" * 40
        self.store.create_job(source_job)
        claimed = self.store.claim_local_job("user-a", agent["agent_id"])
        running = self.store.transition_job("user-a", agent["agent_id"], claimed["job_id"], claimed["lease_token"], "RUNNING")
        self.assertEqual("RUNNING", running["status"])
        checkpoint = {
            "contract_version": "1.0", "checkpoint_id": "cp-1", "job_id": "job-1",
            "owner_id": "user-a", "stage_id": "stage-1", "source_sha": "b" * 40,
            "workflow_state": "PAUSED", "next_action": "resume after review",
            "evidence_refs": [], "created_at": "2026-11-03T00:00:00Z", "created_by": agent["agent_id"],
        }
        saved = self.store.create_checkpoint("user-a", agent["agent_id"], "job-1", claimed["lease_token"], checkpoint)
        self.assertEqual("cp-1", saved["checkpoint_id"])
        self.assertEqual("CHECKPOINTING", self.store.get_job("user-a", "job-1")["status"])
        self.assertEqual([checkpoint], self.store.list_checkpoints("user-a", "job-1"))
        self.assertEqual("READY", self.store.resume_checkpoint("user-a", "job-1", "cp-1")["status"])
        self.assertIsNone(self.store.resume_checkpoint("user-b", "job-1", "cp-1"))
        with self.assertRaises(Exception):
            self.store.create_checkpoint("user-a", agent["agent_id"], "job-1", claimed["lease_token"], checkpoint)

    def test_deferred_checkpoint_never_promotes_to_ready_on_resume(self):
        agent, _ = self.enroll()
        source_job = sample_job()
        source_job["source_sha"] = "c" * 40
        self.store.create_job(source_job)
        claimed = self.store.claim_local_job("user-a", agent["agent_id"])
        self.store.transition_job("user-a", agent["agent_id"], "job-1", claimed["lease_token"], "RUNNING")
        checkpoint = {
            "contract_version": "1.0", "checkpoint_id": "cp-deferred", "job_id": "job-1",
            "owner_id": "user-a", "stage_id": "stage-1", "source_sha": "c" * 40,
            "workflow_state": "DEFERRED", "next_action": "wait for approval",
            "evidence_refs": [], "created_at": "2026-11-03T00:00:00Z", "created_by": agent["agent_id"],
        }
        self.store.create_checkpoint("user-a", agent["agent_id"], "job-1", claimed["lease_token"], checkpoint)
        result = self.store.resume_checkpoint("user-a", "job-1", "cp-deferred")
        self.assertEqual("HOLD", result["status"])
        self.assertIn("checkpoint_not_resumable", result["failures"])

    def test_evidence_is_append_only_and_owner_scoped(self):
        evidence = {
            "contract_version": "1.0", "evidence_id": "ev-1", "job_id": "job-1",
            "owner_id": "user-a", "stage_id": "stage-1", "actor_id": "agent-1",
            "event_type": "job.started", "occurred_at": "2026-11-03T00:00:00Z",
            "result": "INFO", "source_sha": "a" * 40,
            "policy_decision_id": "cloud-local.local-only.v1", "correlation_id": "corr-1",
        }
        self.store.append_evidence("user-a", evidence)
        self.assertEqual([evidence], self.store.list_evidence("user-a", "job-1"))
        self.assertEqual([], self.store.list_evidence("user-b", "job-1"))
        with self.assertRaises(Exception):
            self.store.append_evidence("user-a", evidence)


if __name__ == "__main__":
    unittest.main()
