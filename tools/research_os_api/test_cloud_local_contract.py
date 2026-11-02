from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = ROOT / "contracts" / "research_os" / "cloud_local" / "v1"
FIXTURE_ROOT = ROOT / "tools" / "research_os_api" / "tests" / "fixtures" / "cloud_local"

FIXTURES = {
    "job.schema.json": ("job-cloud.json", "job-local.json"),
    "agent.schema.json": ("agent.json",),
    "checkpoint.schema.json": ("checkpoint.json",),
    "evidence.schema.json": ("evidence.json",),
}


class CloudLocalContractTests(unittest.TestCase):
    def load_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def setUp(self):
        self.schemas = {
            name: self.load_json(SCHEMA_ROOT / name)
            for name in FIXTURES
        }

    def test_all_schemas_are_valid_draft_2020_12(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_golden_fixtures_validate_against_their_contract(self):
        for schema_name, fixture_names in FIXTURES.items():
            validator = Draft202012Validator(
                self.schemas[schema_name], format_checker=FormatChecker()
            )
            for fixture_name in fixture_names:
                with self.subTest(schema=schema_name, fixture=fixture_name):
                    validator.validate(self.load_json(FIXTURE_ROOT / fixture_name))

    def test_local_only_job_cannot_use_cloud_execution(self):
        job = self.load_json(FIXTURE_ROOT / "job-local.json")
        job["execution_mode"] = "CLOUD"
        validator = Draft202012Validator(
            self.schemas["job.schema.json"], format_checker=FormatChecker()
        )
        self.assertFalse(validator.is_valid(job))

    def test_cloud_job_cannot_claim_local_only_data(self):
        job = self.load_json(FIXTURE_ROOT / "job-cloud.json")
        job["data_classification"] = "LOCAL_ONLY"
        validator = Draft202012Validator(
            self.schemas["job.schema.json"], format_checker=FormatChecker()
        )
        self.assertFalse(validator.is_valid(job))

    def test_unknown_job_state_is_rejected(self):
        job = self.load_json(FIXTURE_ROOT / "job-cloud.json")
        job["status"] = "MAGIC_COMPLETE"
        validator = Draft202012Validator(self.schemas["job.schema.json"])
        self.assertFalse(validator.is_valid(job))

    def test_missing_owner_scope_is_rejected(self):
        job = self.load_json(FIXTURE_ROOT / "job-cloud.json")
        del job["owner_id"]
        validator = Draft202012Validator(self.schemas["job.schema.json"])
        self.assertFalse(validator.is_valid(job))

    def test_unrecognized_secret_fields_are_rejected(self):
        job = self.load_json(FIXTURE_ROOT / "job-cloud.json")
        job["access_token"] = "must-never-be-in-a-contract-payload"
        validator = Draft202012Validator(self.schemas["job.schema.json"])
        self.assertFalse(validator.is_valid(job))

    def test_agent_credentials_are_not_part_of_the_agent_contract(self):
        agent = self.load_json(FIXTURE_ROOT / "agent.json")
        agent["enrollment_secret"] = "must-not-be-serialized"
        validator = Draft202012Validator(self.schemas["agent.schema.json"])
        self.assertFalse(validator.is_valid(agent))

    def test_checkpoint_rejects_transcript_or_reasoning_fields(self):
        checkpoint = self.load_json(FIXTURE_ROOT / "checkpoint.json")
        checkpoint["full_transcript"] = "not permitted"
        validator = Draft202012Validator(self.schemas["checkpoint.schema.json"])
        self.assertFalse(validator.is_valid(checkpoint))

    def test_checkpoint_rejects_sensitive_nested_workflow_context(self):
        validator = Draft202012Validator(self.schemas["checkpoint.schema.json"])
        for field in ("full_transcript", "reasoning", "access_token"):
            with self.subTest(field=field):
                checkpoint = self.load_json(FIXTURE_ROOT / "checkpoint.json")
                checkpoint["workflow_context"][field] = "not permitted"
                self.assertFalse(validator.is_valid(checkpoint))


if __name__ == "__main__":
    unittest.main()
