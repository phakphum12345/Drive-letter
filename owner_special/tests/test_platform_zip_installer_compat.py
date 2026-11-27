from pathlib import Path
import unittest


class PlatformZipInstallerCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.script = (
            Path(__file__).resolve().parents[1]
            / "installer"
            / "install-platform-zip.ps1"
        ).read_text(encoding="utf-8-sig")

    def test_extraction_uses_framework_compatible_zipfile_overload(self):
        self.assertIn(
            "[System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $staging)",
            self.script,
        )
        self.assertNotIn("Expand-Archive", self.script)

    def test_sha256_uses_framework_crypto_api_without_optional_cmdlets(self):
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", self.script)
        self.assertIn("$sha.ComputeHash($stream)", self.script)
        self.assertNotIn("Get-FileHash", self.script)
        self.assertNotIn("certutil.exe", self.script)

    def test_zip_entry_validation_precedes_extraction(self):
        validation = self.script.index("foreach ($entry in $archive.Entries)")
        extraction = self.script.index(
            "[System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $staging)"
        )
        self.assertLess(validation, extraction)

    def test_manifest_validation_precedes_copy_to_install_root(self):
        manifest_validation = self.script.index("STEP validate-manifest")
        copy_to_target = self.script.index("STEP robocopy-to-target")
        self.assertLess(manifest_validation, copy_to_target)


    def test_zip_entry_validation_normalizes_backslashes(self):
        self.assertIn("$entry.FullName.Replace('\\', '/')", self.script)

    def test_zip_entry_validation_rejects_ads_and_checks_canonical_boundary(self):
        self.assertIn("$segment.Contains(':')", self.script)
        self.assertIn("[System.IO.Path]::GetFullPath(", self.script)
        self.assertIn("[System.StringComparison]::OrdinalIgnoreCase", self.script)
        self.assertIn("ZIP entry escapes staging directory", self.script)

    def test_zip_validation_failure_is_written_to_diagnostic_log(self):
        self.assertIn("FAIL zip-entry-validation message=", self.script)
        validation = self.script.index('Write-Diagnostic "STEP validate-zip-entries"')
        failure_log = self.script.index("FAIL zip-entry-validation message=")
        archive_dispose = self.script.index("$archive.Dispose()", failure_log)
        staging_creation = self.script.index('Write-Diagnostic "STEP create-staging"')
        self.assertLess(validation, failure_log)
        self.assertLess(failure_log, archive_dispose)
        self.assertLess(archive_dispose, staging_creation)

    def test_staging_creation_occurs_after_zip_validation(self):
        validation = self.script.index('Write-Diagnostic "STEP validate-zip-entries"')
        staging = self.script.index('Write-Diagnostic "STEP create-staging"')
        creation = self.script.index(
            "New-Item -ItemType Directory -Force -Path $staging"
        )
        extraction = self.script.index(
            "[System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $staging)"
        )
        self.assertLess(validation, staging)
        self.assertLess(staging, creation)
        self.assertLess(creation, extraction)

if __name__ == "__main__":
    unittest.main()
