# SET-2 — Android-realistic settings skill (agent benchmark)

A realistic Android settings skill the **agent (thinker)** operates, scored by an
**end-state oracle**. Same contract as SET-1 (mutable state, sandbox per task), but a
deliberately unforgiving, feature-rich backend — the goal is to test how an agent handles
a real device-settings surface (the way `adb shell settings` actually behaves).

## Why it's hard (mirrors real `adb shell settings`)
- **Three namespaces** (`system` / `secure` / `global`); a key only works in its own one.
- **Non-obvious encodings**: brightness `0–255` (not %), `screen_off_timeout` in
  **milliseconds**, `location_mode`/`zen_mode`/`ringer_mode`/`wifi_sleep_policy` are
  **integer enums**, `font_scale` is a **string float** ("1.0"/"1.15"/"1.30"), booleans `0/1`.
- **Permissive `put`** (like real Android): a wrong namespace/key/value "succeeds" silently
  and just fails to change the device → caught only by the end-state oracle.

## Backend (32 settings across the 3 namespaces)
display/brightness/font/sound/ringer, connectivity (wifi/bt/mobile/nfc/airplane/roaming),
location/privacy/accessibility/adb, zen/DND, battery saver, device name, screensaver, etc.
See `settings_schema.json`.

## Tasks — 48 (`tasks.json`)
- **single, cryptic-encoding** (brightness %, timeout units, enum modes, font scale),
- **boolean / namespace traps** (right key in the right namespace),
- **multi-step compound routines** (bedtime / battery-saver / movie / driving / flight /
  privacy-lockdown / accessibility / gaming / focus / kids / presentation …), 2–4 changes
  across namespaces,
- **relative / arithmetic** (double the timeout, halve the brightness, +one font step).
Each task carries an `initial` sandbox patch + a `gold` end-state.

## Modes (`run.ts`)
- `--mode thinker` — **primary.** Generic `SKILL.md` only (namespaces + "encodings vary");
  the agent must discover the right namespace/key/encoding. ceiling 20 + wall-clock backstop.
- `--mode reflexer` — optional/legacy: injects a distilled incantation (`patterns.json`).
  Tasks no longer carry patterns by default; this mode is kept for the SET-1/SET-2 contrast
  but is not the focus here.

## Run
```bash
python3 SET-2/preflight.py                                   # 48/48
tsx SET-2/run.ts --mode thinker --model qwen-3.5-2b
tsx SET-2/run.ts --mode thinker --model qwen3.6-35b --backstop-ms 240000
tsx SET-2/run.ts --mode thinker --tasks /tmp/subset.json     # subset/smoke
```
Full command traces are printed and stored per task in `benchmark/reports/set2-*.json`.
preflight 48/48.
