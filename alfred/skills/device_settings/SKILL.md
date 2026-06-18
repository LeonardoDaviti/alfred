---
name: device_settings
description: Connectivity + UI toggles — wifi, bluetooth, airplane mode, do-not-disturb, dark mode, each on/off. Mock backend. Pure execution.
---

# Device Settings Skill

Toggle device connectivity and UI state. Canonical **reflexer** case — one toggle, one
command. Every toggle shares `--state on|off`; the subcommand is the only discriminator.

> **Mock / binding-only.** Echoes JSON. Real backend: `nmcli` (wifi), `bluetoothctl`/
> `rfkill` (bluetooth/airplane), desktop DND + theme APIs.

## Commands (via bash)
CLI: `python3 agents/skills/device_settings/settings.py <command>` (aliased `settings`).

`settings wifi --state <on|off>`
`settings bluetooth --state <on|off>`
`settings airplane --state <on|off>`
`settings dnd --state <on|off>`
`settings dark-mode --state <on|off>`
`settings light-mode --state <on|off>`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{"mock":true}}`. Exit 0/2.

## Sibling family (why this skill is in the benchmark)
Five toggles that share an identical `--state` slot and differ **only** in subcommand
(`wifi`/`bluetooth`/`airplane`/`dnd`/`dark-mode`) — a dense within-skill sibling family.
`dnd` additionally collides cross-skill with `focus`. Note `dark-mode` is dashed, a
vocabulary-compliance check. **Light mode** is the complementary setting.
