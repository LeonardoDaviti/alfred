# Findings: Thinker vs Reflexer — Binding-Only, Same Tasks, Same Checker

_Thesis evaluation chapter. Generated 2026-06-17. Every number cites a saved run under
`benchmark/reports/`. Binding-only (routing assumed perfect); no execution, no network,
`~/.alfred` read-only, `record_execution` never called. **No fabricated numbers.**_

## 0. Question

Where the deterministic action slice is concerned, how big a model does binding actually
need? We compare three conditions on the **same tasks** with the **same checker**:

| condition | model | gets the pattern? | role |
|---|---|---|---|
| **Reflexer** | qwen-3.5-2b | ✅ pattern `args_template` + slots | A.L.F.R.E.D.'s executor |
| **Thinker-small** | qwen-3.5-2b | ❌ only the SKILL.md (free-form agent) | "small model as agent" baseline |
| **Thinker-big** | qwen3.6-35b-A3B (thinking on) | ❌ only the SKILL.md | capability ceiling |

## 1. Method (standardized across both tracks)

- **One task source.** Both tracks read the same flat JSON tasks
  (`alfred/eval/expansion_tasks_phase2*.json`): `{query, expected_pattern_id,
  gold_command_contains, domain}`.
- **One checker.** Success = every `gold_command_contains` token appears
  (case-insensitive) in the **union of the bash commands the agent emitted**. Identical
  semantics in the reflexer harness (`alfred/eval/binding_only_eval.py`) and the thinker
  harness (`src/run-binding-compare.ts`).
- **"Routing assumed perfect"** means: the reflexer is handed the gold pattern; the
  thinker is told which skill via its loaded `SKILL.md` (derived `domain → skill`). Only
  the *binding* stage is under test.
- **Thinker kill policy.** Run the agent to completion, but cap bash calls at
  `expected_moves × 2` (atoms → cap 2) via a watchdog `agent.abort()`, plus a wall-clock
  backstop (`--backstop-ms`). Atoms scored by token coverage over all emitted commands.
- **Side-effect free.** Thinker uses the `bash`-stub (`agents/bash-stub.ts`) — commands
  are recorded and scored, never executed.

## 2. Headline — matched balanced-10 (1–2 tasks per skill, all 7 skills, identical set)

| condition | binding | model size | median latency | tokens/task |
|---|---|---|---|---|
| **Reflexer + pattern** | **10/10 = 100%** | 2B | single LLM call | — (1 call) |
| **Thinker, no pattern** | **10/10 = 100%** | 35B (ctx 131k) | 6.4 s | ~1.3k |
| **Thinker, no pattern** | **3/10 = 30%** | 2B | 1.7 s | ~0.7k |
| **Thinker, no pattern** | **1/10 = 10%** | 4B (ctx 4000 ⚠️) | 2.8 s | ~0.7k |

Sources: `binding-only-phase2-qwen2b-balanced10.txt` (reflexer 10/10),
`thinker-binding-phase2-qwen35b-balanced10.txt` (35B 10/10),
`thinker-binding-phase2-qwen2b-balanced10.txt` (2B 3/10),
`thinker-binding-phase2-qwen4b-balanced10.txt` (4B 1/10).

> **Scale is non-monotonic for unaided binding (4B < 2B < 35B).** Two causes, kept
> separate: (a) **confound** — the 4B is configured at ctx 4000 vs the 35B's 131k, so a
> reasoning model's thinking crowds the SKILL.md; not a clean capability point. (b) **real
> signal** — the 4B emits *higher-quality real* Linux commands than the 2B (`nmcli radio
> wifi off`, `gsettings set …`, `xdg-open …`, `playerctl pause && next`): it *knows the
> true APIs better*, so it free-forms more aggressively and obeys the skill surface less.
> **Capability-to-know ≠ obedience-to-the-surface** — they can trade off. This is why
> scale is an unreliable lever for binding, and distillation (which removes the choice) wins.

> **The result, in one sentence:** a 2B reflexer with a distilled pattern matches a 35B
> free-form thinker's binding accuracy (both 100%), while the *same* 2B without the
> pattern manages only 30% — **distillation substitutes for ~17× the parameters.**

## 3. Full-set numbers (72 atoms / 12 composites)

| track | accuracy | source |
|---|---|---|
| Reflexer-2b — atoms | **72/72 = 100%** (every skill 100%) | `binding-only-phase2-qwen2b.txt` |
| Reflexer-2b — composites | **8/12 = 66.7%** | `composite-binding-phase2-qwen2b.txt` |
| Thinker-2b — atoms | **14/72 = 19.4%** | `thinker-binding-phase2-qwen2b.txt` |

Thinker-2b per-domain (full set): app 0/6, browser 0/16, call 0/8, clock 1/14, focus
1/6, media 3/10, **device_settings 9/12 (75%)**. device_settings scores highest because
its `settings <toggle> --state on|off` surface is simple enough to copy verbatim — the
more a skill needs its *defined vocabulary*, the more the unaided small model fails.

Composite-2b (reflexer): the 4 deterministic composites fill 100%
(focus_session/goodnight_v2/leave_home/morning_alarm); the 2 needing runtime
`composite_slots` (call_contact `name`, download_and_play `url`) fail — a FakeBash/slot-
extraction harness limit, not a model signal (see `findings_reflexer_model_comparison.md` §3).

## 4. Finding A — two distinct small-thinker failure modes

The 2B thinker fails `call` and `app` for *opposite* reasons:

- **`call` → under-triggering (no command at all).** All 8 call tasks: `calls=0`, tokens
  as low as 182. The model treats "call mom", "hang up", "answer the call" as
  conversational/social acts and replies in prose instead of invoking a tool — short
  social imperatives hit its chat prior, and dial/hangup/answer don't "feel" like shell.
  No bash emitted → automatic miss.
- **`app` → wrong-vocabulary (real-shell substitution).** It *does* emit commands, but
  free-forms its Linux pretraining prior: `spotify &`, `spotify open`, `killall firefox`,
  `ps aux | grep`, `ls ~/Desktop` — never the skill's `app open --name`. Capability
  present, obedience to the defined surface absent (the same vocabulary-compliance failure
  seen at the binding layer for sub-2B, here in the thinker).

Both are fatal for binding; both are **erased by the pattern**, whose `args_template`
hard-codes `call dial --to` / `app open --name`.

## 5. Finding B — the reflexer is robust to SKILL.md prose; the thinker is not

`clock` is the diagnostic skill: its SKILL.md documents the real backend
(`systemd-run --user`, `systemctl --user`). On clock binding:

| | clock binding |
|---|---|
| Reflexer-2b (pattern) | **100%** (14/14) |
| Thinker-35B (no pattern) | **30%** (`thinker-binding-phase2-qwen35b-first10.txt`) |
| Thinker-2b (no pattern) | **7%** (1/14) |

**Why even the 35B ignored the clock SKILL.md.** It had the full `clock` command surface,
but the doc *also leaked the implementation*. A reasoning model thinks, reads
"`systemd-run`/`systemctl`", and prefers the concrete mechanism it has a **strong prior**
for over the abstract `clock` alias it has a **weak** prior for — its misses are literally
`systemctl --user list-timers`, `date '+%H:%M'`. Sampling (temp 0.7, top-p 0.95,
presence_penalty 0.5) is a **contributing amplifier** (widens exploration toward the
alternative, penalizes re-emitting the `clock` token) but **not the root cause**: the
prior-pull toward the documented-and-familiar systemd path would likely persist even at
temp 0. Root cause = leaked implementation detail × strong systemd prior.

Interpretation: for the *thinker*, SKILL.md is a **soft** prompt mediated by reasoning,
priors, and sampling. For the *reflexer*, the pattern `args_template` is a **hard**
constraint — no prose to reason around. (Fix for the thinker: keep `systemd-run` out of
the agent-facing doc; expose only the `clock` CLI.) This robustness-to-authoring is a
productization argument for distillation.

## 6. What the pattern costs, and how to read the comparison

**What a pattern requires** (the cost of the reflexer's 100%): each atom is a signature +
trigger regex + slots + the **`args_template` (exact command shape)** + validators + NL
intent/example-queries for the embedder, plus a working skill CLI. And the 100% is
*conditional*: the pattern must **exist** and routing must have **picked it**
(binding-only assumes this).

**This is a systems/efficiency result, not a capability result.** The reflexer is handed
the template and only fills slots — a strictly easier task than free-form generation. The
legitimate claim is *not* "2B is smarter than 35B"; it is: **on the deterministic slice
where intents are repeatable enough to distill, a 2B constrained executor matches a 35B
free-form thinker's binding accuracy at ~17× smaller, far lower latency and tokens.** The
reflexer trades generality (works only for distilled intents — a cold-start/coverage cost)
for efficiency; the thinker is general but expensive and vocabulary-unreliable. Neither
alone is optimal — the optimum is the **two-tier split**, and this comparison quantifies
exactly *why* the split pays.

**Three caveats that must travel with the headline:**
1. The reflexer is handed the template (constrained task).
2. Coverage is limited to distilled intents.
3. **100% is the binding-stage ceiling.** End-to-end accuracy =
   P(pattern exists) · P(route correct) · P(bind), and **routing is the bottleneck**
   (66–85%, see `findings_retrieval_and_selection.md` / `reflexer_status_and_productization.md`).

## 7. Efficiency (binding, balanced-10)

- Thinker-35B: median **6.4 s/task**, **~1.3k tokens/task** (multi-step agent loop).
- Thinker-2b: median **1.7 s/task**, **~0.7k tokens/task** — and still only 30%.
- Reflexer-2b: a **single** `generate_command` call (one forward pass, no agent loop).
  (Exact reflexer token count is not logged by `binding_only_eval.py`; the structural
  asymmetry — one call vs a multi-step loop — is the point. Logging reflexer tokens for an
  exact ratio is a small follow-up.)

## 8. Conclusions

1. **Distillation, not scale, produces binding.** 2B+pattern = 35B-thinker (both 100%
   balanced); 2B-thinker alone = 30%. The pattern is worth ~17× parameters here.
2. **Small unaided thinkers fail two ways** — under-triggering (no action) and
   wrong-vocabulary (real-shell substitution) — both removed by the pattern.
3. **The reflexer is robust to SKILL.md authoring quality; the thinker is not** — a
   productization argument for distilling the deterministic head.
4. **Frame the comparison as efficiency, gated by routing.** The binding ceiling is solved;
   the open bottleneck is routing.

## 9. Economics — is reflexing worth it, or just buy a bigger model / better router?

The central thesis question, answered as cost accounting.

**A pattern is a frozen answer shape.** The reflexer never *solves* the task — it
slot-fills a solution found once. That is why a 2B matches a 35B on it.

**Distillation = knowledge distillation into a *symbolic* artifact.** The big model is the
**teacher** that mints the pattern *once* (offline); the reflexer is the **student** that
runs it forever (on-device). The big model's cost is paid at distillation time, **not at
inference time** — and unlike a fine-tune, the symbolic pattern keeps plug-and-play
generality (add a JSON, no retraining).

**The distillation pipeline (offline, one-time per intent):** log thinker trajectories
(`query → successful command`) → cluster queries by intent (embed + HDBSCAN) → one
big-model call abstracts variable args into slots, emits `args_template`, generates the
trigger regex + example_queries → validate the candidate with the *small* reflexer over
held-out queries (our binding-only harness) → promote shadow→active. Composites are mined
from frequent atom co-occurrence in trajectories.

**Cost model (order-of-magnitude; illustrative where not directly measured):**

| | one-time (distill) | per-invocation (forever) |
|---|---|---|
| Reflexer atom | ~5–15k big-model tokens + ~1–5 min human review | ~0.3k small-model tokens, <1 s, **fits on-device (2B)** |
| Thinker (big) | 0 | ~1.3k big-model tokens, ~6.4 s, **cannot fit on-device (35B)** |

**Break-even:** distillation pays when
`(cost_thinker − cost_reflexer) · N_invocations > D_distill + maintenance`.
With savings ≈ ~1k tokens/invocation and D ≈ ~10k tokens to mint an atom →
**break-even ≈ 10 invocations** — before counting the ~17× per-token size discount, the
6.4 s→<1 s latency, energy, and on-device feasibility. For a *head* intent (timers, play,
call, toggle — thousands of invocations/user) it is a 100–1000× net win; for a *tail*
intent invoked once it never amortizes → route to the thinker. This is the **power-law /
Pareto** argument: distill the small, high-frequency head; thinker the long tail. (Apple
App Intents = distilled head; PCC/Gemini = thinker tail — the same bet.)

**Atoms vs composites.** Distill atoms aggressively (stable, reusable, ~100% reflexable).
Distill only high-frequency, mostly-deterministic composites; those needing runtime
`composite_slots` (call_contact `name`, download_and_play `url`) are where the reflexer
still struggles (8/12) → leave variable multi-step automations to a planner/thinker.

**Reflexer vs bigger model vs router — a category error to pick one:**
- **Bigger model alone** loses on the head: per-invocation cost *forever*, higher latency/
  energy, can't fit on-device, and still vocab-unreliable (35B clock 30%, 4B 10%). Best
  spent as the **offline teacher + tail fallback**, not the everyday runner.
- **Better router** is necessary but not sufficient: routing is the bottleneck (66–85%),
  so it must be funded regardless — but a router only *decides*, it does not *execute*; it
  improves both tiers (orthogonal, not an alternative).
- **Reflexer** wins the head: cheapest per-invocation, on-device, robust to doc phrasing —
  *conditioned on* the pattern existing (distillation cost) and routing picking it.

**Verdict.** Reflexing is worth it **exactly on the high-frequency deterministic head**,
where one-time distillation amortizes over many cheap on-device invocations. Spend the big
model as the **distiller + tail fallback**; fund the **router regardless** (it gates both
tiers). "Just buy a bigger model" is correct only if the workload has **no repeatable
head** — and the Pixel/Apple usage data says the head is enormous. **When reflexing is NOT
worth it:** no repeatable head; churny skill APIs forcing constant re-distillation; or a
router too weak to place intents (misroutes to the wrong atom are the dangerous failure —
hence the router is the gating investment).

### Reproduce
```
# reflexer (per skill / balanced)
ALFRED_LLM_MODEL=qwen-3.5-2b ALFRED_LLM_URL=http://127.0.0.1:8005/v1 \
  .venv-eval/bin/python -m alfred.eval.binding_only_eval alfred/eval/expansion_tasks_phase2.json
# thinker (same tasks, same checker)
tsx src/run-binding-compare.ts --model qwen-3.5-2b   --backstop-ms 45000
tsx src/run-binding-compare.ts --model qwen3.6-35b   --tasks alfred/eval/expansion_tasks_phase2_balanced10.json --backstop-ms 240000
```
