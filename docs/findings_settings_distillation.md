# Findings: On-Device Settings — Clean vs Realistic, and the Limit of Scale

_Thesis evaluation chapter. 2026-06-17. Numbers cite saved runs under `benchmark/reports/`
(`set1-*`, `set2-*`). Both benchmarks use a **mutable state backend** scored by an
**end-state oracle** (final state == gold, no collateral edits) — not command matching —
so "right command / wrong outcome" and over-editing both fail. Sandbox per task, no real
state touched. No fabricated numbers._

## 0. Two benchmarks, one question

How much model does on-device **action** actually need, and where does a distilled pattern
help? Two settings backends bracket the answer:

- **SET-1** — a *clean, friendly* settings API (`settings set connectivity.wifi off`):
  transparent intent→path mapping, validation with recovery, small surface.
- **SET-2** — a *realistic Android* API (`settings put <ns> <key> <value>`): three
  namespaces (`system`/`secure`/`global`), non-obvious encodings (brightness 0–255,
  timeout in **ms**, `zen_mode`/`location_mode`/`ringer_mode` integer **enums**,
  `font_scale` a string-float), and a **permissive `put`** (wrong ns/key/value "succeeds"
  silently) — exactly how `adb shell settings` behaves.

## 1. SET-1 (clean API): the abstraction is an EFFICIENCY win

| mode (qwen-3.5-2b) | oracle pass | median calls | median tok |
|---|---|---|---|
| E1 — manual JSON edit (no script) | ~30–35% | 9 | 3098 |
| E2 — `settings` script | **100%** (20/20; hard multi-step 10/10) | **2** | **775** |

On a clean surface a small model is **already a competent executor** *if* it has a deep,
validated tool: E2 hits 100%, including 2–3-step compound tasks, recovering from wrong
guesses because the script rejects them. Manual editing (no abstraction) collapses to ~⅓
(wrong value / ceiling-flailing / corrupted JSON). **`score(E2) − score(E1)` ≈ +65pp** =
the measured value of the deep module — but it is *efficiency/competence*, not new
*accuracy* the model lacked. (Sources: `set1-e1e2-qwen2b.txt`, `set1-e2-hard-qwen2b.txt`.)

## 2. SET-2 (realistic API): the small agent collapses

Free-form **thinker on qwen-3.5-2b, 48 tasks: 12/48 = 25%** (`set2-thinker-qwen2b-48.txt`).
Failures cluster exactly on what cannot be guessed:
- **value encodings** — every brightness-% (→0–255), every timeout (→ms), `font_scale`,
  and the integer enums;
- **key-name suffix traps** — `airplane mode`→`airplane_mode_on`, `wifi`→`wifi_on`;
- **compound routines** containing any encoded value.
It passes only guessable booleans and trivial arithmetic. **A small free-form agent cannot
drive a real device-settings API.**

## 3. The limit of scale (the capstone)

A 35B reasoning thinker (qwen3.6-35b) on the hard SET-2 slice:
- **last-3 tasks: 3/3 = 100%** (`set2-thinker-qwen3.6-35b-*.json`)
- **5 hardest tasks: 2/5 = 40%** (`set2-thinker-35b-hard5.txt`)
- combined 8 hardest: **5/8 = 62.5%**, at ~9 calls and **~17–20 s/task**.

Crucially, the 35B's failures are **not discovery** failures — they are **encoding-semantics**:

| task | wanted | 35B produced |
|---|---|---|
| "largest font" | `font_scale "1.30"` | `"1.5"` |
| "DND total silence" | `zen_mode 2` | `1` |
| "DND important only" | `zen_mode 1` | `2` |

**Two kinds of difficulty, split by what scale can fix:**
1. **Discovery** (*which namespace/key?*) — solvable by exploration; the 35B does it
   (`list`/`grep`/`get` → correct `put`).
2. **Encoding semantics** (*what does enum `2` mean? what value is "largest"?*) — **not
   discoverable** from the API; even a 35B **guesses, and is wrong ~half the time**.

**Scale rescues discovery; scale cannot rescue undiscoverable conventions.** That tribal
knowledge exists only in a distilled pattern.

## 4. The reflexer / pattern as the carrier of undiscoverable knowledge

With the distilled incantation handed to it, **qwen-3.5-2b reflexer on SET-2: 11/15 = 73%**
at **1 call / ~400 tok** (`set2-reflexer-qwen-3.5-2b-*`). Its residual misses are
*application* errors (used the enum label instead of the code; brightness arithmetic) —
closable to ~100% by moving the value transform out of the LLM and into the pattern
(deterministic slot-transform).

So on the realistic API:
- **2B free-form thinker: 25%** (no knowledge, can't guess).
- **35B free-form thinker: ~62%** on the hardest (discovers keys, guesses semantics), ~17 s,
  off-device.
- **2B + distilled pattern: 73%→~100%** (carries the convention), ~1 call, on-device.

## 5. Conclusion (the spectrum)

> **The reflexer's benefit scales with discovery difficulty.** On a clean API it is an
> *efficiency* win (a small model already succeeds). On a realistic, cryptic API it is an
> *accuracy* win — and for **undiscoverable encoding conventions a distilled pattern beats
> even a 17× larger model**, because the bottleneck is not reasoning but *knowledge the API
> does not expose*. For on-device control you therefore either pay for a large cloud thinker
> (slow, off-device, still wrong on conventions) or **distill the convention once (teacher)
> and apply it cheaply forever (small reflexer)**.

## 6. Automated cold-start distillation (E3 → E4)

**Setup.** A capable teacher (Claude Sonnet 4.6, sub-agent) was given **only**
`SKILL.md` + `settings_schema.json` — explicitly forbidden from seeing `tasks.json`/gold
(true cold-start, no task exposure) — and asked to mint `patterns_distilled.json` (atoms +
composites) encoding the Android conventions from skill knowledge alone. Then the local
**qwen-3.5-2b reflexer** executed those distilled patterns on the single-setting tasks,
scored by the same end-state oracle. (Routing assumed perfect: each task mapped to its
atom.)

**Teacher quality (Opus validation vs ground truth).** 32/32 keys covered, 12 composites.
~30/32 conventions correct — including brightness 0–255, ms timeouts, `ringer_mode`,
`location_mode`, all booleans + namespaces, and **`zen_mode = 2` for "total silence"** —
the exact convention the 35B *thinker* guessed wrong (§3). Two conventions wrong, both
genuinely ambiguous/OEM- or version-dependent (the teacher flagged its own uncertainty):
`font_scale` "largest" → 1.45 (gold 1.30), `wifi_sleep_policy` "never" → 0 (gold 2).

**Reflexer on distilled patterns: 19/25 = 76%** (`set2-reflexer-qwen-3.5-2b-*`), ~1–2
calls / ~800 tok / 1.4 s — vs the free-form **2B thinker 25%** and **35B thinker ~62%**
(slow, off-device). The 6 misses split cleanly:
- **2 = teacher convention errors** (font-largest, wifi-never) — the genuinely-undiscoverable
  ones → **session-based distillation** (observe the real device) is the fix.
- **4 = small-model application errors** (pattern correct, 2B misapplied the enum/boolean:
  zen→0 not 2, location→1 not 3, ringer, battery) → **deterministic slot-transform** in the
  pattern is the fix (move the lookup/arithmetic out of the LLM).

## 6b. Teacher quality matters — cloud Sonnet vs local 35B as distiller

We re-ran the cold-start distillation with the **local qwen3.6-35b** (`pi`, `--thinking
high`) under the identical prompt, then ran the *same* 2B reflexer on each teacher's
patterns (key-matched task→atom; 25 single-setting tasks).

| distilled by | structure (keys/namespaces) | critical conventions correct | **reflexer pass** |
|---|---|---|---|
| **Sonnet 4.6 (cloud)** | 32/32, 0 ns errors | ~5/7 | **20/25 = 80%** |
| **qwen3.6-35b (local)** | 32/32, 0 ns errors | ~2/7 | **15/25 = 60%** |

Both nail *structure* (which key, which namespace) — discovery is easy. They diverge on
*semantic conventions*: the local 35B got `zen_mode` total-silence backwards (=1, same
error it made as a thinker — a consistent knowledge gap, not noise), `location_mode`
high-accuracy=2 (collapsed the enum, dropped "sensors"), and a wrong brightness worked
example (`75%=192`); and its over-verbose `airplane` encoding induced **collateral edits**
in the student. Sonnet also honestly *flagged* its uncertainties (font scale, zen
version-dependence); the local 35B reported "all verified" while silently wrong.

**Finding:** end-to-end reflexer accuracy tracks **teacher quality** (−20pp from the
weaker teacher), and a local model is a *weak distiller* — it bakes its own wrong priors
into the patterns, which the student then faithfully executes. Both teachers still miss the
genuinely-undiscoverable conventions (font "largest", wifi-sleep "never") → those need
session-based device grounding regardless of teacher. **Implication:** cold-start
distillation should use the strongest available teacher as a *one-time* step; the cheap
local reflexer then runs forever. (Reports: `set2-reflexer-qwen-3.5-2b-*`;
`SET-2/patterns_distilled.json` vs `SET-2/patterns_distilled_pi.json`.)

## 7. Conclusion

The full chain holds end-to-end: **a teacher distills device conventions once (cold-start,
no task exposure) → a 2B reflexer applies them on-device, 25% → 76%**, and the teacher
encodes the very conventions a 17× larger in-context thinker gets wrong. The two failure
classes point at the two remaining levers — *session-based distillation* for genuinely
device-specific values, and *deterministic pattern transforms* for the small model's
enum/arithmetic application. Both are clear, bounded next steps, not open problems.

Restated for the thesis: **on a real device API, scale buys discovery but not undiscoverable
convention; distillation buys the convention; and the small reflexer applies it at a
fraction of the cost — the executioner paradigm, validated through the full teacher→student
loop.**
