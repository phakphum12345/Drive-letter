#!/usr/bin/env python3
"""Validate central feature-track colors against the canonical navigation registry."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ROOT / "apps/research_os_flutter/lib/src/ui/enterprise_navigation.dart"
FEATURE_SYSTEM = ROOT / "apps/research_os_flutter/lib/src/ui/research_os_feature_color_system.dart"
SIDEBAR_V2 = ROOT / "apps/research_os_flutter/lib/src/ui/research_os_sidebar_v2.dart"
TEST = ROOT / "apps/research_os_flutter/test/research_os_feature_color_system_test.dart"

EXPECTED_TRACKS = {
    "architecture",
    "execution_automation",
    "research_knowledge",
    "assurance_evidence",
    "owner_experience",
    "workspace",
}
STATUS_WORDS = {"pass", "fail", "blocked"}


def fail(message: str) -> None:
    raise SystemExit(f"FEATURE_COLOR_SYSTEM=FAIL: {message}")


def main() -> int:
    for path in (NAVIGATION, FEATURE_SYSTEM, SIDEBAR_V2, TEST):
        if not path.is_file():
            fail(f"required source or regression test missing: {path.relative_to(ROOT)}")

    navigation = NAVIGATION.read_text(encoding="utf-8")
    system = FEATURE_SYSTEM.read_text(encoding="utf-8")
    sidebar = SIDEBAR_V2.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")

    nav_ids = re.findall(r"destinationId:\s*'([^']+)'", navigation)
    if not nav_ids:
        fail("canonical navigation destination IDs not found")
    if len(nav_ids) != len(set(nav_ids)):
        fail("canonical navigation contains duplicate destination IDs")

    marker = "static const Map<String, ResearchOSFeatureStyle> byDestination = {"
    if marker not in system:
        fail("central destination-to-feature mapping is missing")
    mapping_body = system.split(marker, 1)[1].split("};", 1)[0]
    mapping_ids = re.findall(r"'([^']+)':\s*[A-Za-z_][A-Za-z0-9_]*", mapping_body)
    if len(mapping_ids) != len(set(mapping_ids)):
        fail("central feature map contains duplicate destination IDs")

    missing = sorted(set(nav_ids) - set(mapping_ids))
    stale = sorted(set(mapping_ids) - set(nav_ids))
    if missing:
        fail("navigation destinations missing feature mapping: " + ", ".join(missing))
    if stale:
        fail("feature mapping references unknown destinations: " + ", ".join(stale))

    declared_tracks = set(re.findall(r"id:\s*'([^']+)'", system))
    if not EXPECTED_TRACKS.issubset(declared_tracks):
        fail("one or more required feature tracks are missing")
    if declared_tracks & STATUS_WORDS:
        fail("feature track IDs must not encode PASS/FAIL/BLOCKED status")

    if "?? unclassified" not in system or "Unknown destinations stay neutral" not in system:
        fail("unknown destinations must fail closed to neutral presentation")
    if "ResearchOSFeatureColorSystem" not in sidebar or ".forDestination(item.destinationId)" not in sidebar:
        fail("canonical sidebar is not wired to the central feature color system")
    if "ResearchOSFeatureColorSystem" not in navigation or ".forDestination(item.destinationId)" not in navigation:
        fail("shared mobile/legacy navigation is not wired to the central feature color system")
    if "unknown destinations remain neutral" not in test:
        fail("unknown-destination regression test is missing")
    if "authorization" not in system.lower() or "presentation-only" not in system.lower():
        fail("the non-authorizing presentation boundary must be documented")

    print("FEATURE_COLOR_SYSTEM=PASS")
    print(f"NAVIGATION_DESTINATIONS={len(nav_ids)}")
    print(f"FEATURE_TRACKS={len(EXPECTED_TRACKS)}")
    print("UNKNOWN_DESTINATIONS=NEUTRAL")
    print("AUTHORIZATION_AUTHORITY=UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
