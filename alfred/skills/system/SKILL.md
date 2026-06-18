---
name: system
description: Control the local machine — volume up/down/mute/set, screen brightness, lock screen, suspend. Pure execution, no communication. Mock backend (binding-only) for the thesis benchmark.
---

# System Skill

Use this skill for local-machine control: adjusting audio volume, setting screen
brightness, locking the screen, and suspending the machine. It is a canonical
**reflexer** case — every request maps to a single side-effecting shell command with
**no dialogue and no information return** beyond a status line. Deterministic
intent → one command → execute.

> **Mock / binding-only.** In this thesis benchmark the `sys` CLI is a mock that echoes a
> JSON status line WITHOUT touching real hardware — we evaluate **command correctness**
> (does the reflexer emit the right subcommand/level?), not real device effects. To target
> a live machine, wire the subcommands to `pactl`/`wpctl`, `brightnessctl`, `loginctl`, etc.

## Commands (via bash)

CLI: `python3 agents/skills/system/sys.py <command> [args]` (aliased `sys`).

### Volume up / down / mute (the direction subcommand is the discriminator)
`sys volume up`
`sys volume down`
`sys volume mute`

### Set volume to an explicit level (hard sibling: same `volume`, the `--level` slot discriminates)
`sys volume set --level <0-100>`

### Set screen brightness
`sys brightness set --level <0-100>`

### Lock the screen / suspend the machine
`sys lock`
`sys suspend`

## Flags
- `--level <0-100>` target level (`volume set`, `brightness set`)

## Output format
One JSON line: `{"ok": bool, "data": {...}, "error": null|{...}, "meta": {"mock": true}}`.
Exit 0 on success, 2 on bad args.

## Sibling families (why this skill is in the benchmark)
`volume up` / `volume down` / `volume mute` share the `volume` subcommand and differ
only in the **direction word** — a dense action-sibling family. `volume set` is a
*hard* sibling of those (same `volume` subcommand, distinguished only by the `--level`
slot, mirroring the HA brightness case). `lock` / `suspend` form a second power/session
sibling pair. These dense siblings stress the router's action-discrimination — the
dominant failure mode (sibling collision).
