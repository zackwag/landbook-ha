# Changelog

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

