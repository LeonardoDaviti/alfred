"""Shared runtime types. Every other alfred.runtime module imports from here.

The Pattern dataclass is the in-memory projection of a single pattern from
~/.alfred/patterns/<skill>.json. The raw dict is preserved on `.raw` so the
distiller's authoritative structure is never lost.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Pattern:
    id: str
    version: int
    status: str                           # "active" | "draft"
    domain: str                           # from signature.domain
    required_slots: list[str]             # from signature.required_slots
    slots: list[dict]                     # raw slot defs: {name,type,required,description,default?}
    trigger_regex: str                    # first trigger's regex value
    steps: list[dict]                     # raw step defs: {tool,args_template,retries,timeout,on_failure}
    validators: list[dict]                # [{assert: "..."}]
    raw: dict = field(repr=False)         # full pattern dict for debugging / future fields

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        sig = d.get("signature", {}) or {}
        triggers = d.get("triggers", []) or []
        if not triggers:
            raise ValueError(f"pattern {d.get('id')!r} has no triggers")
        return cls(
            id=d["id"],
            version=int(d.get("version", 1)),
            status=d.get("status", "draft"),
            domain=sig.get("domain", ""),
            required_slots=list(sig.get("required_slots", [])),
            slots=list(d.get("slots", [])),
            trigger_regex=triggers[0]["value"],
            steps=list(d.get("steps", [])),
            validators=list(d.get("validators", [])),
            raw=d,
        )


@dataclass
class CompositeAtomRef:
    """One step inside a composite — references an atomic pattern plus
    slot bindings (literal/composite-slot/runtime-var/step-output) and
    an optional skip_if predicate over previous step outputs."""
    pattern_id: str
    slot_bindings: dict[str, Any]             # name -> binding expression (str | int | bool | None)
    skip_if: str | None = None                # e.g. "step[0].count == 0"

    @classmethod
    def from_dict(cls, d: dict) -> "CompositeAtomRef":
        return cls(
            pattern_id=d["pattern_id"],
            slot_bindings=dict(d.get("slot_bindings", {})),
            skip_if=d.get("skip_if"),
        )


@dataclass
class CompositePattern:
    """A composite executes a sequence of atomic patterns deterministically.
    Optionally extracts user-supplied slots once at entry (composite_slots);
    individual atoms then consume those slots, runtime variables (TODAY, etc.),
    or outputs of prior steps via slot_bindings expressions."""
    id: str
    version: int
    status: str                               # "active" | "draft"
    trigger_regex: str
    composite_slots: list[dict]               # [{name, type, description, default?}]
    atoms: list[CompositeAtomRef]
    output_template: str = ""
    parse_schema: dict[str, str] = field(default_factory=dict)
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "CompositePattern":
        sig = d.get("signature", {}) or {}
        triggers = d.get("triggers", []) or []
        if not triggers:
            raise ValueError(f"composite {d.get('id')!r} has no triggers")
        atoms_raw = d.get("atoms", []) or []
        if not atoms_raw:
            raise ValueError(f"composite {d.get('id')!r} has no atoms")
        return cls(
            id=d["id"],
            version=int(d.get("version", 1)),
            status=d.get("status", "draft"),
            trigger_regex=triggers[0]["value"],
            composite_slots=list(sig.get("composite_slots", [])),
            atoms=[CompositeAtomRef.from_dict(a) for a in atoms_raw],
            output_template=d.get("output_template", ""),
            parse_schema=dict(d.get("parse_schema", {})),
            raw=d,
        )


@dataclass
class CompositeStepResult:
    atom_id: str
    skipped: bool = False
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    parsed: dict = field(default_factory=dict)


@dataclass
class CompositeResult:
    status: Literal["success", "failure", "error"]
    pattern_id: str
    output: str = ""                          # rendered output_template
    steps: list[CompositeStepResult] = field(default_factory=list)
    reason: str = ""
    latency_ms: int = 0

    @classmethod
    def error(cls, pattern_id: str, reason: str) -> "CompositeResult":
        return cls(status="error", pattern_id=pattern_id, reason=reason)


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class RoutingDecision:
    route: Literal["reflexer", "thinker"]
    pattern_id: str | None = None
    confidence: float = 0.0
    reason: str = ""
    candidates_considered: int = 0
    # v2 — margin gating
    margin: float = 0.0                       # top1 - top2 (0 if only 1 candidate)
    ambiguous_between: list[str] = field(default_factory=list)  # [pid_a, pid_b] when margin < threshold
    arbiter_candidates: list[str] = field(default_factory=list)  # tail-arbiter top-k ids (reason="tail_arbiter")


@dataclass
class ReflexerResult:
    status: Literal["success", "failure", "escalated"]
    output: str = ""
    reason: str = ""
    command_generated: str = ""           # bash command the small LLM produced
    steps_executed: int = 0
    total_latency_ms: int = 0
    llm_latency_ms: int = 0


@dataclass
class DispatchResult:
    status: str                           # "success" | "failure" | "escalated" | "error"
    route_taken: str                      # "thinker" | "reflexer" | "escalated_after_reflexer" | "escalated_no_match" | "error_no_match"
    pattern_id: str | None
    output: str
    latency_ms: int
    reason: str = ""
    command_generated: str = ""
    llm_latency_ms: int = 0


@dataclass
class AlfredConfig:
    # full_loop = mixed + distillability triage: thinker fallbacks are
    # classified (pattern candidate vs too complex) and pattern failures are
    # recorded, feeding the future Loom mining pipeline via candidates_log.
    mode: Literal["thinker_only", "reflexer_only", "mixed", "full_loop"] = "mixed"
    confidence_threshold: float = 0.55
    reflexer_only_on_miss: Literal["escalate", "error"] = "escalate"
    llm_base_url: str = "http://127.0.0.1:8003/v1"
    llm_model: str = "ministral-3-3b"
    llm_timeout_s: int = 8
    thinker_command: list[str] = field(default_factory=lambda: ["pi", "--mode", "rpc", "--no-session"])
    thinker_timeout_s: int = 120
    executions_log: str = "./data/executions.jsonl"
    patterns_dir: str = "./data/patterns"
    stats_file: str = "./data/stats/stats.json"
    # v2 router upgrades — all config-gated for A/B testing
    laplace_smoothing: bool = True              # M5 fix: (s+1)/(n+2) instead of s/n
    position_weighted: bool = False             # A/B variant: bonus when trigger matches early
    position_window_chars: int = 50             # first-N chars considered "early"
    position_bonus: float = 0.15                # bonus added to score when early-match fires
    margin_gating: bool = False                 # hour-8 backstop for sibling collisions
    margin_threshold: float = 0.05              # if top1 - top2 < this, ask reflexer to choose
    # v3 router upgrades (Stage-1 core, 2026-06) — all config-gated for ablation
    score_v3: bool = False                      # new formula: semantic + wilson + regex bonus (drops recency/specificity)
    wilson_z: float = 1.96                      # z for Wilson lower bound on success rate
    embedding_routing: bool = False             # add cosine(query, pattern exemplars) term to score
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_cache: str = "./data/cache/embeddings.json"
    semantic_weight: float = 0.5                # weights for score_v3 (renormalized if embedder absent)
    wilson_weight: float = 0.35
    regex_bonus_weight: float = 0.15
    success_prior_strength: float = 3.0         # shrink wilson toward 0.8 prior for small n (0 = raw wilson)
    semantic_rescue: bool = False               # V4 cascade: embedding NN on regex-miss tail (needs embedding_routing)
    semantic_rescue_tau: float = 0.45           # min cosine to rescue; below -> thinker (calibrated 2026-06-12)
    tail_arbiter: bool = False                  # on regex-miss tail, LLM picks among embedding top-k or NONE->thinker (needs semantic_rescue)
    tail_arbiter_k: int = 5                     # embedding candidates shown to the arbiter (R@5=91%; contrastive prompt handles 5 well)
    reflexer_disambiguation: bool = False       # on ambiguous_pair, Reflexer chooses between top-2
    exploration_epsilon: float = 0.0            # P(shadow-route a below-threshold pattern) — starvation recovery
    # caching layers (Stage-1 core, 2026-06)
    command_cache: bool = False                 # (pattern_id, normalized msg) -> command; skips Reflexer LLM
    response_cache: bool = False                # (pattern_id, command) -> output; TTL + write-invalidation
    cache_db: str = "./data/cache/cache.sqlite"
    # pattern lifecycle (Stage-1 core wave 2, 2026-06) — shadow/quarantine overlay
    lifecycle_enabled: bool = False             # state machine: shadow -> active -> quarantined (stats-sidecar overlay)
    shadow_promote_n: int = 5                   # shadow uses before promotion decision
    shadow_promote_min_success: int = 4         # successes (of shadow_promote_n) required to promote
    quarantine_wilson_threshold: float = 0.4    # active pattern demoted when wilson_lower < this
    skill_hash_check: bool = False              # verify metadata.skill_sha256 against resolved CLI file at load
    # full-loop triage + standalone runner (Stage-1 UX, 2026-06)
    candidates_log: str = "./data/candidates.jsonl"   # distillation candidates + pattern failures (raw queries, local-only)
    runner_log: str = "./data/runner_log.jsonl"       # REPL ground-truth log: query -> pattern -> command -> outcome


class LLMError(Exception):
    """LLM call failed (non-2xx, malformed JSON, etc.)."""
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"llm_error: {kind} {detail}".strip())
        self.kind = kind
        self.detail = detail


class LLMTimeout(LLMError):
    def __init__(self, detail: str = ""):
        super().__init__("timeout", detail)
