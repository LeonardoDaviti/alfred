---
name: call
description: Telephony actions — dial a contact/number, redial, hang up, answer. Mock backend (no real telephony). Pure execution.
---

# Call Skill

Place and control phone calls. Canonical **reflexer** case.

> **Mock / binding-only.** Echoes JSON; no telephony. A real backend would bridge to a
> phone link (KDE Connect / GSConnect) or a SIP client.

## Commands (via bash)
CLI: `python3 agents/skills/call/call.py <command>` (aliased `call`).

`call dial --to "<contact name or number>"`
`call redial`
`call hangup`
`call answer`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{"mock":true}}`. Exit 0/2.

## Composes with contacts
`composite_call_contact` chains `contacts search --query "<name>"` → `call dial --to
"<name>"` (resolve a name to a number, then dial) — the classic two-tier name→number→action.
`dial` (needs a target) vs `redial`/`hangup`/`answer` (no target) is the within-skill split.
