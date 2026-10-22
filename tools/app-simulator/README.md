# Research OS App Simulator

A dependency-free, browser-based **mock UI and state-flow simulator** for Research OS.

## Run locally

Open `index.html` directly in a current browser. No package installation, local server, account, API, or network connection is required.

## Included scenarios

- Happy path: mock login → QR pairing preview → simulated scan → mock connection → workspace/navigation.
- QR expired.
- Offline network.
- Pairing denied.
- Windows, Web, and iOS presentation labels.
- Configurable mock API port validation (1024–65535).
- Timestamped event log and JSON evidence export.

## Safety and evidence boundaries

- This tool does **not** authenticate a user, call a backend, access a camera, open a socket, or create a usable pairing token.
- The QR graphic is decorative mock data only.
- Exported evidence deliberately reports `source_sha: null` and `source_sha_status: UNBOUND`. It must not be treated as proof that a specific commit, native build, device, API, or service passed.
- A scenario such as offline/expired/denied is an expected simulated failure path, not a production-system test.
- CI must independently bind any automated result to the exact checked-out Git SHA before it can be treated as repository test evidence.

## Scope

This is a first-pass interactive simulator for reviewing flows and state transitions. It is not an iOS Simulator replacement, Android emulator, browser automation suite, or substitute for Flutter unit/widget/integration tests.

## Live code editor

Open `studio.html` to use the linked Code Studio:

1. Open `studio.html` in your browser.
2. Choose **Load Simulator HTML** and select `index.html` from this folder.
3. Edit HTML, CSS, or JavaScript. The isolated preview refreshes automatically.
4. Download the edited HTML as a new file, then review and test it before replacing any source file.

The editor does not silently overwrite source files. It reads a user-selected local HTML file, previews edits in a sandboxed iframe, and downloads a new HTML file. No server or network API is required. The preview sandbox is a development convenience, not a security boundary for untrusted code; only load code you trust.
