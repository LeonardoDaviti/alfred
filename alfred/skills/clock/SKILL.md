---
name: clock
description: Unified time control — countdown timers, absolute-time alarms (with optional repeat), and current/world time. The one skill that ACTUALLY fires (systemd-run --user) when ALFRED_CLOCK_REAL=1; mock for the binding benchmark. Pure execution.
---

# Clock Skill

One skill for everything time-based: **timers** (relative countdowns), **alarms**
(absolute clock times), and **time** lookups. Replaces ad-hoc "remind me in N minutes".
Canonical **reflexer** case — deterministic intent → one command → execute.

> **Backends.** Default is a MOCK that echoes a JSON status line (binding-only scoring).
> With `ALFRED_CLOCK_REAL=1` it genuinely schedules via `systemd-run --user`
> (`--on-active` for timers, `--on-calendar` for alarms) and lists/cancels via
> `systemctl --user` — so timers and alarms really go off and survive logout.

## Commands (via bash)
CLI: `python3 agents/skills/clock/clock.py <command>` (aliased `clock`).

### Timers (relative duration)
`clock timer start --duration <10m|90s|1h30m>`
`clock timer cancel`
`clock timer list`

### Alarms (absolute time — hard sibling of timers)
`clock alarm set --time <07:00|6:30am|14:15>`
`clock alarm cancel`
`clock alarm list`

### Current / world time
`clock now` · `clock now --city "Tokyo"`

## Flags
- `--duration` relative span (timer start); `--time` absolute time (alarm set)
- `--label` optional notification label; `--city` optional world-clock city

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{...}}`. Exit 0/2.

## Sibling families (why this skill is in the benchmark)
`timer start` vs `alarm set` are **hard siblings** — both "set a …", distinguished only by
relative-duration vs absolute-time. `timer cancel`/`list` mirror `alarm cancel`/`list`, so
"cancel the timer" vs "cancel the alarm" stress the **noun** discriminator. This is the
dominant router failure mode (sibling collision) inside a single skill.
