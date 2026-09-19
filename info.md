# Landbook

Control fans and other **Landbook / Landecia** devices directly over your local network whenever reachable, falling back automatically to the cloud (real-time MQTT, no polling) when they're not.

## What you get

- **Fan** — on/off, speed percentage, preset modes (Normal / Natural / Sleep / Auto), oscillation
- **Temperature sensor** — ambient temperature in °F or °C
- **Device Display** — LED display on/off
- **Device Sound** — beep sounds on/off
- **Mode** — operating mode select
- **Countdown** — sleep timer select
- **Local-first control** — direct LAN connection when possible, cloud MQTT fallback otherwise; one shared cloud connection per account

## Requirements

- A Landbook account with at least one device already paired **through the official Landbook app** — this integration connects to devices already on your account, it doesn't provision new ones onto your Wi-Fi, and a Landbook account is required even though control itself happens locally
- Home Assistant 2024.1.0 or newer

## Setup

1. Install via HACS
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Landbook**
4. Select your region, enter your email and password — devices are discovered automatically
