---
name: settings
description: Read and change the phone's settings (Pixel-style) — connectivity, display, device, and per-app settings — through the `settings` script. Pure execution: explore, then set the value the user asked for.
---

# Settings Skill (SET-1)

Control the device settings store via the `settings` script. Three commands:

- `python3 SET-1/settings.py get <path>` — read a setting's current value.
- `python3 SET-1/settings.py set <path> <value>` — change a setting.
- `python3 SET-1/settings.py search <query>` — find setting paths by keyword.

Paths are dotted, e.g. `connectivity.wifi`, `display.brightness`, `device.name`,
`apps.spotify.notifications`.

## How values work
- **toggles** (wifi, bluetooth, airplane_mode, hotspot, nfc, dark_mode, app
  notifications, location): `on`/`off`.
- **ranged** (brightness, text_size, animation_speed, screen_timeout, data_usage):
  integer **0–10** (out-of-range is rejected).
- **free text** (device.name, device.ringtone, device.wallpaper): any string.

## How to work
1. If unsure of the exact path, `search` for it first.
2. For a **relative** change ("increase brightness by 2"), `get` the current value,
   compute the target, then `set` it.
3. Make **only** the change requested — do not touch other settings.

The script validates type, range, and path existence for you, so you cannot write an
invalid value. The active settings file is selected automatically.
