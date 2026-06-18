---
name: android_settings
description: Change Android device settings via the `settings` script (adb-style put/get/list across system/secure/global namespaces). Inspect with list/get, then put the value.
---

# Android Settings Skill (SET-2)

Change device settings the way Android does, via the `settings` script:

- `python3 SET-2/settings.py get <namespace> <key>`
- `python3 SET-2/settings.py put <namespace> <key> <value>`
- `python3 SET-2/settings.py list <namespace>`

## Namespaces
Settings live in **one of three** namespaces: `system`, `secure`, `global`. A key only
takes effect in its correct namespace — writing it to the wrong one silently does nothing.
You may need to `list` each namespace to find where a setting lives.

## Values are raw device integers
Values are stored as Android stores them — raw integers, not friendly words or percents:
- booleans are `0` / `1`;
- some settings are **scaled** (a percentage or duration maps to a device-specific
  integer range);
- some settings are **enumerated codes** (an integer selects a mode).
The `put` command does **not** validate keys or values — it accepts whatever you give it,
so a wrong key/namespace/encoding will appear to succeed but won't change the device.
Inspect current values with `get`/`list` to infer the encoding before you `put`.

## How to work
1. Find the setting: `list` the namespace you think holds it; confirm the exact key.
2. Work out the right encoding for the value (boolean? scaled? enum code?).
3. `put` the value into the correct namespace. Change only what was asked.
