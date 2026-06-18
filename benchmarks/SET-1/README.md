# SET-1 — Settings backend benchmark (mutable state, end-state oracle)

Isolated benchmark for the live-distillation experiment. Spec:
`docs/spec_settings_distillation.md`. A Pixel-style settings store the thinker operates,
scored by the **end state** (not command matching), so "right command / wrong outcome"
and over-editing both fail.

## Files
- `settings_schema.json` — canonical state (4 setting types: toggle / ranged 0–10 /
  free-text / nested-app).
- `settings.py` — the **deep** `settings` script: `get` / `set` / `search`; hides path
  traversal, type/range validation, errors. State file = `--state` > `SET1_STATE` env >
  canonical.
- `SKILL.md` — settings skill doc (for E2).
- `tasks.json` — 20 tasks (5 per type), each `{query, initial, gold}`; mix of absolute +
  relative (read-before-write) tasks.
- `oracle.py` — the single success checker: gold paths match **and** no collateral edits.
- `preflight.py` — proves every task's gold is achievable via the script and the oracle
  passes when it should (run before any model).
- `run.ts` — runner. `--mode e1` (manual file edit, no script) | `e2` (settings script).
  Fresh sandbox per task, kill policy (20 calls + wall-clock), end-state scoring.

## Run
```bash
python3 SET-1/preflight.py                                   # must be 20/20
tsx SET-1/run.ts --mode e1 --model qwen-3.5-2b               # manual-edit baseline
tsx SET-1/run.ts --mode e2 --model qwen-3.5-2b               # settings-script
tsx SET-1/run.ts --mode e2 --model qwen3.6-35b --backstop-ms 240000
```
`score(e2) − score(e1)` = the measured value of the abstraction. Reports →
`benchmark/reports/set1-*.json`.

## Status
- E1 / E2 + backend + oracle + preflight: **built & validated** (preflight 20/20; smoke
  qwen-3.5-2b: e2 7/7, e1 1/3 — abstraction gap visible).
- **Deferred** (per spec, core-first): E3 distillation (session + cold-start) and E4
  reflexer-on-distilled-patterns. Both reuse this task set + gold end-states.
