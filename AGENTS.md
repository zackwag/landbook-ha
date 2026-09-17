# Agent instructions for landbook-ha

## Honor the API/HA split

This repo (landbook-ha) is the Home Assistant integration layer only:
config flow, options, entities, platforms, and HA-specific orchestration
(config-entry lifecycle, `async_track_time_interval` timers, turning
[landbook-api](https://github.com/zackwag/landbook-api) callbacks into HA
state).

**Do not implement or work around Landbook cloud/MQTT client behavior in
this repo.** That includes connection/reconnection semantics, write
retry or deferral logic, and anything else about the wire protocol.
That code belongs in `landbook-api`, released as a package version, and
consumed here via the `requirements` pin in
`custom_components/landbook/manifest.json`.

In particular: **never subclass `LandbookMQTTClient` to add behavior, and
never reach into its private attributes** (`_wire_lock`, `_client`,
`_connected`, `_reconnect_timer`, `_deferred_writes`, etc.) from this repo.
If the integration needs the client to behave differently, that is a
landbook-api change — open a PR there, get it released, then bump the
version requirement here.

### Worked example (why this rule exists)

An earlier pass at fixing MQTT resilience (landbook-ha #22/#23) added a
`_ResilientMQTTClient(LandbookMQTTClient)` subclass in
`custom_components/landbook/__init__.py` that queued writes across a
disconnect, and a `force_reconnect()` method that directly manipulated the
parent class's private locks and connection state. Both concerns were
generic client behavior with no HA dependency, so they were moved into
landbook-api itself (`send_write` deferral + a public `reconnect()`,
released as landbook-api 0.2.0, see landbook-api#9) and landbook-ha#24 was
cut down to just the genuinely HA-specific piece: the `mqtt_watchdog_enabled`
option and its timer, which now calls the client's public `reconnect()`.

If you're asked to fix something that looks like "the integration doesn't
handle a dropped/flaky MQTT connection well," check whether the fix is
about the client's behavior (→ landbook-api) or about HA-side scheduling,
config, or entity state (→ here) before writing code.

## Testing

- `tests/conftest.py` mocks `landbook_api.LandbookMQTTClient` completely —
  this suite does not exercise real MQTT/wire behavior. Add tests here for
  config flow, options, entity setup, token refresh, and watchdog/timer
  orchestration.
- Run `pytest tests/ -v` before considering a change complete.
- If your change depends on new landbook-api behavior that isn't released
  yet, install it locally with `pip install -e /path/to/landbook-api` to
  test against it, and call out in the PR description that it depends on
  an unreleased landbook-api version plus the `requirements` bump needed
  once it ships.

## Releases

`custom_components/landbook/manifest.json` (`version` + `requirements`),
`.bumpversion.cfg`, and `CHANGELOG.md` must be updated together — see
CONTRIBUTING.md. Do not assume a merge alone ships anything; a `vX.Y.Z` tag
push is what triggers the release workflow.
