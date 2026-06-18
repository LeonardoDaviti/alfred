---
name: docker
description: Manage Docker containers — start/stop/restart, remove, show logs, list running containers. Pure execution, no communication. Mock backend (binding-only) for the thesis benchmark.
---

# Docker Skill

Use this skill for Docker container control: bringing containers up and down,
restarting, removing them, tailing their logs, and listing what is running. It is a
canonical **reflexer** case — every request maps to a single side-effecting shell
command with **no dialogue and no information return** beyond a status line.
Deterministic intent → one command → execute.

> **Mock / binding-only.** In this thesis benchmark the `dock` CLI is a mock that echoes
> a JSON status line WITHOUT touching a real Docker daemon — we evaluate **command
> correctness** (does the reflexer emit the right subcommand/container?), not real
> container effects. To target a live daemon, replace the mock with `docker`.

## Commands (via bash)

CLI: `python3 agents/skills/docker/dock.py <command> [args]` (aliased `dock`).

### Start / stop / restart a container (the subcommand is the discriminator)
`dock start   --container "<container>"`
`dock stop    --container "<container>"`
`dock restart --container "<container>"`

### Remove a container (destructive)
`dock remove --container "<container>"`

### Show a container's logs (read)
`dock logs --container "<container>"`

### List running containers (no slot)
`dock ps`

## Flags
- `--container "<container>"` container name or id (e.g. `redis`, `my-nginx`)

## Output format
One JSON line: `{"ok": bool, "data": {...}, "error": null|{...}, "meta": {"mock": true}}`.
Exit 0 on success, 2 on bad args.

## Sibling families (why this skill is in the benchmark)
`start` / `stop` / `restart` / `remove` / `logs` share the same domain and
`--container` slot, differing only in the **subcommand word** — a dense action-sibling
family that stresses the router's action-discrimination (sibling collision is the
dominant failure mode). `logs` and `ps` are the two reads; `ps` is the only no-slot
member; `remove` is the destructive distractor that must not be confused with `stop`.
