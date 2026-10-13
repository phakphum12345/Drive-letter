from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("m2_source_integrity_audit.py")
SPEC = importlib.util.spec_from_file_location("m2_source_integrity_audit", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load M.2 source-integrity audit module")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class SourceIntegrityByteClassificationTests(unittest.TestCase):
    def test_detects_bom_only_file_as_corruption(self) -> None:
        findings = AUDIT.classify_bytes("tools/create_change_queue.py", b"\xef\xbb\xbf")
        self.assertIn("BOM_ONLY_EMPTY_FILE", {item["code"] for item in findings})

    def test_detects_bom_prefixed_source(self) -> None:
        findings = AUDIT.classify_bytes("tools/example.py", b"\xef\xbb\xbfprint('x')\n")
        self.assertIn("UTF8_BOM", {item["code"] for item in findings})

    def test_detects_nul_byte_in_text_source(self) -> None:
        findings = AUDIT.classify_bytes("tools/example.py", b"print('x')\x00\n")
        self.assertIn("TEXT_NUL_BYTE", {item["code"] for item in findings})

    def test_does_not_treat_binary_image_nul_as_text_corruption(self) -> None:
        findings = AUDIT.classify_bytes("assets/logo.png", b"\x89PNG\x00binary")
        self.assertEqual(findings, [])

    def test_zero_byte_source_is_reported(self) -> None:
        findings = AUDIT.classify_bytes("lib/main.dart", b"")
        self.assertIn("ZERO_BYTE_TEXT_FILE", {item["code"] for item in findings})

    def test_clean_utf8_source_passes_byte_checks(self) -> None:
        self.assertEqual(AUDIT.classify_bytes("lib/main.dart", "void main() {}\n".encode()), [])


if __name__ == "__main__":
    unittest.main()
