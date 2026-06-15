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
- `openssl` available on the HA host (present in all standard HA OS / Container installs)

## Notes

- The integration auto-detects the power switch and speed control from the device's TSL model. If detection is wrong, open an issue with your TSL dump.
- Only one MQTT connection is created per account regardless of how many devices you add.

## Releasing a New Version

Requires `bump2version` (`pip install bump2version`).

```bash
# patch = 1.0.0 → 1.0.1 | minor = 1.0.0 → 1.1.0 | major = 1.0.0 → 2.0.0
bump2version patch
git push --tags
```

This commits the version bump, creates a `vX.Y.Z` tag, and pushes it. The release workflow picks up the tag and publishes a GitHub Release automatically. HACS notifies users of the update once the release is live.
