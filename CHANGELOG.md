# Changelog

## [1.3.8] - 2026-08-25

- Add GitHub Action to close stale issues- Fix multi-device token refresh race condition (issue #9)



## [1.3.7] - 2026-08-17

- Update README.md- Persist refreshed token to all account entries on startup, update translations and README



## [1.3.6] - 2026-07-23

- No functional change. Re-cut as a clean release for HACS default-repository submission — v1.3.5 was published before its HACS/hassfest validation runs on the same commit had finished (they passed, but out of order), so this release is cut only after confirming both are green.

## [1.3.5] - 2026-07-23

- Fix `brand/icon@2x.png`, which contained WebP data mislabeled with a `.png` extension (and was the wrong size, 280×280 instead of a valid 2x of the 256×256 `icon.png`). Regenerated as a proper 512×512 PNG. Also removes an unreferenced duplicate `icon.png` that lived outside the `brand/` directory HA/HACS actually reads brand assets from. No functional change.

## [1.3.4] - 2026-07-18

- **Breaking:** Remove the "Restore state when turned on" option. The Landbook cloud resets speed/mode/sound to defaults on every power cycle regardless of what triggered it, and the reset isn't consistently timed relative to a re-sent command, so the restore workaround could never be made reliable. Existing config entries with the option enabled keep the now-unused value on file but it has no effect.
- Extract the REST/MQTT API client into a standalone [`landbook-api`](https://github.com/zackwag/landbook-api) PyPI package. No functional change — `api.py` and `mqtt_client.py` had no Home Assistant dependencies and move out as-is; the integration now depends on `landbook-api` via `manifest.json` instead of bundling the client code and its `paho-mqtt`/`pycryptodome` requirements directly.

## [1.3.3] - 2026-07-13

- Fix session refresh — the API requires the account's refresh token (not the access token) to renew a session, and rotates it on every use; the integration only ever sent the access token, so renewal always failed and forced a full reauth every ~2 hours. Now stores and uses the refresh token correctly, and refreshes proactively on a timer ahead of the access token's 2-hour expiry instead of only reacting after it fails.

## [1.3.2] - 2026-07-02

- Fix restore state not applying to device — send after delay



## [1.3.1] - 2026-07-02

- Fix restore_state label showing raw key in options UI



## [1.3.0] - 2026-07-02

- Add restore state on power-on, replace mute option, gate controls when fan is off



## [1.2.16] - 2026-07-02

- Gate fan controls unavailable when fan is off



## [1.2.15] - 2026-06-26

- Fix diagnostics platform error on startup



## [1.2.14] - 2026-06-25

- Stop MQTT reconnect loop when reauth is triggered



## [1.2.13] - 2026-06-23

- Fix spurious reauth on network errors during token refresh



## [1.2.12] - 2026-06-23

- Convert countdown from dropdown to select with hour labels



## [1.2.11] - 2026-06-18

- Fix spurious reauth prompt on startup by only triggering reauth on credential rejection



## [1.2.10] - 2026-06-17

- Fix token validation error on setup retry by refreshing expired token automatically



## [1.2.9] - 2026-06-17

- Fix invalid JSON in de.json translation (mismatched quote character)



## [1.2.8] - 2026-06-16

- Add translations for 12 languages



## [1.2.7] - 2026-06-16

- Fix hassfest — sort manifest keys and add CONFIG_SCHEMA



## [1.2.6] - 2026-06-16

- Add opt-in Wi-Fi signal strength sensor with 5-minute polling



## [1.2.5] - 2026-06-16

- Remove unused imports, fix hassfest CI pin, update info.md



## [1.2.4] - 2026-06-16

- Fix token refresh using latest token, add options reload listener, pin CI actions, add quality_scale and hacs filename



## [1.2.3] - 2026-06-16

- Fix hassfest — move reauth_confirm step under config.step per HA schema



## [1.2.2] - 2026-06-16

- Add diagnostics platform — download device state and TSL info from the device page



## [1.2.1] - 2026-06-16

- Add temperature unit option — display in °F or °C via Configure



## [1.2.0] - 2026-06-16

- Share a single MQTT connection across all devices on the same account



## [1.1.15] - 2026-06-16

- Update README — add countdown entity, Auto mode speed note, re-auth note, and mute option description



## [1.1.14] - 2026-06-16

- Use TSL property name for light entity instead of hardcoded 'Device Display'



## [1.1.13] - 2026-06-16

- Add re-auth flow — prompts for password when session expires instead of silently failing



## [1.1.12] - 2026-06-16

- Fix initial state type coercion — REST API strings now match native MQTT types



## [1.1.11] - 2026-06-16

- Persist refreshed bearer token to config entry so restarts use the latest token



## [1.1.10] - 2026-06-16

- Fix countdown timer showing raw option names — now shows human-readable minutes



## [1.1.9] - 2026-06-16

- Updating release generation- Add description text to mute-on-command option in the UI



## [1.1.8] - 2026-06-16

- Show firmware version in device info



## [1.1.7] - 2026-06-16




## [1.1.6] - 2026-06-16

- Add changelog generation to release script, fix .gitignore

