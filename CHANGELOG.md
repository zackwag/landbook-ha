# Changelog

## [2.2.2](https://github.com/zackwag/landbook-ha/compare/v2.2.1...v2.2.2) (2026-09-22)


### Bug Fixes

* require landbook-api&gt;=0.7.2 for data-plane stall detection ([#63](https://github.com/zackwag/landbook-ha/issues/63)) ([b4ab241](https://github.com/zackwag/landbook-ha/commit/b4ab24131fef52befa6a4f675d6b39017bcbce25))

## [2.2.1](https://github.com/zackwag/landbook-ha/compare/v2.2.0...v2.2.1) (2026-09-22)


### Bug Fixes

* detect and demote wedged local sessions that stay connected but stop echoing ([#59](https://github.com/zackwag/landbook-ha/issues/59)) ([f09ed2d](https://github.com/zackwag/landbook-ha/commit/f09ed2d3033effef6637d718aa0e2527ad7d3d1d))
* remove application-layer wedge detection, rely on transport-layer pong timeout in landbook-api ([#61](https://github.com/zackwag/landbook-ha/issues/61)) ([39c33f6](https://github.com/zackwag/landbook-ha/commit/39c33f6))
* require landbook-api>=0.7.1 for heartbeat pong timeout and command split ([#62](https://github.com/zackwag/landbook-ha/issues/62)) ([5863b09](https://github.com/zackwag/landbook-ha/commit/5863b09))

## [2.2.0](https://github.com/zackwag/landbook-ha/compare/v2.1.1...v2.2.0) (2026-09-22)


### Features

* automatic local-LAN reconnection after unexpected disconnect ([#57](https://github.com/zackwag/landbook-ha/issues/57)) ([695992d](https://github.com/zackwag/landbook-ha/commit/695992d25776fb2517c83ae7b487b548b1025092))

## [2.1.1](https://github.com/zackwag/landbook-ha/compare/v2.1.0...v2.1.1) (2026-09-21)


### Bug Fixes

* reauth completion now heals live MQTT session, prevents reauth storm ([#55](https://github.com/zackwag/landbook-ha/issues/55)) ([c764a22](https://github.com/zackwag/landbook-ha/commit/c764a22af3e1b27b961b0504ce3dabd0abc25dd9))

## [2.1.0](https://github.com/zackwag/landbook-ha/compare/v2.0.2...v2.1.0) (2026-09-19)


### Features

* cache TSL model and skip REST state seed when local covers everything ([#51](https://github.com/zackwag/landbook-ha/issues/51)) ([7142ddc](https://github.com/zackwag/landbook-ha/commit/7142ddcdeb1fb400e2dba0cd149764c35ac56238))


### Bug Fixes

* clear local_client on an unexpected local disconnect ([#53](https://github.com/zackwag/landbook-ha/issues/53)) ([db1f7eb](https://github.com/zackwag/landbook-ha/commit/db1f7eb2baa741cd77580b867826dd7f6a5ae634))

## [2.0.2](https://github.com/zackwag/landbook-ha/compare/v2.0.1...v2.0.2) (2026-09-19)


### Bug Fixes

* seed state correctly at startup, map p11vkW's local temperature id ([#49](https://github.com/zackwag/landbook-ha/issues/49)) ([3ffff70](https://github.com/zackwag/landbook-ha/commit/3ffff708fc588b96a2f13237daa9b9dcc0647892))

## [2.0.1](https://github.com/zackwag/landbook-ha/compare/v2.0.0...v2.0.1) (2026-09-19)


### Bug Fixes

* keep updating properties local control doesn't cover from cloud ([#47](https://github.com/zackwag/landbook-ha/issues/47)) ([66153f0](https://github.com/zackwag/landbook-ha/commit/66153f081f424415b52d744f170ee320f91320a0))

## [2.0.0](https://github.com/zackwag/landbook-ha/compare/v1.5.0...v2.0.0) (2026-09-19)


### ⚠ BREAKING CHANGES

* always attempt local-LAN control and make it authoritative for reads ([#42](https://github.com/zackwag/landbook-ha/issues/42))

### Features

* add opt-in local control option, grouped account-wide ([#37](https://github.com/zackwag/landbook-ha/issues/37)) ([246842d](https://github.com/zackwag/landbook-ha/commit/246842df4790ee812cd6e745c29699777586907e))
* always attempt local-LAN control and make it authoritative for reads ([#42](https://github.com/zackwag/landbook-ha/issues/42)) ([de9ae22](https://github.com/zackwag/landbook-ha/commit/de9ae222f9181f6263b5e920165b168ef2a470c6))
* backfill authKey from the device list for existing entries ([#46](https://github.com/zackwag/landbook-ha/issues/46)) ([a7f8255](https://github.com/zackwag/landbook-ha/commit/a7f8255697d2b435c7c66222e880d99fdc8300c4))
* feed local device pushes into state too, not just writes ([#40](https://github.com/zackwag/landbook-ha/issues/40)) ([ac0385b](https://github.com/zackwag/landbook-ha/commit/ac0385b059130aa26e56eb7a1d06b5c9ad0d945e))
* offer local control during setup, not just in Options ([#41](https://github.com/zackwag/landbook-ha/issues/41)) ([a53264c](https://github.com/zackwag/landbook-ha/commit/a53264c7197b5ed2e701264e4b4501808e185f1e))
* wire local-LAN control into the write path ([#39](https://github.com/zackwag/landbook-ha/issues/39)) ([1d2579e](https://github.com/zackwag/landbook-ha/commit/1d2579e349148a1f82bddac4196548bb5b775530))


### Bug Fixes

* skip cloud re-seed reads for devices with a live local connection ([#44](https://github.com/zackwag/landbook-ha/issues/44)) ([0450945](https://github.com/zackwag/landbook-ha/commit/0450945795b59cec9fea70c8280a53298d341066))
* update stale opt-in wording in local-control log messages ([#43](https://github.com/zackwag/landbook-ha/issues/43)) ([c6fa694](https://github.com/zackwag/landbook-ha/commit/c6fa694530b1fb9d59601c6e1558dafc9bff052e))

## [1.5.0](https://github.com/zackwag/landbook-ha/compare/v1.4.1...v1.5.0) (2026-09-18)


### Features

* **ci:** add ruff lint + format check ([#33](https://github.com/zackwag/landbook-ha/issues/33)) ([a8e0f76](https://github.com/zackwag/landbook-ha/commit/a8e0f76b3d4f847632825184bc879180c1477a5f))


### Bug Fixes

* **deps:** require landbook-api&gt;=0.4.2 for reconnect ghost-session fix ([#35](https://github.com/zackwag/landbook-ha/issues/35)) ([13fc78d](https://github.com/zackwag/landbook-ha/commit/13fc78d7c06526f6db4fe9c9afd18a4792975440))

## [1.4.1](https://github.com/zackwag/landbook-ha/compare/v1.4.0...v1.4.1) (2026-09-17)


### Bug Fixes

* **ci:** use RELEASE_PLEASE_TOKEN so releases trigger downstream workflows ([#31](https://github.com/zackwag/landbook-ha/issues/31)) ([9b35201](https://github.com/zackwag/landbook-ha/commit/9b35201cae6876c2a6dcae96dfa92c9d01e2d19c))

## [1.4.0](https://github.com/zackwag/landbook-ha/compare/v1.3.14...v1.4.0) (2026-09-17)


### Features

* **ci:** adopt release-please ([#29](https://github.com/zackwag/landbook-ha/issues/29)) ([4f3218d](https://github.com/zackwag/landbook-ha/commit/4f3218d008335a6d2b29e33f5c5870bb66b80370))

## [1.3.14] - 2026-09-17

- Add MQTT watchdog: new `mqtt_watchdog_enabled` option (default on) forces a reconnect when no inbound MQTT message has arrived for 5 minutes, closing a silent-connection-drop gap the broker never reports (#24)
- Require landbook-api>=0.2.0: `send_write` now queues a write across a brief disconnect (e.g. during token-rotation) instead of raising and losing it, and `connect()` cleans up a half-started client before raising on a timeout instead of leaking a background thread (#24)

## [1.3.13] - 2026-09-15

- Require landbook-api>=0.1.1, which serializes MQTT wire operations in the client itself and fixes a BufferError ("Existing exports of data: object cannot be re-sized") from concurrent publish() on a shared account's MQTT client (#18)
- Skip reload for a config entry that isn't LOADED, so a failed_unload/setup_error entry can't spam OperationNotAllowed when a sibling entry's token refresh fires the options-update listener (#19)



## [1.3.12] - 2026-09-10

- unload-race-fix: safer account lookup in async_unload_entry using .get() and .pop() (#15)
- Add PR test workflow- Fix unload race condition for shared accounts



## [1.3.11] - 2026-09-09

- fix: persist latest tokens on unload and push fresh token to MQTT client (#13)
- Gate release on test suite passing
- Bump the actions group across 1 directory with 4 updates (#12)
- Fix options flow tests — patch config_entry property with create=True
- Fix options flow tests for newer HA where config_entry is read-only
- Add CI test workflow, Dependabot config, and tests for config flow and unload- Persist latest tokens on unload and add explanatory comments (PR #13)



## [1.3.10] - 2026-09-09

- Prevent spurious reauth on cold boot, guard MQTT client creation (PR #11)
- Fix stale token on proactive refresh — use in-memory token pair (issue #9)
- Add test suite for integration- Prevent spurious reauth on cold boot, fix stale token on proactive refresh (issue #9)



## [1.3.9] - 2026-09-08

- Serialize setup-time token refresh per account (issue #9) (#10)- Add test suite for token refresh race conditions, merge setup-time lock fix (issue #9)



## [Unreleased]

- Fix multi-device reauth race on startup (issue #9). On a cold boot Home Assistant sets up every config entry for an account concurrently; when the access token had expired, each entry independently called the refresh endpoint with the same single-use refresh token, so only the first succeeded and the rest were forced into a reauth prompt. The setup-time token check/refresh is now serialized per account with a lock — the first entry refreshes and persists the new token pair to every entry for the account, and the others re-read the fresh token and skip the refresh. The earlier 1.3.7/1.3.8 fixes only covered the startup persist-sync and the runtime (proactive-timer / MQTT-reconnect) refresh path, not this setup path.

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
