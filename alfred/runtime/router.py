"""Router — thin regex+score pattern picker.

The Router does NOT extract slots. It only returns a pattern_id (or routes
to the Thinker). Slot extraction is the Reflexer's job.

Per spec section 8. v3 scoring (semantic + Wilson + regex bonus) per the
Stage-1 core spec (2026-06-12), Workstream C — all config-gated, legacy
path byte-identical when flags are off.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .types import AlfredConfig, Pattern, RoutingDecision

if TYPE_CHECKING:
    from .embedder import EmbeddingBackend
    from .store import PatternStore


def wilson_lower(s: int, n: int, z: float = 1.96) -> float:
    """Wilson score interval lower bound on a success rate.

    Penalizes thin evidence: (4/5) bounds lower than (80/100) at the same
    observed rate. n=0 returns the 0.8 cold-start prior so brand-new
    patterns keep the current cold-start routing semantics."""
    if n <= 0:
        return 0.8
    p_hat = s / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p_hat + z2 / (2.0 * n)
    margin = z * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    return max(0.0, (center - margin) / denom)


class Router:
    def __init__(
        self,
        store: "PatternStore",
        config: AlfredConfig,
        embedder: "EmbeddingBackend | None" = None,
        rng: Callable[[], float] | None = None,
    ):
        self.store = store
        self.config = config
        # v3 — injected for tests; lazily constructed in production.
        self._embedder = embedder
        self._embedder_failed = False           # remember a failed lazy init
        self._pattern_index: dict[str, list[float]] | None = None
        self._rng: Callable[[], float] = rng if rng is not None else random.random

    def route(self, message: str) -> RoutingDecision:
        # STAGE 1 — regex pre-filter
        candidates: list[Pattern] = [
            p for p in self.store.active_patterns()
            if self.store.compiled_triggers[p.id].search(message)
        ]
        if not candidates:
            # Lifecycle wave 2 (spec item 5): when NO active candidate
            # matched, exploration may rescue a quarantined pattern so its
            # stats can update and it can re-enter shadow. Gated by BOTH
            # lifecycle_enabled and exploration_epsilon > 0; rng injected.
            epsilon = float(getattr(self.config, "exploration_epsilon", 0.0))
            if (
                getattr(self.config, "lifecycle_enabled", False)
                and epsilon > 0.0
                and self._rng() < epsilon
            ):
                for q in self.store.quarantined_patterns():
                    compiled = self.store.compiled_triggers.get(q.id)
                    if compiled is not None and compiled.search(message):
                        return RoutingDecision(
                            route="reflexer",
                            pattern_id=q.id,
                            confidence=0.0,
                            reason="exploration_quarantined",
                            candidates_considered=0,
                        )
            # Semantic rescue (V4 cascade, measured 2026-06-12): when regex
            # finds NOTHING, embedding nearest-neighbor may recover the query
            # — at tau=0.45 this rescued recall blindspots with zero newly-
            # wrong routes and thinker recall preserved on the 75-query matrix.
            if getattr(self.config, "semantic_rescue", False):
                rescue = self._semantic_rescue(message)
                if rescue is not None:
                    return rescue
            return RoutingDecision(route="thinker", reason="no_pattern_match")

        # STAGE 2 — score (message-aware for position-weighted variant)
        qvec = None
        index = None
        if getattr(self.config, "score_v3", False):
            # v3: embed the query ONCE per route() call, not per pattern.
            qvec, index = self._semantic_context(message)
            scored = sorted(
                ((p, self._score_v3(p, qvec, index)) for p in candidates),
                key=lambda x: -x[1],
            )
        else:
            scored = sorted(
                ((p, self._score(p, message)) for p in candidates),
                key=lambda x: -x[1],
            )
        best, best_score = scored[0]
        # Margin = top1 - top2 (or 0 if only one candidate)
        margin = (best_score - scored[1][1]) if len(scored) >= 2 else 0.0

        # STAGE 3 — confidence gate
        if best_score < self.config.confidence_threshold:
            # Exploration (starvation recovery): with probability epsilon,
            # route the below-threshold best anyway so its stats can update
            # and the Wilson bound can recover. epsilon=0.0 (default) = off.
            epsilon = float(getattr(self.config, "exploration_epsilon", 0.0))
            if epsilon > 0.0 and self._rng() < epsilon:
                return RoutingDecision(
                    route="reflexer",
                    pattern_id=best.id,
                    confidence=best_score,
                    margin=margin,
                    reason="exploration",
                    candidates_considered=len(candidates),
                )
            return RoutingDecision(
                route="thinker",
                reason="below_confidence_threshold",
                confidence=best_score,
                candidates_considered=len(candidates),
                margin=margin,
            )

        # STAGE 4 — margin gate: when the top regex candidates score close, the
        # gate can't tell them apart. With the tail arbiter on we escalate to the
        # contrastive arbiter over the EMBEDDING top-k (not just the two regex
        # siblings). We deliberately do NOT also trigger on regex/embedding
        # disagreement: measured 2026-06-15 that overrode confident-correct regex
        # routes and regressed the canonical matrix -4.5pp — the small-model
        # arbiter is a safe TIE-BREAKER, not a reliable override.
        close = (
            getattr(self.config, "margin_gating", False)
            and len(scored) >= 2
            and margin < getattr(self.config, "margin_threshold", 0.05)
        )
        if close:
            if (
                getattr(self.config, "tail_arbiter", False)
                and qvec is not None
                and index
            ):
                from .embedder import max_cosine

                k = int(getattr(self.config, "tail_arbiter_k", 5))
                ranked = sorted(
                    ((max_cosine(qvec, v), pid) for pid, v in index.items()),
                    key=lambda x: -x[0],
                )
                cands = [pid for _, pid in ranked[:k]]
                if best.id not in cands:               # keep the regex top-1 in the slate
                    cands = [best.id] + cands[: max(0, k - 1)]
                return RoutingDecision(
                    route="reflexer",
                    pattern_id=best.id,                 # provisional
                    arbiter_candidates=cands,
                    confidence=best_score,
                    margin=margin,
                    reason="margin_arbiter",
                    candidates_considered=len(candidates),
                )
            return RoutingDecision(
                route="reflexer",
                pattern_id=best.id,                     # provisional — may be overridden
                ambiguous_between=[scored[0][0].id, scored[1][0].id],
                confidence=best_score,
                margin=margin,
                reason="ambiguous_pair",
                candidates_considered=len(candidates),
            )

        return RoutingDecision(
            route="reflexer",
            pattern_id=best.id,
            confidence=best_score,
            margin=margin,
            reason="matched_with_confidence",
            candidates_considered=len(candidates),
        )

    def _score(self, p: Pattern, message: str = "") -> float:
        stats = self.store.stats.get(p.id, {})
        n = stats.get("use_count", 0)
        s = stats.get("success_count", 0)
        # M5 — Laplace smoothing for n≥1; preserve old 0.8 cold-start for n=0.
        # Without smoothing: n=1,s=0 → success_rate=0 → score below threshold permanently.
        # With smoothing: n=1,s=0 → 1/3=0.33, recoverable as use_count grows.
        # We keep cold-start = 0.8 (unchanged) so cold patterns still route.
        if getattr(self.config, "laplace_smoothing", True):
            success_rate = 0.8 if n == 0 else (s + 1) / (n + 2)
        else:
            success_rate = 0.8 if n == 0 else s / n
        days_since = self._days_since(stats.get("last_used_at"))
        recency = max(0.0, 1.0 - days_since / 30)
        specificity = min(1.0, len(p.trigger_regex) / 200)
        base = 0.6 * success_rate + 0.2 * recency + 0.2 * specificity
        # A/B variant: position-weighted bonus when the trigger matches in the first N chars
        if getattr(self.config, "position_weighted", False) and message:
            window = message[: int(getattr(self.config, "position_window_chars", 50))]
            compiled = self.store.compiled_triggers.get(p.id)
            if compiled is not None and compiled.search(window):
                base += float(getattr(self.config, "position_bonus", 0.15))
        return base

    # ── v3 scoring (semantic + Wilson + regex bonus) ───────────────────
    #
    # Recency and specificity are deliberately GONE here (EXP2 / QA report
    # Bug 2: recency drives the starvation death-spiral, specificity is a
    # constant per pattern — neither reads the message).

    def _score_v3(
        self,
        p: Pattern,
        qvec: list[float] | None,
        index: dict[str, list[float]] | None,
    ) -> float:
        from .embedder import max_cosine

        stats = self.store.stats.get(p.id, {})
        n = stats.get("use_count", 0)
        s = stats.get("success_count", 0)
        wilson = wilson_lower(s, n, float(getattr(self.config, "wilson_z", 1.96)))
        # Small-n shrinkage toward the 0.8 cold-start prior. Without it the
        # Wilson LB punishes thin evidence below cold-start — measured in the
        # 2026-06-12 ablation: wilson(1,1)=0.207, so one SUCCESS scored worse
        # than never-used and starved young patterns below the gate.
        k = float(getattr(self.config, "success_prior_strength", 3.0))
        if k > 0:
            wilson = (n * wilson + k * 0.8) / (n + k)

        sw = float(getattr(self.config, "semantic_weight", 0.5))
        ww = float(getattr(self.config, "wilson_weight", 0.35))
        rw = float(getattr(self.config, "regex_bonus_weight", 0.15))

        # Regex bonus is 1.0 for every candidate — they all passed the regex
        # prefilter. It exists so the three weights sum to 1.
        pvecs = index.get(p.id) if index else None
        if qvec is not None and pvecs:
            total = sw + ww + rw
            return (sw * max_cosine(qvec, pvecs) + ww * wilson + rw * 1.0) / total
        # Embedder off/unavailable (or pattern has no exemplar text):
        # renormalize the remaining weights to sum to 1.
        total = ww + rw
        if total <= 0.0:
            return wilson
        return (ww * wilson + rw * 1.0) / total

    def _semantic_rescue(self, message: str) -> RoutingDecision | None:
        """V4 recall tail: embedding NN over ALL patterns when regex matched
        nothing. Returns a decision only when best cosine >= tau; never raises
        (any failure degrades to None -> thinker).

        With config.tail_arbiter on, returns the embedding top-k as
        `arbiter_candidates` (reason="tail_arbiter") so the Reflexer can ask
        the LLM to pick one or escape to NONE->thinker — the precision guard
        the bare top-1 rescue lacks (top-1 dragged creative/chitchat queries
        into weather/reminder atoms at tau=0.45, measured 2026-06-15)."""
        try:
            qvec, index = self._semantic_context(message)
            if qvec is None or not index:
                return None
            from .embedder import max_cosine

            ranked = sorted(
                ((max_cosine(qvec, vecs), pid) for pid, vecs in index.items()),
                key=lambda x: -x[0],
            )
            if not ranked:
                return None
            best_sim, best_id = ranked[0]
            tau = float(getattr(self.config, "semantic_rescue_tau", 0.45))
            if best_id is None or best_sim < tau:
                return None

            if getattr(self.config, "tail_arbiter", False):
                k = int(getattr(self.config, "tail_arbiter_k", 3))
                candidates = [pid for _, pid in ranked[:k]]
                return RoutingDecision(
                    route="reflexer",
                    pattern_id=best_id,                 # provisional top-1
                    arbiter_candidates=candidates,
                    confidence=best_sim,
                    reason="tail_arbiter",
                    candidates_considered=len(index),
                )
            return RoutingDecision(
                route="reflexer",
                pattern_id=best_id,
                confidence=best_sim,
                reason="semantic_rescue",
                candidates_considered=len(index),
            )
        except Exception:
            return None

    def _semantic_context(
        self, message: str
    ) -> tuple[list[float] | None, dict[str, list[float]] | None]:
        """(query_vector, pattern_index) — (None, None) when semantic routing
        is off, the backend is unavailable, or encoding fails."""
        backend = self._ensure_embedder()
        if backend is None:
            return None, None
        try:
            if self._pattern_index is None:
                from .embedder import build_pattern_index
                self._pattern_index = build_pattern_index(
                    self.store, backend,
                    cache_path=getattr(self.config, "embedding_cache", None),
                )
            qvec = backend.encode([message])[0]
        except Exception:
            # Semantic scoring must never break routing — degrade to
            # the renormalized wilson+regex score.
            self._embedder_failed = True
            return None, None
        return qvec, self._pattern_index

    def _ensure_embedder(self) -> "EmbeddingBackend | None":
        if not getattr(self.config, "embedding_routing", False):
            return None
        if self._embedder is not None:
            return self._embedder
        if self._embedder_failed:
            return None
        from .embedder import EmbedderUnavailable, SentenceTransformerBackend
        try:
            self._embedder = SentenceTransformerBackend(
                getattr(self.config, "embedding_model",
                        "sentence-transformers/all-MiniLM-L6-v2")
            )
        except EmbedderUnavailable:
            self._embedder_failed = True
            return None
        return self._embedder

    @staticmethod
    def _days_since(iso_str: str | None) -> float:
        if iso_str is None:
            return 30.0
        try:
            s = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            return max(0.0, delta.total_seconds() / 86400.0)
        except (ValueError, TypeError):
            return 30.0
