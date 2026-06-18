---
name: browser
description: Drive the user's real browser (Chromium/Brave/Chrome) — open url, web search, read page text, click, type, screenshot, list/switch tabs. Real backend = Playwright connect_over_cdp (attaches to your existing browser); mock for the binding benchmark. Pure execution (slot-filled, no LLM).
---

# Browser Skill

Deterministic control of the user's **own** browser. Canonical **reflexer** case — each
request is one slot-filled command, no autonomous reasoning.

> **Backends.** Default MOCK echoes JSON (binding-only). The REAL backend uses
> **Playwright `connect_over_cdp`** to attach to a running Chromium/Brave/Chrome started
> with `--remote-debugging-port=9222` (preserves your logins/tabs). On Raspberry Pi /
> ARM, attach to the apt `chromium-browser` (never Playwright's bundled binary); raw CDP
> (`pychrome`) is the lightweight fallback. See `docs/research/browser_skill_options.md`.

## Commands (via bash)
CLI: `python3 agents/skills/browser/browser.py <command>` (aliased `browser`).

`browser open --url "<url>"`
`browser search --query "<text>" [--engine google]`
`browser read-text [--selector "<css>"]`
`browser click --target "<css selector or visible text>"`
`browser type --selector "<css>" --text "<text>"`
`browser screenshot [--path <file>] [--full-page]`
`browser tabs`
`browser tab-switch --id <id>`

## Output format
One JSON line: `{"ok":bool,"data":{...},"error":null|{...},"meta":{...}}`. Exit 0/2.
On an ambiguous `click` target the real backend returns `error.code = "ambiguous"`
rather than guessing.

## Pure-executioner boundary
No smart-waits, no "do this whole task" verbs, no arbitrary JS-eval, no credential
handling — those would require a thinker. The browser is just one more OS surface the
reflexer fills slots against.

## Collisions (why this skill is in the benchmark)
`browser open --url` vs `app open --name` (URL vs app); `browser search` vs `maps search`
(web vs places) vs `spotify search` (web vs music); `browser tab-switch` vs `app switch`.
