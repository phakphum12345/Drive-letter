import unittest

from tools.validate_generate_orchestrator import (
    WORKFLOWS,
    unsupported_required_inputs,
    workflow_dispatch_inputs,
)


class GenerateOrchestratorInputTests(unittest.TestCase):
    def test_required_choice_with_default_is_supported(self):
        self.assertEqual(
            unsupported_required_inputs({
                "deployment_mode": {
                    "description": "API endpoint profile",
                    "required": True,
                    "type": "choice",
                    "options": ["local", "render"],
                    "default": "local",
                }
            }),
            [],
        )

    def test_artifact_build_default_is_supported_and_orchestrator_passes_it(self):
        schema = workflow_dispatch_inputs(WORKFLOWS / "artifacts-build.yml")
        self.assertEqual(schema["deployment_mode"]["default"], "local")
        self.assertEqual(unsupported_required_inputs(schema), [])
        source = (WORKFLOWS / "generate-orchestrator.yml").read_text(encoding="utf-8")
        self.assertIn('elif isinstance(spec, dict) and "default" in spec:', source)
        self.assertIn('inputs[name] = spec["default"]', source)

    def test_required_unknown_input_without_default_stays_blocking(self):
        self.assertEqual(
            unsupported_required_inputs({
                "unrecognized_required_input": {"required": True, "type": "string"}
            }),
            ["unrecognized_required_input"],
        )

    def test_orchestrator_supported_required_inputs_remain_supported(self):
        self.assertEqual(
            unsupported_required_inputs({"target_sha": {"required": True, "type": "string"}}),
            [],
        )


if __name__ == "__main__":
    unittest.main()
