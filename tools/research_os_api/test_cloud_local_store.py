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
