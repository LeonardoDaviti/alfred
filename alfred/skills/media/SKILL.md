---
name: media
description: Generic OS media transport — play/pause/next/previous and player volume (playerctl). Mock backend for binding-only. Pure execution.
---

# Media Skill

System-wide media transport over whatever player is active (the `playerctl` surface),
**not** Spotify-specific. Canonical **reflexer** case — one command, one action.

> **Mock / binding-only.** `media` echoes JSON without touching a player. A real backend
> maps to `playerctl play/pause/next/previous` and `playerctl volume <0-1>`.

## Commands (via bash)
CLI: `python3 agents/skills/media/media.py <command>` (aliased `media`).

`media play`        — resume current playback
`media pause`
`media next`
`media previous`
`media volume --level <0-100>`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{"mock":true}}`. Exit 0/2.

## Cross-skill collision (why this skill is in the benchmark)
`media play/pause/next/previous/volume` deliberately **overlap Spotify**. The discriminator
is specificity: `media play` resumes the *current* player with **no track**, while
`spotify play --track "<q>"` names a track; `media volume` is the *player* level while
`sys volume set` is the *system master*. This is a hard **cross-skill** routing test.
