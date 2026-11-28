from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


class OwnerBundleBuilder:
    """Build a portable source bundle containing only owned architecture files."""

    INCLUDED_ROOT_FILES = ("OWNER_MANIFEST.json", "README.md", "pyproject.toml")
    INCLUDED_FLUTTER_ROOT_FILES = ("pubspec.yaml", "analysis_options.yaml")
    APPLICATION_PROTOCOL_SOURCE = "RESEARCH_OS_APPLICATION_DEVELOPMENT_PROTOCOL.md"
    APPLICATION_PROTOCOL_BUNDLE_PATH = "research_os_friend/application_development_protocol.md"

    def __init__(self, owner_special_root: Path) -> None:
        self.root = Path(owner_special_root).resolve()

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _source_files(self) -> list[tuple[str, Path]]:
        files: list[tuple[str, Path]] = []
        candidates = [self.root / name for name in self.INCLUDED_ROOT_FILES]
        candidates.extend(sorted((self.root / "research_os_friend").glob("*.py")))
        candidates.extend(sorted((self.root / "scripts").glob("*.py")))
        candidates.extend(sorted((self.root / "scripts").glob("*.ps1")))

        flutter_root = self.root / "flutter_app"
        candidates.extend(flutter_root / name for name in self.INCLUDED_FLUTTER_ROOT_FILES)
        candidates.extend(sorted((flutter_root / "lib").rglob("*.dart")))
        candidates.extend(sorted((flutter_root / "test").rglob("*.dart")))

        candidates.extend(sorted((self.root / "windows_service").glob("*.cs")))
        candidates.extend(sorted((self.root / "windows_service").glob("*.csproj")))
        candidates.extend(sorted((self.root / "installer").glob("*.iss")))

        for path in candidates:
            if path.is_file():
                files.append((path.relative_to(self.root).as_posix(), path))

        protocol_source = self.root.parent / "docs" / self.APPLICATION_PROTOCOL_SOURCE
        if protocol_source.is_file():
            files.append((self.APPLICATION_PROTOCOL_BUNDLE_PATH, protocol_source))

        unique = {archive_path: path for archive_path, path in files}
        return [(name, unique[name]) for name in sorted(unique)]

    def build(self, destination: Path) -> dict[str, object]:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        inventory: list[dict[str, object]] = []
        payloads: list[tuple[str, bytes]] = []
        for relative, path in self._source_files():
            data = path.read_bytes()
            payloads.append((relative, data))
            inventory.append({"path": relative, "sha256": self._sha256(data), "bytes": len(data)})

        bundle_manifest = {
            "schema_version": 3,
            "edition": "owner-special",
            "bundle": "Friend Complete V1.3",
            "content_policy": "owned source and architecture files only; runtime owner data remains external",
            "files": inventory,
        }
        manifest_bytes = (json.dumps(bundle_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, data in payloads:
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, data)
            info = zipfile.ZipInfo("BUNDLE_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, manifest_bytes)

        return {"path": str(destination), "sha256": self._sha256(destination.read_bytes()), "files": len(inventory) + 1, "source_only": True}
