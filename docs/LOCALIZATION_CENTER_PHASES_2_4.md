# Research OS Localization Center — Phases 2–4

This roadmap extends PR #51 without replacing the existing resource metadata translator.

## Phase 2 — Runtime catalog integration

Status: **Implementation started; CI verification pending.**

- [x] Add versioned English and Thai JSON catalogs to Flutter assets.
- [x] Load catalogs through LocalizationCatalogStore instead of hard-coded editor-only sample strings.
- [x] Keep the web editor catalog and Flutter runtime assets identical; a Python regression test checks parity.
- [ ] Move the shared app shell and high-traffic product surfaces to the same runtime translation lookup.
- [ ] Verify catalog loading on Windows, Web, and iOS build/test runners.

Acceptance: catalog parity and placeholder checks pass; supported locales load without missing-key exceptions; no existing destination is removed or renumbered.

## Phase 3 — Local draft lifecycle

Status: **Implementation started; CI verification pending.**

- [x] Persist selected locale and per-locale translation drafts in local SharedPreferences.
- [x] Restore drafts after the page is recreated.
- [x] Import JSON and block export while catalog-quality findings remain.
- [x] Keep writes local-only; no GitHub API, production endpoint, credential, or automatic repository mutation.
- [ ] Add explicit Reset-to-versioned-catalog and draft revision/restore controls.
- [ ] Add failure-path tests for malformed imports, storage errors, unknown keys, and placeholder mismatches.

Acceptance: draft persistence and locale switching tests pass; invalid catalogs cannot be exported; the user can recover the bundled catalog without deleting files or resetting other app settings.

## Phase 4 — Product-wide localization and release gates

Status: **Started as test/quality work; product-wide language switching is not complete.**

- [x] Add widget tests for the editor, search, and local draft persistence.
- [x] Expand Localization Center CI to validate both web-editor and Flutter runtime catalogs.
- [x] Keep the canonical navigation destination additive at index 18.
- [ ] Add a persisted app-level language selector that updates the shared Research OS shell and product pages.
- [ ] Expand Thai/English coverage to authentication, navigation, settings, errors, empty states, and accessibility labels.
- [ ] Run Flutter analyze, widget tests, Windows build, Web build, and iOS/macOS compile checks on the final exact SHA.
- [ ] Complete manual responsive checks and accessibility review before changing the PR from Draft.

Acceptance: all required CI checks pass on the exact PR head SHA; locale changes affect the shared app UI consistently; fallback behavior is documented; no merge or deployment occurs until separately approved.

## Platform-level upgrade plan

This is the next implementation scope; it is not a claim that the platform-wide migration is already complete.

### Platform architecture

- [ ] Introduce one app-level localization state/controller as the single source of truth for the selected locale.
- [ ] Load locale catalogs through a typed, validated runtime interface with deterministic fallback to the source locale.
- [ ] Connect the locale controller to the shared Research OS shell and navigation without changing existing destination indexes or route/capability bindings.
- [ ] Keep translation authoring/drafts separate from the active runtime catalog. Draft edits must not silently change the app's production strings.
- [ ] Preserve the existing Resource Translator and use explicit catalog export/import as the handoff boundary; no automatic GitHub writes or deployment.
- [ ] Define a stable key naming convention and catalog schema, including interpolation placeholders, plural/select behavior where needed, and accessibility strings.
- [ ] Add a coverage report that compares required source keys against each supported locale and fails on missing keys, empty values, duplicate JSON keys, invalid value types, or placeholder drift.

### Delivery sequence

1. **Runtime foundation:** typed catalog service, locale state, persistence, fallback, error handling, and unit tests.
2. **Shared shell:** app-level language selector, navigation/sidebar/status surfaces, and locale propagation across retained pages.
3. **Product surfaces:** migrate screens in small, reviewable groups, starting with authentication, home/research, settings, errors/empty states, and common actions; maintain an explicit coverage inventory rather than claiming untranslated screens are complete.
4. **Editor lifecycle:** reset to bundled catalog, inspect current draft, save named local revisions, restore a revision, discard a draft with confirmation, and surface storage/import/export errors accessibly.
5. **Quality gates:** catalog schema/parity/coverage checks, placeholder and fallback tests, widget tests for locale switching, and build/test jobs for supported platforms.
6. **Release evidence:** verify the exact final SHA, inspect every required workflow, conduct responsive and accessibility review, and record device/manual checks separately from CI. Only then consider removing Draft status.

### Safety and compatibility invariants

- No secrets, credentials, translation-provider calls, telemetry, or network persistence are introduced by the localization layer.
- Locale preference and authoring drafts remain device-local unless a separately reviewed storage design is approved.
- Invalid or incomplete drafts cannot replace the active bundled catalog.
- Existing navigation indexes, routes, capability bindings, authentication boundaries, and product surfaces remain intact.
- No automatic commit, pull-request merge, release, or deployment is performed by the editor.
- Do not label platform coverage complete while any required screen or platform is unverified.

## Evidence policy

Use PASS, FAIL, SKIPPED, or UNKNOWN based on the actual check output. A queued workflow is not a pass. A build or widget test does not prove a manual UI review. This PR remains Draft and is not merged or deployed by this roadmap.
