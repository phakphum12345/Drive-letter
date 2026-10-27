# Research OS Localization Center (MVP)

A standalone, dependency-free translation editor prototype. It is intentionally separate from the existing resource metadata translator.

## Features

- English source catalog and Thai target catalog examples.
- Edit translations in a browser, search by key or text, and view completion counts.
- Import a target JSON catalog and export only when browser-side key/value/placeholder checks pass.
- No credentials, server API, external translation provider, or GitHub write integration.

## Run locally

Serve this folder with any local static HTTP server, then open the served URL. For example, from the repository root:

```sh
python -m http.server 8000
```

Open `http://127.0.0.1:8000/tools/localization_center/`. The port is an example; choose an available local port if it is occupied.

## CLI quality gate

```sh
python tools/validate_localization_catalogs.py --source tools/localization_center/locales/en.json --target tools/localization_center/locales/th.json
python -m unittest discover -s tools -p 'test_validate_localization_catalogs.py' -v
```

## Current limits

- This is an MVP prototype, not a production translation management service.
- Edits stay in the current browser session until exported; there is no server-side persistence.
- The example catalogs are not yet wired into the Research OS runtime UI.
- No GitHub API integration, accounts, multi-user review, AI translation, or automatic deployment.
- Export validation checks JSON keys, string values, non-empty translations, and simple `{placeholder}` tokens. Plural rules, ICU messages, HTML safety, and locale-specific formatting need dedicated design before production use.
- Serve over localhost rather than opening `index.html` directly because the app loads catalog files using fetch.
