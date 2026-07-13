# Landbook — Home Assistant HACS Integration

A HACS custom integration for Landbook smart home devices, reverse-engineered from the Landbook iOS app (Netprisma/Landecia cloud). Supports real-time control and state via MQTT over TLS — no polling.

## Entities

For each device the integration creates:

| Entity | Type | Description |
|--------|------|-------------|
| Fan | `fan` | Power, speed (percentage), mode (preset), oscillation |
| Device Display | `light` | LED display on/off |
| Device Sound | `switch` | Beep sounds on/off |
| Temperature | `sensor` | Ambient temperature (°F, read-only) |
| Mode | `select` | Operating mode (Normal / Natural / Sleep / Auto) |
| Countdown | `select` | Sleep timer (Cancel / 1 h / 2 h / … / 12 h) |

Additional entities are created automatically for any other writable properties discovered in the device's TSL model.

## Tested Devices

| Device | Model |
|--------|-------|
| OmniBreeze Tower Fan with Internal Oscillation and Wi-Fi | DC2313R |

Other Landbook devices may work but have not been verified. If yours does, please open an issue or PR to add it to this list.

## Installation

### HACS (recommended)

1. In HA, go to **HACS → Integrations**
2. Click the three-dot menu (top right) → **Custom repositories**
3. Enter `https://github.com/zackwag/landbook-ha` and set category to **Integration**
4. Click **Add**, then find and install **Landbook**
5. Restart Home Assistant

### Manual

Copy `custom_components/landbook/` into your HA `config/custom_components/` directory, then restart.

## Setup

1. Go to **Settings → Devices & Services → Add Integration → Landbook**
2. Select your region (US, EU, or CN)
3. Enter your Landbook account email and password
4. Select the device to add
5. Optionally enable **Restore state when turned on** (see Options below)

## Supported Regions

| Region | API |
|--------|-----|
| United States | `iot-api.quectelus.com` |
| Europe | `iot-api.quecteleu.com` |
| China | `iot-gateway.quectel.com` |

EU and CN support is untested — if you try it, please open an issue to report whether it works.

## Options

After setup, click **Configure** on the integration card to change:

| Option | Default | Description |
|--------|---------|-------------|
| Restore state when turned on | Off | When the fan is turned on, restores the previous speed, mode, oscillation, sound, and display settings. State is saved when the fan turns off (via HA, the app, or the physical button). Disabled by default — enable if you find the device resets to unwanted defaults on each power cycle. |
| Temperature unit | °F | The device always reports temperature in °F. Selecting °C converts the value for display in Home Assistant. |
| Show Wi-Fi signal strength sensor | Off | Adds a signal strength sensor (dBm). **Requires a REST API call every 5 minutes** — this is additional polling on top of the normal push-based connection. Enable only if you need it. |

## Requirements

- `paho-mqtt >= 2.0.0` (installed automatically)
- `pycryptodome >= 3.0.0` (installed automatically)
- Home Assistant 2024.1.0 or newer

## Notes

- **Fan speed in Auto mode** — speed shows as unknown while Auto is active. The device controls speed autonomously in this mode and does not push immediate updates, matching the behavior of the native Landbook app. Speed resumes showing when you switch back to another mode.
- **Temperature** updates arrive when the device reports a state change — there is no fixed polling interval.
- **Fan controls availability** — speed, mode, oscillation, countdown, sound, and display entities are marked unavailable while the fan is off, matching the behavior of the Landbook app. Temperature and signal strength remain available regardless of fan state.
- **Restore state** — when enabled, turning the fan on via any method (HA, app, or physical button) re-applies the settings that were active when it was last turned off. This works around the device resetting to default speed, mode, and sound on every power cycle.
- **State on startup** — the integration requests a full state read from the device on every connect and reconnect, so entities reflect actual device state after a restart even if the device was already on.
- **Device availability** — all entities go unavailable if the device drops off the Landbook cloud (MQTT `onl_` event). They recover automatically when the device reconnects.
- **Session expiry** — the access token (2-hour lifetime) is renewed automatically in the background using the account's refresh token, both proactively on a timer and whenever a reconnect or API call needs it. If the refresh token itself has expired or been revoked, Home Assistant will prompt you to re-enter your password from the integration card. No need to remove and re-add the device.
- The integration auto-detects power, speed, mode, and oscillation properties from the device's TSL model. If detection is wrong for your device, open an issue with a debug log.
- One MQTT connection is maintained per account regardless of how many devices you add. All devices on the same account share a single connection — adding a second device does not open a second connection to the broker.

## Troubleshooting

### Diagnostics

On the device page in Home Assistant, click the three-dot menu → **Download diagnostics**. The report includes detected TSL properties, current device state, MQTT connection status, and firmware version. Credentials are automatically redacted. Attach this when opening an issue.

### Debug logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.landbook: debug
```

## Releasing a New Version

Use the release script:

```bash
./scripts/prep_release.sh "Your commit message here"
```

The script will prompt for patch / minor / major, show the resulting version, ask for confirmation, then commit, tag, and push. The GitHub Actions release workflow picks up the tag and publishes a GitHub Release automatically. HACS notifies users once the release is live.
