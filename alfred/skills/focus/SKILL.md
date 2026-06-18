---
name: focus
description: Named focus profiles — turn work/sleep/personal focus on, turn it off, check status. Mock backend. Pure execution.
---

# Focus Skill

Named focus/concentration profiles. Canonical **reflexer** case.

> **Mock / binding-only.** Echoes JSON. A real backend would drive the desktop
> do-not-disturb + notification policy per named profile.

## Commands (via bash)
CLI: `python3 agents/skills/focus/focus.py <command>` (aliased `focus`).

`focus on --mode <work|sleep|personal>`
`focus off`
`focus status`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{"mock":true}}`. Exit 0/2.

## Cross-skill collision (why this skill is in the benchmark)
`focus on/off` overlaps **device_settings `dnd`**. The discriminator: `focus on --mode` is a
*named profile*; `settings dnd --state on|off` is the *raw* do-not-disturb toggle. A
cross-skill routing test where both are semantically "do not disturb me."
