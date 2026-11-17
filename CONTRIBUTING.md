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

Releases are cut by [release-please](https://github.com/googleapis/release-please) from Conventional Commit PR titles. Don't hand-edit `version` in `manifest.json` or `CHANGELOG.md`, and don't touch `chore(main): release ...` PRs. Merging the release PR tags `vX.Y.Z` and creates the GitHub Release that HACS installs from.

`manifest.json` pins an exact `landbook-api==X.Y.Z`. Home Assistant only installs a requirement when the installed version doesn't satisfy it, so this pin is the only way a landbook-api release reaches users, and it guarantees everyone runs the pair CI tested (CI installs exactly what the manifest pins). The `Bump landbook-api` workflow (`.github/workflows/bump-landbook-api.yml`) checks PyPI daily and opens a `fix(deps): bump landbook-api to X.Y.Z` PR when there's a newer release, closing any older bump PR it supersedes. Before merging, read the release notes and push anything the integration should adopt to that branch; retitle to `feat(deps):` if it adds user-facing functionality. Run it from the Actions tab to check immediately after a landbook-api release.
