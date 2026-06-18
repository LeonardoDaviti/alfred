# Findings: Reflexer Model Comparison — Binding-Only (routing assumed perfect)

_Thesis evaluation chapter. Generated 2026-06-16. All numbers from real runs saved
under `benchmark/reports/binding-only-*.txt`. Binding-only harness
(`alfred/eval/binding_only_eval.py`): the reflexer is handed the GOLD pattern for
every task (no router, no arbiter), isolating command-generation quality. No
execution, no network, ~/.alfred read-only. **No fabricated numbers.**_

## 0. Why this matters

The binding-only ceiling (§findings_expansion_skills 6b) showed binding ≈ 96% with
ministral-3-3b, and that **routing, not binding, is the bottleneck**. This raised the
question: *which small model is the best reflexer (command generator)?* We swept the
Qwen3.5 family (0.8B / 2B / 4B) against ministral-3-3b on the 409-atom expansion set.

## 1. Atom binding accuracy (409 expansion atom tasks, routing assumed perfect)

| model | overall | docker | ffmpeg | home_assistant | service | spotify | system | youtube |
|---|---|---|---|---|---|---|---|---|
| qwen-3.5-0.8b | 380/409 = **92.9%** | **0%** | 100% | 89.3% | 83.3% | 96% | 100% | 100% |
| ministral-3-3b | 391/409 = **95.6%** | 100% | 100% | 100% | 100% | 98% | 100% | **81%** |
| **qwen-3.5-2b** | **409/409 = 100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| qwen-3.5-4b | docker+service 24/24 = 100% (full 409 not persisted) | 100% | — | — | 100% | — | — | — |

(ministral on the full 627-task set incl. core skills: 601/627 = 95.9%; its misses are
youtube `--skip-download` ×16, reminders `remindme due` ×7, `spotify next` ×2.)

> **Data-integrity note.** No full-409 run was saved for qwen-3.5-4b; only its
> docker+service subset (100%) was captured live. A "qwen-3.5-4b = 95.6% / youtube 81%"
> figure that circulated in an earlier summary is **identical to the ministral-3-3b run**
> and was a mislabel — it is not recorded here as 4B. Re-run when 8004 is back to fill
> the 4B row.

### Headline: **qwen-3.5-2b is the best reflexer found**
Perfect 100% across all 409 atoms — beating both the smaller 0.8B (92.9%, catastrophic
docker) and the larger ministral-3-3b (95.6%, prunes `--skip-download`). It is the
smallest model with perfect binding *and* perfect vocabulary compliance — the sweet
spot for a local 4 GB reflexer.

## 2. The vocabulary-compliance finding (the new result)

The diagnostic subset is docker+service (the two skills whose CLI alias differs from the
real binary name: `dock`/`svc`, not `docker`/`service`):

| model | docker | service | overall |
|---|---|---|---|
| **qwen-3.5-0.8b** | **0/12 (0%)** | 10/12 (83.3%) | **10/24 (41.7%)** |
| qwen-3.5-2b | 12/12 | 12/12 | 100% |
| qwen-3.5-4b | 12/12 | 12/12 | 100% |
| ministral-3-3b | 12/12 | 12/12 | 100% |

**qwen-3.5-0.8b systematically emits the real binary name** (`docker start`,
`service ...`) **instead of the skill's defined alias** (`dock start`, `svc ...`) — its
most-missed gold tokens are `dock start/stop/restart/remove/logs/ps`, each exactly the
subcommand it replaced with `docker`. The model is **semantically correct** (`docker
start` would work on a real host) but **schema-noncompliant**: it ignores the alias
fixed in the pattern's `args_template`, even at temp 0.2.

This is **intentional to test**: the skill CLI (`dock.py`) is the only interface the
agent may use; it defines `dock`, so `docker` would not resolve. So this is a genuine
failure, not an artificial one.

**Interpretation — capability emergence.** Vocabulary/schema compliance is a *capacity
threshold* that appears between 0.8B and 2B: the 0.8B model lacks the capacity to
reliably obey a lexical constraint that contradicts its strong prior (the real command
name); the 2B model already complies perfectly, at parity with 4B. Scale beyond 2B buys
nothing here — the threshold, not a gradient, is the story.

### Model-specific *signature* failure modes
Each small model fails differently, which is itself a finding (there is no universal
small-model binding weakness):
- **ministral-3-3b** — prunes semantically-secondary *static flags* (`--skip-download`
  on youtube → 81%); perfect vocabulary compliance.
- **qwen-3.5-0.8b** — violates *vocabulary* (docker→`docker`, 0%); but prunes **nothing**
  (youtube 100% — keeps `--skip-download`).
- **qwen-3.5-2b** — neither failure mode; 100%.

## 3. Composite binding (167 composite tasks) — and a harness caveat

| model | bound (no executor error) | filled (all slots resolved) |
|---|---|---|
| qwen-3.5-0.8b | 144/167 = 86.2% | 68/167 = 40.7% |
| qwen-3.5-2b | 145/167 = 86.8% | 59/167 = 35.3% |

**The "filled" column is NOT a model discriminator — it is harness-bound.** Both models
fail the *exact same* composites (birthday_reminder 0/5, flight_deal_watch 0/5,
youtube_to_mp3 0/9, rain_umbrella_* 0/N, … identical for both), which means the cause is
the eval harness, not the model: the FakeBash backend returns no real inter-step data,
so composites that (a) chain `step[N]` outputs or (b) need runtime `composite_slots`
resolve to `None` regardless of which LLM is used. Only the **bound** metric (~86%,
executor runs end-to-end without a binding/slot error) is a meaningful signal here; it is
comparable across both models.

Composites that *do* fill cleanly for both are the literal/deterministic ones
(ha_goodnight 9/9, spotify_party_mode 9/9, movie_night, focus_mode, workout_session,
morning_brief, reminders_today, local_scout, weekend_planner). **Next step:** to make
composite slot-filling a real model signal, the harness needs a per-composite stubbed
backend that returns realistic step outputs (so `step[N]` chains resolve) — then re-run.

## 4. Conclusions
1. **Adopt qwen-3.5-2b as the reflexer.** 100% atom binding, perfect vocabulary
   compliance, smallest viable size. (Config: `qwen-3.5-2b`, port 8005.)
2. **Vocabulary compliance is a capability threshold between 0.8B and 2B** — a clean
   capability-emergence result for the thesis; do not deploy sub-1B models as reflexers.
3. Small-model binding failures are **model-specific signatures** (flag-pruning vs
   vocabulary-violation), not a single universal weakness.
4. Composite slot-filling needs a better harness before it can rank models; current
   "filled" numbers reflect FakeBash, not the LLM.
5. **Open:** persist a full-409 qwen-3.5-4b run to complete the table (8004).
