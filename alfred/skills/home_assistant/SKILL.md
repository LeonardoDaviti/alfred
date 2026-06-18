---
name: home_assistant
description: Control Home Assistant devices — turn entities on/off/toggle, read state, set thermostat temperature and light brightness, and activate scenes. Pure execution, no communication. Mock backend (binding-only) for the thesis benchmark.
---

# Home Assistant Skill

Use this skill for smart-home control: switching devices, reading sensor/device state,
adjusting climate and lights, and running scenes. It is the canonical **reflexer** case —
every request maps to a single, side-effecting shell command with **no dialogue and no
information return** beyond a status line. That is exactly why it suits the reflexion
strategy: deterministic intent → one command → execute.

> **Mock / binding-only.** In this thesis benchmark the `ha` CLI is a mock that echoes a
> JSON status line without touching a real Home Assistant instance — we evaluate **command
> correctness** (does the reflexer emit the right service/flags?), not real device effects.
> To target a live instance, point `ha` at your `HASS_URL` + long-lived token.

## Commands (via bash)

CLI: `python3 agents/skills/home_assistant/ha.py <command> [args]` (aliased `ha`).

### Turn a device on / off / toggle (the action verb is the discriminator)
`ha call --domain <domain> --service turn_on  --entity "<entity>"`
`ha call --domain <domain> --service turn_off --entity "<entity>"`
`ha call --domain <domain> --service toggle   --entity "<entity>"`

### Read the current state of an entity
`ha state --entity "<entity>"`

### Set thermostat target temperature
`ha call --domain climate --service set_temperature --entity "<entity>" --temp <N>`

### Set light brightness (note: same `turn_on` service, the `--brightness` flag discriminates)
`ha call --domain light --service turn_on --entity "<entity>" --brightness <0-255>`

### Activate a scene
`ha scene --name "<scene>"`

## Flags
- `--domain` HA domain (`light`, `switch`, `climate`, `fan`, `cover`, …)
- `--service` HA service (`turn_on`, `turn_off`, `toggle`, `set_temperature`, …)
- `--entity` entity id or friendly name (e.g. `light.kitchen`, `climate.bedroom`)
- `--temp <N>` target temperature (`set_temperature`)
- `--brightness <0-255>` brightness level (`turn_on` on a light)
- `--name "<scene>"` scene name (`scene`)

## Output format
One JSON line: `{"ok": bool, "data": {...}, "error": null|{...}, "meta": {"mock": true}}`.
Exit 0 on success, 2 on bad args.

## Sibling families (why this skill is in the benchmark)
`turn_on` / `turn_off` / `toggle` share a domain and differ only in the **service** word;
`set_brightness` is a *hard* sibling of `turn_on` (same service, distinguished only by the
`--brightness` slot). These dense action-siblings are a deliberate stress test of the
router's action-discrimination — the dominant failure mode (sibling collision).
