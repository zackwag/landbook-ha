# Contributing to landbook-ha

## What lives here vs. in landbook-api

This repo is the **Home Assistant integration** — config flow, options, entities,
platforms, and the HA-specific orchestration around those (timers via
`async_track_time_interval`, config-entry lifecycle, translating
[landbook-api](https://github.com/zackwag/landbook-api) callbacks into HA
state).

It is **not** where the Landbook cloud protocol lives. Anything about talking
to the cloud — REST auth, MQTT wire format, connection/reconnection behavior,
write retry semantics — belongs in landbook-api, not here. See that repo's
`CONTRIBUTING.md` and `AGENTS.md` for the other half of this split.

A concrete rule of thumb: if a fix would make sense regardless of whether the
caller is Home Assistant, it's a landbook-api change plus a `requirements`
version bump here — not code in `custom_components/landbook/`.

## Local development

```bash
pip install pytest pytest-asyncio homeassistant landbook-api
pytest
```

To test against unreleased landbook-api changes, install it in editable mode
from a local checkout instead:

```bash
pip install -e /path/to/landbook-api
```

## Tests

`tests/conftest.py`'s `mock_landbook_api` fixture mocks
`landbook_api.LandbookMQTTClient` entirely — this repo's test suite exercises
integration logic (config flow, options, entity setup, token refresh,
watchdog scheduling), not the MQTT wire protocol. If your change adds
HA-side orchestration, add coverage here. If it's about client/connection
behavior, that coverage belongs in landbook-api's test suite instead.

Run the full suite before opening a PR:

```bash
pytest tests/ -v
```

CI (`.github/workflows/test.yml`, `tests.yml`) runs this on every PR against
Python 3.12 and 3.13, plus HACS/hassfest validation.

## Versioning and releases

Three files must move together:

- `custom_components/landbook/manifest.json` — `version`, and `requirements`
  (the `landbook-api>=X.Y.Z` pin — bump this whenever a fix or feature you're
  depending on landed in landbook-api instead of here)
- `.bumpversion.cfg` — `current_version`
- `CHANGELOG.md` — a new `## [X.Y.Z] - YYYY-MM-DD` entry; the release
  workflow extracts this section verbatim as the GitHub Release body

A merged PR does not ship to HACS users by itself — a `vX.Y.Z` git tag on
`main` triggers `.github/workflows/release.yml`, which runs tests and
creates the GitHub Release. Push the tag (or use the workflow's
`workflow_dispatch` input) once the version-bump PR is merged.
