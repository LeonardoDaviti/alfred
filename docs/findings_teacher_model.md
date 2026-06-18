# The Teacher Model in Distillation: Cloud vs Local, What the Local 35B Missed, and How to Fix It

_Thesis evaluation chapter. 2026-06-18. All numbers from saved runs
(`benchmark/reports/set2-reflexer-*`, `SET-2/patterns_distilled*.json`, the `pi` session).
Distillation = cold-start: each teacher saw ONLY `SET-2/SKILL.md` + `settings_schema.json`,
never the tasks or gold. Quality measured by running the SAME qwen-3.5-2b reflexer on each
teacher's patterns over the same 25 single-setting tasks, scored by the end-state oracle._

## 1. Why the teacher matters

In the executioner paradigm the expensive model is used **once, offline, as a teacher** that
distills device conventions into patterns; the cheap on-device reflexer applies them forever.
The whole approach therefore rests on a question we can now answer empirically: **how much
does the choice of teacher matter, and can a *local* model be the teacher?**

We compare two cold-start distillers under an identical prompt and constraints:
- **Cloud teacher** — Claude Sonnet 4.6 (`SET-2/patterns_distilled.json`).
- **Local teacher** — qwen3.6-35b via `pi --thinking high` (`SET-2/patterns_distilled_pi.json`).

## 2. Headline result

| teacher | structure (keys / namespaces) | conventions correct | **reflexer end-accuracy** | cost |
|---|---|---|---|---|
| **Sonnet 4.6 (cloud)** | 32/32, 0 errors | ~5/7 critical | **20/25 = 80%** | one cloud call |
| **qwen3.6-35b (local)** | 32/32, 0 errors | ~2/7 critical | **15/25 = 60%** | local, ~slow |

The 60% figure is **confirmed by two independent task→atom mappings** (our key-matched
mapping, and the local model's own slug mapping) — it is not a harness artifact.

**Teacher quality propagates straight to the student: −20pp** on the *same* reflexer and
tasks. A local model can serve as a teacher, but a weak one **bakes its own wrong priors
into the patterns**, which the student then faithfully executes.

## 3. What the local 35B missed — itemized

Both teachers are **perfect on structure**: every one of the 32 keys covered, every
namespace (`system`/`secure`/`global`) correct. Discovery — *which key, which namespace* —
is easy. The gap is entirely in **semantic conventions** (the values).

| setting | gold | local 35B | Sonnet | local error type |
|---|---|---|---|---|
| `zen_mode` "total silence" | **2** | **1** (swapped with priority) | 2 ✓ | **wrong prior** |
| `location_mode` "high accuracy" | **3** | **2** (enum collapsed to 0/1/2) | 3 ✓ | **enum compression** |
| `screen_brightness` 75% | **191** | states "75%=192" | 191 ✓ | **arithmetic / worked-example error** |
| `screen_brightness` 25% | **64** | encoding let student emit `25` | 64 ✓ | **under-specified formula** |
| `font_scale` "large" | **1.15** | "1.25"/"1.3" region | 1.15 ✓ | **scale step error** |
| `font_scale` "largest" | **1.30** | 1.4 | 1.45 | **genuinely ambiguous (both miss)** |
| `wifi_sleep_policy` "never" | **2** | 0 | 0 | **shared wrong prior (both miss)** |
| `airplane_mode` | set flag only | verbose "disables all radios" → student also toggled wifi/bt | clean | **over-verbose → student collateral edits** |

Behaviourally, the local model also reported **"All verified ✓"** with no caveats, while
**silently wrong** on `zen_mode`/`location_mode`. Sonnet, by contrast, *flagged* its own
uncertainty (font scale, zen version-dependence, input-method format).

## 4. How it missed — a taxonomy of failure modes

1. **Wrong prior (most damaging).** `zen_mode` total-silence→1 and `wifi_sleep_policy`
   never→0 are confident, specific, and wrong. Notably the `zen_mode` error is the **same**
   one the 35B made as a *thinker* (§ findings_settings_distillation §3) — a **consistent
   knowledge gap**, not sampling noise. The model "knows" a wrong fact.
2. **Enum compression.** `location_mode` was rendered as a 3-value enum (0/1/2) instead of
   4 (0–3), dropping "sensors only" and shifting high-accuracy to 2. The model simplified a
   conventional enum toward a more "natural" on/off-ish shape.
3. **Arithmetic / worked-example error.** Right formula intent (`%×255/100`) but a wrong
   concrete example ("75%=192"), and an under-specified rule that let the student emit the
   raw percent (`25`). The transform was left to the LLM and neither model nor student is
   reliable at it.
4. **Over-verbosity → collateral.** Encodings that editorialize about side-effects
   ("airplane mode disables Wi-Fi, Bluetooth, mobile data…") **leaked into the student's
   behaviour**: the 2B then toggled those radios too, failing the no-collateral oracle.
   More words in the pattern = more ways for a small student to over-act.
5. **Mis-calibration.** No uncertainty signalling ("all verified"), so a downstream
   pipeline cannot tell which atoms to trust or route for human/device verification.
6. **Genuinely undiscoverable conventions.** `font_scale` "largest" and `wifi_sleep` "never"
   are device/version-specific and **not derivable** from the skill doc or general
   knowledge — *both* teachers miss them. No amount of teacher capability fixes these; only
   observing the real device does.

## 5. Why (root causes)

- **Weaker / quantized world-knowledge** on niche Android internals (AOSP enum constants)
  than a frontier cloud model — hence the wrong priors and enum compression.
- **Poor calibration** — it does not know what it does not know, so it asserts wrong
  conventions instead of flagging them.
- **Verbose generation** — a smaller instruct model pads encodings with side-effect prose
  that becomes an attack surface for an over-eager student.
- **No grounding** — cold-start gives it no way to *check* a convention against reality, so
  it can only emit priors.

## 6. How to make the local teacher better (concrete, ranked)

1. **Ground the teacher in the real device (biggest lever).** Give the teacher read-only
   `settings get`/`list` access (or an authoritative dump) so it can *observe* the actual
   codes before writing the encoding. This converts the undiscoverable conventions
   (`font_scale` largest, `wifi_sleep` never, the `zen`/`location` enums) from *guesses*
   into *facts*. This is **session-based / grounded distillation** and would fix essentially
   every convention error — including the ones the cloud teacher also misses. (Integrity:
   ground on the device/dev split, never on the eval gold.)
2. **Inject authoritative reference into the prompt (RAG).** Feed the relevant AOSP
   `Settings.System/Secure/Global` constant tables (zen_mode, location_mode,
   wifi_sleep_policy, brightness range, timeout units) into the distiller context. Cheap,
   offline, eliminates the wrong-prior class without device access.
3. **Determinize the transforms inside the pattern.** Move `%→0–255` arithmetic and enum
   label→code lookups out of natural-language "encoding" prose into a small deterministic
   function/table in the pattern. Then neither the (weak) teacher's worked example nor the
   (weak) student's arithmetic matters — kills the brightness/enum-application errors for
   *both* models.
4. **Constrain output + lint.** Enforce a tight schema: one short encoding line, an explicit
   `enum: {label: code}` map (forces enum completeness, catches the location compression),
   a `value_range`, and **no free-text side-effect prose** (kills the airplane collateral).
   A validator rejects atoms missing codes or with out-of-range examples.
5. **Force calibration.** Require a `confidence` + `assumptions` field per atom. Low-confidence
   atoms are auto-routed to device-grounding (lever 1) or human review. This recovers the
   honesty Sonnet showed and the local model lacked.
6. **Critic / self-verify pass.** A second pass (or a second model) checks each atom's
   convention against the schema + reference, and a *dry-run* executes the candidate command
   on a sandbox to confirm it's well-formed (not against gold). Catches compression and
   example errors.
7. **Sample-and-vote.** Distill N times at temperature and majority-vote each convention;
   disagreement flags the ambiguous/uncertain ones for grounding.
8. **Hybrid division of labour.** Use the local model for what it already does perfectly —
   **structure/coverage** (32/32 keys, namespaces) — and a strong source (docs/device) for
   the **conventions**. The teacher need not be one model.
9. **Fine-tune the local model on AOSP settings conventions** (post-thesis; ties to the
   Gemma fine-tune plan) so the priors themselves become correct.
10. **Iterative distill → test → re-distill (the strongest *automated* lever).** Run the
    cold-start patterns, **execute them on a real device / sandbox and observe the result**,
    feed the failures back to the teacher, and re-distill — 2–3 rounds. This is *automated
    session-based distillation*: the teacher's wrong priors (zen, location, wifi-sleep) get
    corrected by *observation* rather than by a bigger model, and it would lift the local
    teacher toward the cloud teacher's quality without changing the teacher at all.
    **Guardrails (critical):** (a) iterate on a **dev/calibration split or the live device,
    never the eval gold** — otherwise it overfits the benchmark (leakage, exactly the
    post-hoc "fix the encodings" temptation we rejected); (b) **cap the rounds** (2–3) and
    require improvement on a *held-out* split, or stop; (c) **lint for minimality each
    round** so corrections fix conventions without accreting special-case cruft — the
    pattern must get *more correct*, not *more complex*.

## 7. Implications for the thesis

- The **distiller is a swappable component**, and its quality is measurable end-to-end via
  the student (−20pp here). This makes "teacher choice" a first-class design axis.
- **Cold-start with a weak local teacher is the worst case.** Two routes recover quality:
  a **strong (cloud) teacher** as a one-time step, or a **grounded local teacher** (lever 1)
  that observes the device. Both preserve the on-device runtime — only the *teaching* step
  differs.
- The split is clean and reusable: **structure is learnable by any 35B; conventions require
  either a stronger teacher or device grounding; cryptic transforms should be determinized
  out of the LLM entirely.** That is the recipe for a robust automated distillation pipeline.

## 7b. Does iterative refinement break the "simple reflex" idea? — No.

A natural worry: if we add 2–3 rounds of test-and-re-distill, are we not making the reflexer
*complex* — contradicting the whole point that it should be a simple, instant reflex (as in
the human brain)?

**No — because the iteration lives entirely in the *learning* phase, not the *reflex*
phase.** The two are cleanly separated:

- **Learning (distillation): slow, iterative, feedback-driven, expensive, offline,
  done once per pattern.** This is where the test→re-distill loop runs.
- **Reflex (runtime): a single forward pass over a *frozen* pattern — one shot, fast,
  on-device.** Nothing about the runtime changes no matter how many rounds the teacher took.

This is exactly how human reflexes/skills form. Procedural memory is *not* born simple — it
is **practiced**: many repetitions with error-correction and feedback, gradually
consolidated (myelination) until the skill executes **automatically and instantly, without
deliberation**. The slow, effortful practice is the analogue of iterative distillation; the
fast, unconscious execution is the analogue of the reflexer firing a frozen pattern. **The
practice making the skill better does not make the skill *slower or more conscious* — it
makes it more *correct*.** Same here: more distillation rounds make the pattern more
correct, while the reflex stays a one-shot lookup.

The only way iteration *would* threaten simplicity is if it let patterns accrete special
cases — which is why guardrail (c) above lints for minimality every round: **corrections
improve the convention, they do not grow the pattern.** Simplicity is preserved by
construction: the reflex remains "query → fill the frozen pattern → emit one command."

## 8. Reproduce
```bash
# local teacher (pi / qwen3.6-35b): see SET-2/patterns_distilled_pi.json (frozen)
# evaluate either teacher's patterns with the same 2B reflexer (key-matched mapping):
python3 /tmp/build_eval.py SET-2/patterns_distilled_pi.json   # or patterns_distilled.json
tsx SET-2/run.ts --mode reflexer --model qwen-3.5-2b --patterns patterns_distilled_pi.json --tasks _distill_eval.json
```
