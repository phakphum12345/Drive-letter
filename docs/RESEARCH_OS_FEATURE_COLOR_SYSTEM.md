# Research OS Feature Color System

Status: **IMPLEMENTED ON FEATURE BRANCH / VALIDATION REQUIRED**

## Purpose

Use stable feature-track colors to help people recognize the kind of work and
navigate consistently across the canonical Research OS Flutter surface. This is
a presentation aid, not an authority or workflow engine.

## Single-source boundaries

- `researchNavigationItems` in
  `apps/research_os_flutter/lib/src/ui/enterprise_navigation.dart` remains the
  only canonical navigation destination registry.
- `ResearchOSFeatureColorSystem` in
  `apps/research_os_flutter/lib/src/ui/research_os_feature_color_system.dart`
  owns the mapping from existing `destinationId` values to feature-track
  presentation metadata.
- Sidebar and mobile navigation consume the same mapping. The mapping must not
  create routes or destinations of its own.
- Unknown destinations use the neutral `unclassified` style; no feature is
  guessed from a label or section name.
- Feature colors never represent PASS, FAIL, BLOCKED, warnings, permission, or
  execution state.
- Authorization, capability execution, Owner authority, and release decisions
  remain with their existing authoritative subsystems. Color metadata grants no
  access and cannot bypass a boundary.

## Feature tracks

| Feature ID | Label | Color | Scope examples |
|---|---|---|---|
| `architecture` | Platform Architecture | `#2563EB` blue | GitHub, local API and service |
| `execution_automation` | Execution & Automation | `#0D9488` teal | Agent Center, workflows, Friend Connect |
| `research_knowledge` | M.2 Platform & Research | `#7C3AED` purple | Brain Skills, Library, Knowledge Graph, Google Workspace |
| `assurance_evidence` | Assurance & Evidence | `#EA580C` orange | System Monitor, Settings, Developer Access, Control Center |
| `owner_experience` | Owner Experience & UI | `#DB2777` pink | Owner and Google Sign-In |
| `workspace` | Workspace | `#64748B` slate | Home, AI Chat, Projects |

The color assignment is navigation metadata. The mapping can be refined only
with tests updated in the same change. The generic Workspace track stays neutral
so it does not masquerade as the architecture track.

## Verification

Run from the repository root:

```powershell
python tools/validate_research_os_feature_color_system.py
cd apps/research_os_flutter
flutter test test/research_os_feature_color_system_test.dart
flutter test test/platform_surface_parity_test.dart
```

The validator checks that every canonical destination is mapped exactly once,
that the central registry has no stale destination IDs, that the expected tracks
exist, and that navigation consumes the central style mapping.

## Rollout rule

This feature branch is not a release. Merge only after the validator, Flutter
regression tests, required CI checks, and the existing Final Gate pass against
the exact proposed commit SHA. Then verify the merged `main` SHA and rerun
post-merge checks. Do not weaken or skip a required gate to obtain a green result.
