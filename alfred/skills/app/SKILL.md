---
name: app
description: Application control — open/launch, close/quit, and switch-to a running app by name. Mock backend. Pure execution.
---

# App Skill

Launch, close, and focus desktop applications. Canonical **reflexer** case.

> **Mock / binding-only.** Echoes JSON. Real backend: `gtk-launch`/`xdg-open` (open),
> `wmctrl`/process signal (close), `wmctrl -a` (switch/focus).

## Commands (via bash)
CLI: `python3 agents/skills/app/app.py <command>` (aliased `app`).

`app open --name "<application>"`
`app close --name "<application>"`
`app switch --name "<application>"`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{"mock":true}}`. Exit 0/2.

## Cross-skill collision (why this skill is in the benchmark)
`app open --name "<app>"` collides with `browser open --url "<url>"` ("open X") — the
**app name vs URL** object discriminates. `app switch` also collides with `browser
tab-switch` (window vs tab).
