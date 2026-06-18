---
name: service
description: Manage systemd service units — start/stop/restart, check status, enable/disable on boot. Pure execution, no communication. Mock backend (binding-only) for the thesis benchmark.
---

# Service Skill

Use this skill for systemd service control: bringing units up and down, restarting
them, reading their status, and toggling boot-persistence. It is a canonical
**reflexer** case — every request maps to a single side-effecting shell command with
**no dialogue and no information return** beyond a status line. Deterministic
intent → one command → execute.

> **Mock / binding-only.** In this thesis benchmark the `svc` CLI is a mock that echoes a
> JSON status line WITHOUT touching real systemd — we evaluate **command correctness**
> (does the reflexer emit the right subcommand/unit?), not real service effects. To target
> a live system, replace the mock with `systemctl`.

## Commands (via bash)

CLI: `python3 agents/skills/service/svc.py <command> [args]` (aliased `svc`).

### Start / stop / restart a unit (the subcommand is the discriminator)
`svc start   --unit "<unit>"`
`svc stop    --unit "<unit>"`
`svc restart --unit "<unit>"`

### Check a unit's status (read)
`svc status --unit "<unit>"`

### Enable / disable a unit on boot
`svc enable  --unit "<unit>"`
`svc disable --unit "<unit>"`

## Flags
- `--unit "<unit>"` systemd unit name (e.g. `nginx.service`, `docker`, `postgresql`)

## Output format
One JSON line: `{"ok": bool, "data": {...}, "error": null|{...}, "meta": {"mock": true}}`.
Exit 0 on success, 2 on bad args.

## Sibling families (why this skill is in the benchmark)
`start` / `stop` / `restart` / `status` / `enable` / `disable` all share the same
domain and `--unit` slot, differing only in the **subcommand word** — a dense
six-member action-sibling family. This is a deliberate stress test of the router's
action-discrimination (the dominant failure mode: sibling collision). `status` is the
sole read; `enable`/`disable` are the boot-persistence pair.
