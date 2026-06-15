# Landbook — Home Assistant HACS Integration

A HACS custom integration for fans (and other devices) running on the Landbook platform (Netprisma/Landecia cloud).

## Features

- **Config flow UI** — add devices through the HA interface, no YAML required
- **Fan entity** — on/off, speed percentage, and preset modes auto-detected from the device's TSL model
- **Number entities** — one per INT-typed writable property (e.g. timer, brightness)
- **Select entities** — one per ENUM/BOOL writable property (e.g. mode, oscillation)
- **Cloud-push** — state updates arrive via MQTT WebSocket; no polling

## Tested Devices

| Device | Model |
|--------|-------|
| OmniBreeze Tower Fan with Internal Oscillation and Wi-Fi | DC2313R |

Other Landbook devices may work but have not been verified. If yours does, please open an issue or PR to add it to this list.

## Installation

### HACS (recommended)

1. Add this repo as a custom repository in HACS (type: **Integration**).
2. Install **Landbook**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration → Landbook**.

### Manual

Copy `custom_components/landbook/` into your HA `config/custom_components/` directory, then restart.

## Configuration

The config flow will ask for:

| Field | Description |
|-------|-------------|
| Email | Your Landbook account email |
| Password | Your account password |
| Device | Pick from your linked devices |

Credentials are stored in the HA config entry. The bearer token is refreshed on each HA restart.

## Requirements

- `paho-mqtt >= 2.0.0` (installed automatically)
- `pycryptodome >= 3.0.0` (installed automatically)

## Limitations

- **US region only** — the integration connects to the Landbook US servers (`iot-api.quectelus.com`, `iot-south.landecia.com`). Accounts on EU or CN servers are not currently supported.

## Notes

- Temperature is reported by the device whether it is on or off, and is refreshed on every HA restart or MQTT reconnect. There is no fixed polling interval — updates arrive when the device reports a state change.
- The integration auto-detects the power switch and speed control from the device's TSL model. If detection is wrong, open an issue with your TSL dump.
- Only one MQTT connection is created per account regardless of how many devices you add.

## Releasing a New Version

Use the release script in `scripts/prep_release.sh`:

```bash
./scripts/prep_release.sh "Your commit message here"
```

The script will:
1. Read the current version from `manifest.json`
2. Ask whether this is a **patch**, **minor**, or **major** bump and show you the resulting version
3. Ask for confirmation before doing anything
4. Update the version in `manifest.json` and `.bumpversion.cfg`
5. Commit all staged changes, tag the commit `vX.Y.Z`, and push to `origin/main`

The GitHub Actions release workflow picks up the tag and publishes a GitHub Release automatically. HACS notifies users of the update once the release is live.
