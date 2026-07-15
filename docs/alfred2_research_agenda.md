# ALFRED 2.0 Research Agenda

Status: working note, 2026-07-06. Ideas by David; analysis, prior art, and
experiment designs added in discussion. This is the research-side successor to
the thesis: the goal is no longer a product but a **laboratory for small-agent
capabilities** — benchmarks we own, ablations we can trust, and findings that
build foundations, not just features.

Guiding principle inherited from the thesis: **the oracle is the asset.** Every
idea below is worth doing only to the degree it stays verifiable. Anything that
cannot be scored automatically degrades into a demo.

---

## 0. Priority map (analyzer's verdict, discuss before accepting)

| # | Idea | Verdict | Why |
|---|------|---------|-----|
| 1 | Memento-Skills mode + counterfactual rerun | **Highest impact** | Genuinely under-measured in the literature; extends the thesis's frozen-pattern rigor into self-evolution; strongest career artifact |
| 2 | Self-vs-teacher evolution (2×2) | **High** | Direct sequel to the thinker-vs-reflexer distillation finding; nobody has clean numbers on "who should do the evolving" |
| 3 | Verifiable observability | **High (enabler)** | Without it, #1 and #2 produce scores you cannot explain; build it first as infrastructure |
| 4 | SET-3 + AND-1 as a sim-to-real pair | **Medium-high** | Valuable only framed as a *gap measurement*, not as "another settings bench" |
| 5 | Full-context + compaction mode | **Medium, cheap** | Good early ablation; main risk is cross-task leakage, which is easy to control |
| 6 | Memory mode | **Medium** | Needs a benchmark redesign (task sequences) before it can show anything; do after #1 |
| 7 | Sub-agent efficacy bench | **Defer** | Real open question, but requires multi-step tasks ALFRED doesn't have yet; literature already gives a partial answer (see §7) |
| 8 | BRO-1 (browser) | **Skeptical, defer** | Crowded space, GUI-native domain, drifts from the CLI-agent niche that makes ALFRED distinctive |
| 9 | Adapt external benchmarks / study winning architectures | **Ongoing practice** | Not a project, a habit; fold into every phase |
| 10 | Cloud hosting for local models | **Do now (hygiene)** | Hardware preservation + reproducibility; small infra task |

Sequencing that follows from this: **3 → 5 → 1 → 2 → 4 → 6 → 7**, with 9 and 10
running continuously.

---

## 1. New environments: SET-3 and AND-1

### The idea (David)
- SET-3: a 1:1 copy of the current system-settings mock environment, but the
  agent has **total control** over it.
- AND-1: total **adb** control of a real/emulated Android device.
- Motivation: settings is only ~1–5 % of agentic tasks — essential but narrow.
- Existing work (Qwen-AgentWorld, OSWorld, Google's Android benchmarks) is
  computer-use / screenshot based; we want **CLI-native** benchmarks, partly to
  learn benchmark construction itself.

### Analysis
The scientific value is not SET-3 alone — a third settings mock has diminishing
returns after SET-1 (clean) and SET-2 (realistic). The value appears when SET-3
and AND-1 are designed as a **matched pair measuring the sim-to-real gap**:

- SET-3 = the *simulator ceiling*: same task set, same oracle semantics, but
  the environment is fully controllable, resettable, deterministic.
- AND-1 = the *real substrate*: identical task intents executed through
  `adb shell settings put/get`, `cmd`, `am`, `pm` on an emulator.
- The headline metric is **Δ(SET-3, AND-1) per task**: which distilled patterns
  survive contact with the real device, and which fail on real-world mess
  (permission walls, vendor quirks, asynchronous settling, side effects).

This is the same move SET-1→SET-2 made ("scale buys discovery, not
convention"), one level up: **distillation quality vs. environment fidelity.**
That framing turns "another benchmark" into a finding.

The CLI-native angle is legitimately underexplored. AndroidWorld (Rawles et
al., arXiv 2405.14573) drives the UI through screenshots/accessibility trees;
OSWorld (arXiv 2404.07972) is desktop GUI. An adb-shell action space —
text-only, no vision, verifiable via `settings get` — is exactly the
low-resource regime ALFRED argues for, and almost nobody benchmarks it
directly. Terminal-Bench is the closest relative in spirit (CLI, verifiable),
worth studying for task-format conventions.

### Design requirements (non-negotiable)
1. **Reset discipline.** AND-1 must run against an emulator with snapshot
   restore between tasks (`avdmanager` + `adb emu avd snapshot load`). A real
   phone accumulates state and kills reproducibility.
2. **Oracle stays out-of-band.** Score by reading device state via a separate
   adb channel after the episode, never by trusting agent output. Same
   principle as SET-2's oracle.py.
3. **Task intents shared across SET-3/AND-1** so the gap is attributable to
   the environment, not to task drift.
4. Frozen-pattern rule carries over: patterns distilled before the run, never
   edited after seeing failures.

### Open question to resolve before building
Is SET-3 needed at all, or can SET-2 serve as the simulator arm of the pair?
If SET-2's API surface already matches what adb exposes, SET-3 is redundant
and the pair is SET-2 ↔ AND-1. Audit this before writing any code.

---

## 2. Thinker mode: Memory (self-curated fact store)

### The idea (David)
Agent decides which facts to save (Claude-Code-memory style), a self-evolve
loop over its own memory.

### Analysis
Memory only pays rent when **later tasks depend on things learned in earlier
tasks**. The current benchmarks are i.i.d. single tasks — on those, a memory
mode measures nothing except the overhead of writing memories. So this idea is
gated on a benchmark redesign:

- Build **task sequences** (episodes of 5–15 tasks) with deliberate cross-task
  dependencies: task 3 needs the Wi-Fi SSID discovered in task 1; task 7
  repeats a task family from task 2 with a twist; a user preference stated
  early must be honored late.
- Metrics: (a) accuracy on dependent tasks with/without memory, (b) **memory
  precision** — fraction of saved facts ever re-used, (c) **memory recall** —
  fraction of needed facts actually saved, (d) token cost of the memory
  channel.

Prior art to read before designing: MemGPT/Letta (arXiv 2310.08560) for the
memory-hierarchy mechanics, Mem0 (arXiv 2504.19413) for extraction-based
memory, LoCoMo (arXiv 2402.17753) for how long-horizon memory benchmarks are
constructed, and A-Mem (arXiv 2502.12110) for agentic memory organization.
The interesting *small-model* question none of them answer: does a 2B model
have enough judgment to decide what is worth remembering, or does memory
curation need the teacher? (That folds this idea into §5's 2×2.)

---

## 3. Thinker mode: Memento-Skills (self-editing skills) — the crown jewel

### The idea (David)
Agent can update its own skills. Track *which* skill it updated, *how* (what
was added, what was deleted), and whether the edit had real effect: after the
benchmark ends, **rerun the agent and compare against baseline** to see if the
self-updates actually gained performance.

### Analysis
This is the strongest idea in the set, for three reasons:

1. The self-improving-agent literature (Voyager, arXiv 2305.16291; Reflexion,
   arXiv 2303.11366; Darwin Gödel Machine, arXiv 2505.22954; SICA) reports
   *end scores* but almost never does **counterfactual attribution** — "this
   specific diff caused this specific gain." Diff-level tracking + controlled
   rerun is a real methodological contribution.
2. It inherits the thesis's discipline: the frozen-pattern rule becomes the
   *baseline arm* of a controlled experiment instead of a limitation.
3. It is cheap. No training, no GPUs — it is benchmark engineering plus
   version control over skill files.

### The one pitfall that can invalidate everything: evolution-set leakage
If the agent edits skills after failing benchmark tasks and is then rerun **on
the same tasks**, the skills have been fit to the test set — the same gold
leakage the frozen-pattern rule exists to prevent. The design must split:

- **Evolution split (E):** agent runs, fails, edits skills freely.
- **Held-out split (H):** never seen during evolution. The *only* split that
  proves generalization.
- Report both: gain on E (memorization + generalization) vs. gain on H
  (generalization only). The E−H gap is itself a finding — "how much of
  self-improvement is test-set memorization" would be a genuinely novel
  number.

### Instrumentation spec
- Every skill edit lands as a git commit in an isolated skills workspace:
  diff, timestamp, triggering task id, agent's stated rationale.
- After the run: per-edit ablation where feasible (revert one edit, rerun H)
  — expensive, so sample the largest diffs.
- Classify edits: addition / deletion / parameter tweak / new-skill creation.
  Hypothesis worth testing: small models mostly *append* (bloat), strong
  teachers *prune*. Deletion rate may be a capability signal.

---

## 4. Thinker mode: persistent context + auto-compaction

### The idea (David)
Instead of flushing context every task, let the agent keep its full context
across tasks; at 90 % capacity it auto-compacts. Compare against
flush-per-task.

### Analysis
Cheap, well-posed ablation — do it early. Three arms, not two:

1. **Flush** per task (current baseline).
2. **Persist + compact** at 90 %.
3. **Persist, no compaction** (run until overflow) — needed to separate "carry
   context helps" from "compaction hurts/helps."

Expected physics, to be confirmed: context *rot* (long-context degradation is
well documented — models attend worse mid-context as length grows) will fight
context *transfer* (earlier tasks teach environment conventions). For a 2B
model the rot likely wins early; the crossover point vs. model size is the
interesting curve.

**Leakage warning, same shape as §3:** if tasks in a run share answers or
overlapping state, persistent context is an information channel between
test items. Either randomize task order per seed and report variance, or
verify tasks are mutually uninformative. Otherwise arm 2 gets credit for
peeking, not for memory.

Also measure: tokens per task (compaction has a cost), latency, and *where*
failures happen in the sequence (position-dependent accuracy curve — early vs.
late tasks — is the signature of rot).

---

## 5. Self-Evolution Loop: self-taught vs. teacher-taught

### The idea (David)
Compare the evolution loop run by the model itself vs. by a stronger teacher
(e.g., Opus 4.8 evolving qwen3.6-35b's — or the 2B's — skills/memory/patterns).
Measure which returns higher results, which is faster, what each loop actually
updated, token efficiency, cost efficiency. Also decide *what* is given freedom
to evolve.

### Analysis
This is the natural sequel to the thesis's central result (2B + distilled
pattern ≈ 35B thinker; teacher quality propagates). The thesis showed
*offline* distillation works; this asks whether **online/continual
distillation** works and who should drive it. Frame as a 2×2 (or 2×3):

|  | evolves: skills | evolves: memory | evolves: patterns |
|---|---|---|---|
| **self (same model)** | §3 | §2 | ⚠ see below |
| **teacher (Opus-class)** | teacher-guided skill edits | teacher-curated memory | online distillation |

- **Prediction to test:** teacher-evolution wins on quality but the gap
  *narrows with what is being evolved* — memory curation needs less capability
  than skill rewriting. If a 2B can self-curate memory but not self-edit
  skills, that is a capability-threshold finding exactly like the 0.8B→2B
  vocabulary-compliance threshold.
- **Cost axis matters as much as accuracy:** report gain-per-dollar and
  gain-per-token for each cell. Teacher loops cost API money; self loops cost
  local compute. The practical question for tiny-device ALFRED is whether a
  *periodic* teacher pass (nightly, weekly) beats *continuous* self-evolution.
- ⚠ **Patterns are a special case.** Distilled pattern JSONs are frozen by
  project law. If evolution is allowed to touch patterns, it must happen in a
  clearly separated experimental arm with its own directory and the same E/H
  split as §3, never mutating the thesis artifacts. Recommend keeping patterns
  frozen in v1 of this experiment and evolving only skills + memory.

Prior art: Reflexion (self-feedback), Darwin Gödel Machine (self-modification
with archive), and the distillation literature; but the *self-vs-teacher
controlled comparison at matched budgets* is, to my knowledge, not cleanly
published. This plus §3 is a workshop paper.

---

## 6. Verifiable Observability: explaining *why* a score moved

### The idea (David)
When a model scores higher, understand what it did differently: did it win
because it *knew more* (parameter count) or because it *explored more with
tools* and tried different ways?

### Analysis
Right instinct, and it should be built **first**, because §3 and §5 are
uninterpretable without it. Concretely, this is trace instrumentation plus a
small set of behavioral metrics computed per episode:

- **Knowledge-vs-exploration decomposition.** For each task, record: number of
  tool calls before first correct action; unique environment states visited;
  read-verify actions (e.g., `settings get` before `put`) vs. blind writes;
  retries after errors. A model that wins by knowledge has short traces and
  few probes; a model that wins by exploration has longer traces with
  verification loops.
- **The clean causal test is an ablation, not a metric:** run the same model
  (a) tools-enabled and (b) forced to answer/act in one shot with no
  intermediate reads. The (b) score isolates parametric knowledge; (a)−(b)
  isolates the value of exploration. Compare that decomposition across model
  sizes — this directly answers "did 35B win on knowledge or on search?"
- **Progress rate, not just pass/fail.** AgentBoard (arXiv 2401.13178)
  introduced per-step progress metrics precisely because binary success hides
  *where* agents diverge. The SET oracles can be extended to score partial
  state (right screen, wrong value = 0.5) without touching the pass/fail
  headline number.
- Store every trace as structured JSONL (task id, step, tool, args, env
  observation, tokens, latency). Traces are the raw material for every other
  section — and for the learned-router training data later.

This is also the section with the highest career leverage per hour: "built
instrumented agent benchmarks with causal ablations" is the exact shape of
evals work at the labs you target.

---

## 7. Sub-agent efficacy benchmark (deferred, but keep the question)

### The idea (David)
Does delegating to a sub-agent (separate context) actually improve
performance vs. doing everything in the main agent? In which tasks does it
help, in which not (e.g., dedicated search agent vs. search in main agent)?

### Analysis
Genuine open question with partial answers in the literature:

- Anthropic's multi-agent research write-up reported large gains (~90 % on
  their internal research eval) from orchestrator + parallel subagents, **but
  at ~15× token cost**, and only on parallelizable, read-heavy tasks.
- "Why Do Multi-Agent LLM Systems Fail?" (MAST, arXiv 2503.13657) catalogs the
  failure modes: inter-agent misalignment, lost context at handoff,
  verification gaps. Coding tasks with shared mutable state are where
  delegation hurts.
- Emerging consensus: sub-agents pay off when the subtask is (a) context-heavy
  to *perform* but cheap to *summarize*, and (b) independent of the main
  thread's mutable state. Search is the canonical yes; sequential
  state-mutation (most ALFRED tasks today) is the canonical no.

Your instinct to defer is correct: current SET tasks are too short for
delegation to matter. Revisit once AND-1 or task-sequence episodes (§2) exist
— e.g., "research the right adb incantation" as a delegable subtask. When
built, the metrics are: accuracy Δ, end-to-end latency, total tokens
(including the sub-agent), and handoff-failure rate (MAST taxonomy).

---

## 8. BRO-1 browser benchmark — skeptic's note

CLI-driven browser control (playwright/CDP text interface, accessibility-tree
snapshots) exists, but the space is crowded (WebArena, arXiv 2307.13854;
Mind2Web; BrowserGym unifies most of them) and browsers are GUI-native — a
CLI framing fights the domain instead of exploiting it, and the sites
themselves are nondeterministic. The learning-to-build-benchmarks goal is
better served by AND-1, where the CLI action space is *natural* (adb is
already text) and the niche is actually empty. Recommendation: park BRO-1; if
web capability is ever needed, adopt BrowserGym rather than building.

---

## 9. Continuous practices (not projects)

- **Benchmark archaeology.** For every external benchmark touched
  (Qwen-AgentWorld/AgentWorldBench, AndroidWorld, Terminal-Bench, τ-bench
  arXiv 2406.12045): read the raw task files, classify task types, note what
  their oracle actually checks vs. claims to check, and port the good task
  *shapes* (not the tasks) into SET/AND formats — saved as atoms, then
  composed into patterns, matching the existing atoms→composites pipeline.
  Remember the Ornith lesson: SWE-Bench had ~20 % mislabeled resolutions and
  >30 % leakage — always audit the oracle before trusting the leaderboard.
- **Architecture study.** For each benchmark, also study the *winning agent*:
  what scaffold, what action space, what verification loop. Keep a running
  `docs/architecture_notes.md` — one page per architecture, focused on which
  single design choice carried the win.
- **Baseline extension.** Every new mode (§2–§5) gets run against the same
  frozen model set so the whole grid stays comparable over time.

---

## 10. Infrastructure: move local models to cloud

Motivation: local hardware wear (sustained inference is killing the machine).

- Recommended shape: rented GPU (RunPod / Vast.ai / Lambda) running **vLLM**
  with pinned model revisions, temperature 0, and pinned vLLM version —
  benchmark runs must stay reproducible, and serverless endpoints that
  hot-swap engine versions silently are a reproducibility hazard.
- Keep the *interface* identical (OpenAI-compatible endpoint) so `run.ts`
  needs only a base-URL change; record the endpoint config (model hash, engine
  version, sampling params) in every report JSON.
- Cost sanity: a 35B in 4-bit fits a single 48 GB card (~$0.30–0.70/hr
  spot-ish rates); the 2B can stay local or ride along. Batch benchmark runs;
  don't keep the instance warm.
- Privacy rule carries over: no personal data (`~/.alfred` contents) is ever
  sent to a rented box; benchmarks use mock environments only, which already
  satisfies this.

---

## 11. What this agenda produces (12-month horizon)

1. **Infrastructure:** trace instrumentation (§6), cloud runner (§10) — weeks.
2. **First finding:** context persistence ablation (§4) — cheap, publishable
   as a blog post.
3. **Core contribution:** Memento-Skills counterfactual benchmark (§3) with
   E/H splits and diff-level attribution — workshop-paper sized.
4. **Second contribution:** self-vs-teacher evolution 2×2 (§5) — extends the
   thesis's distillation result into the online setting; strongest paper.
5. **Environment contribution:** SET/AND sim-to-real pair (§1) — the reusable
   asset that makes others cite the repo.
6. Memory episodes (§2) and sub-agent bench (§7) slot in after 3–5 exist.

Everything above keeps the model frozen (no training) until Track B of the
learning roadmap — this agenda and the ML learning roadmap are deliberately
the same project seen from two sides: the benchmarks built here become the
reward signals and datasets used there.
