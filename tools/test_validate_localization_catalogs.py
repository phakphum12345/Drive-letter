"""Unit tests for the standalone localization catalog quality gate."""
import json
import tempfile
import unittest
from pathlib import Path

from validate_localization_catalogs import DuplicateKeyError, load_catalog, validate


class LocalizationCatalogTests(unittest.TestCase):
    def test_matching_catalogs_pass(self):
        source = {"title": "Hello", "count": "{count} results"}
        target = {"title": "สวัสดี", "count": "{count} รายการ"}
        self.assertEqual(validate(source, target), [])

    def test_missing_and_unknown_keys_fail(self):
        errors = validate({"one": "One", "two": "Two"}, {"one": "หนึ่ง", "extra": "เพิ่ม"})
        self.assertTrue(any("missing key: two" in error for error in errors))
        self.assertTrue(any("unknown key: extra" in error for error in errors))

    def test_empty_translation_fails(self):
        self.assertIn("empty translation: greeting", validate({"greeting": "Hello"}, {"greeting": "  "}))

    def test_placeholder_mismatch_fails(self):
        errors = validate({"count": "{count} results"}, {"count": "{total} รายการ"})
        self.assertTrue(any("placeholder mismatch: count" in error for error in errors))

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"key":"first","key":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_catalog(path)

    def test_non_string_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"count": 2}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "all keys and values must be strings"):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
