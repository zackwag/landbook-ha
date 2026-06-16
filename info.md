# Landbook

Control fans and other devices running on the **Landbook / Landecia** cloud platform via real-time MQTT — no polling.

## What you get

- **Fan** — on/off, speed percentage, preset modes (Normal / Natural / Sleep / Auto), oscillation
- **Temperature sensor** — ambient temperature in °F or °C
- **Device Display** — LED display on/off
- **Device Sound** — beep sounds on/off
- **Mode** — operating mode select
- **Countdown** — sleep timer select
- **Cloud-push** — real-time state via MQTT; one shared connection per account

## Requirements

- A Landbook account with at least one paired device
- Home Assistant 2024.1.0 or newer

## Setup

1. Install via HACS
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Landbook**
4. Select your region, enter your email and password — devices are discovered automatically
