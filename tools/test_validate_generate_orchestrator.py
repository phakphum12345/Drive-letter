import unittest

from tools.validate_generate_orchestrator import unsupported_required_inputs


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
