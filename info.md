# Landbook

Control fans and other devices running on the **Landbook / Landecia** cloud platform (used by Landbook and similar apps).

## What you get

- **Fan entity** — on/off, speed percentage, and preset modes
- **Number entities** — one per INT-typed writable property (e.g. timer)
- **Select entities** — one per ENUM/BOOL writable property (e.g. mode, oscillation)
- **Cloud-push** — real-time state via MQTT; no polling

## Requirements

- A Landbook account with at least one paired device
- Home Assistant 2024.1.0 or newer

## Setup

1. Install via HACS
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Landbook**
4. Enter your email and password — devices are discovered automatically
