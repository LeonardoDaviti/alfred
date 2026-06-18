---
name: spotify
description: Control Spotify playback — play/pause, next/previous track, search the catalog, add tracks to playlists, and set volume. Mock backend (binding-only) for the thesis benchmark; no device required.
---

# Spotify Skill

Use this skill for music playback control and library actions. Most commands are pure
**reflexer** actions: one request → one playback command. Search is the read action.

> **Mock / binding-only.** The `spotify` CLI here is a mock that echoes a JSON status line
> without touching a real Spotify device or the Web API — we score **command correctness**,
> not real playback (the developer has no device). To go live, back it with the Spotify Web
> API (`/me/player/...`) and an OAuth token.

## Commands (via bash)

CLI: `python3 agents/skills/spotify/spotify.py <command> [args]` (aliased `spotify`).

### Playback control (the verb is the discriminator)
`spotify play [--track "<query>"]`   — start/resume, optionally a specific track
`spotify pause`
`spotify next`
`spotify previous`

### Search the catalog (read)
`spotify search --query "<artist/track/album>"`

### Add a track to a playlist
`spotify add --track "<track>" --playlist "<playlist>"`

### Set volume
`spotify volume --level <0-100>`

## Flags
- `--track "<...>"` track/artist to play or add
- `--query "<...>"` search terms (`search`)
- `--playlist "<...>"` target playlist (`add`)
- `--level <0-100>` volume percentage (`volume`)

## Output format
One JSON line: `{"ok": bool, "data": {...}, "error": null|{...}, "meta": {"mock": true}}`.
Exit 0 on success, 2 on bad args.

## Sibling families (why this skill is in the benchmark)
`play` / `pause` and `next` / `previous` are minimal-pair playback siblings — same topic,
opposite action. They extend the action-discrimination stress test (sibling collision)
beyond Home Assistant into a second domain.
