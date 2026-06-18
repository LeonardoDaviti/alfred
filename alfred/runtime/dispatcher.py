"""Dispatcher — three-mode switch + executions.jsonl observability point.

Per spec section 11.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .router import Router
from .types import AlfredConfig, DispatchResult, ReflexerResult, RoutingDecision

if TYPE_CHECKING:
    from .reflexer import Reflexer
    from .store import PatternStore
    from .thinker_adapter import ThinkerAdapter


class Dispatcher:
    def __init__(
        self,
        router: Router,
        reflexer: "Reflexer",
        thinker: "ThinkerAdapter",
        store: "PatternStore",
        config: AlfredConfig,
    ):
        self.router = router
        self.reflexer = reflexer
        self.thinker = thinker
        self.store = store
        self.config = config

    # ------------------------------------------------------------------ public

    def handle(self, message: str) -> DispatchResult:
        mode = self.config.mode
        t_start = time.time()

        if mode == "thinker_only":
            return self._run_thinker(message, mode, t_start, None, "thinker")

        # Composite precedence: composites scanned before atomic patterns.
        # If any composite trigger matches, run it via the composite executor.
        # Composites apply in both reflexer_only and mixed modes.
        composite = self._match_composite(message)
        if composite is not None:
            return self._run_composite(composite, message, mode, t_start)

        decision = self.router.route(message)

        # Margin-gated disambiguation (v2): when Router flagged top1/top2 as
        # ambiguous, ask the small LLM to choose. ~30-80ms binary decision.
        # Superseded by v3 single-call disambiguation (reflexer_disambiguation):
        # when that flag is on, the decision flows through to Reflexer.execute,
        # which chooses AND generates the command in one LLM call.
        if (
            decision.route == "reflexer"
            and decision.ambiguous_between
            and not getattr(self.config, "reflexer_disambiguation", False)
        ):
            a_id, b_id = decision.ambiguous_between
            a = self.store.patterns.get(a_id)
            b = self.store.patterns.get(b_id)
            if a is not None and b is not None:
                a_intent = (a.raw.get("metadata", {}) or {}).get("natural_language_intent") or a_id
                b_intent = (b.raw.get("metadata", {}) or {}).get("natural_language_intent") or b_id
                try:
                    chosen, disambig_ms = self.reflexer.llm.disambiguate_pair(
                        message, a_id, a_intent, b_id, b_intent
                    )
                except Exception:
                    chosen = a_id
                decision = RoutingDecision(
                    route="reflexer",
                    pattern_id=chosen,
                    confidence=decision.confidence,
                    margin=decision.margin,
                    reason=f"disambiguated_pair({chosen})",
                    candidates_considered=decision.candidates_considered,
                )

        if mode == "reflexer_only":
            if decision.route != "reflexer":
                if self.config.reflexer_only_on_miss == "escalate":
                    return self._run_thinker(
                        message, mode, t_start, None, "escalated_no_match"
                    )
                result = DispatchResult(
                    status="error",
                    route_taken="error_no_match",
                    pattern_id=None,
                    output="",
                    latency_ms=int((time.time() - t_start) * 1000),
                    reason="reflexer_only_no_match",
                )
                self._log(message, mode, "error_no_match", None, result, t_start)
                return result
            return self._run_reflexer_with_escalation(
                message, decision, mode, t_start, escalate_on_failure=False
            )

        # mode == "mixed"
        if decision.route == "thinker":
            return self._run_thinker(message, mode, t_start, None, "thinker")
        return self._run_reflexer_with_escalation(
            message, decision, mode, t_start, escalate_on_failure=True
        )

    # ------------------------------------------------------------------ internals

    def _run_reflexer_with_escalation(
        self, message: str, decision, mode: str, t_start: float,
        escalate_on_failure: bool = True,
    ) -> DispatchResult:
        pattern = self.store.patterns[decision.pattern_id]

        # ── cache fast paths (Stage-1 core) — inert unless a flag is on ──
        # Order: response-cache check → command-cache check → LLM. Both
        # checks need the cached command (the message→command index), so a
        # CommandCache lookup happens whenever either flag is on; skipping
        # the LLM with that command is gated on config.command_cache.
        rr: ReflexerResult | None = None
        # v3 disambiguation pending => the pattern identity is provisional, so
        # cache lookups/stores keyed on it would be wrong. Skip caching there.
        # The pattern identity is provisional whenever an LLM step downstream
        # may change it: v3 disambiguation (ambiguous_between) or the tail
        # arbiter (arbiter_candidates). Caching keyed on the provisional id
        # would be wrong, so skip the fast paths in both cases.
        provisional = bool(
            getattr(self.config, "reflexer_disambiguation", False)
            and getattr(decision, "ambiguous_between", None)
        ) or bool(
            getattr(self.config, "tail_arbiter", False)
            and getattr(decision, "arbiter_candidates", None)
        )
        caching = (
            self.config.command_cache or self.config.response_cache
        ) and not provisional
        if caching:
            cached_command = self._cache_safe(
                lambda c: c[0].lookup(pattern, message), "command lookup")
            if cached_command:
                if self.config.response_cache:
                    cached_stdout = self._cache_safe(
                        lambda c: c[1].lookup(pattern, cached_command),
                        "response lookup")
                    if cached_stdout is not None:
                        result = DispatchResult(
                            status="success",
                            route_taken="reflexer",
                            pattern_id=decision.pattern_id,
                            output=cached_stdout,
                            latency_ms=int((time.time() - t_start) * 1000),
                            reason="response_cache_hit",
                            command_generated=cached_command,
                            llm_latency_ms=0,
                        )
                        result.cache = "response"
                        self._log(message, mode, "reflexer",
                                  decision.pattern_id, result, t_start)
                        return result
                if self.config.command_cache:
                    rr = self._execute_cached_command(pattern, cached_command)
                    if rr is not None and rr.status != "success":
                        # Stale command — drop it so the next request
                        # regenerates via the LLM.
                        self._cache_safe(
                            lambda c: c[0].invalidate(pattern, message),
                            "command invalidate")

        if rr is None:
            # decision is passed through for v3 disambiguation; Reflexer
            # ignores it unless the flag + ambiguous_between are both set.
            rr = self.reflexer.execute(pattern, message, decision=decision)
        if caching and rr.status == "success" and rr.command_generated:
            # Stored only after a successful validated execution; for WRITE
            # patterns this also purges the domain's response entries.
            self._cache_safe(
                lambda c: c[0].store(pattern, message, rr.command_generated),
                "command store")
            if self.config.response_cache:
                self._cache_safe(
                    lambda c: c[1].record_success(
                        pattern, rr.command_generated, rr.output),
                    "response record")

        if rr.status == "escalated" and not escalate_on_failure:
            # reflexer_only mode: do NOT call Thinker. Surface the reflexer's
            # attempt directly so the benchmark can score command_generated.
            result = DispatchResult(
                status="failure",
                route_taken="reflexer",
                pattern_id=decision.pattern_id,
                output=rr.output,
                latency_ms=rr.total_latency_ms or int((time.time() - t_start) * 1000),
                reason=rr.reason,
                command_generated=rr.command_generated,
                llm_latency_ms=rr.llm_latency_ms,
            )
            self._log(message, mode, "reflexer", decision.pattern_id, result, t_start)
            return result

        if rr.status == "escalated":
            # Reflexer gave up → Thinker fallback. One log entry for the
            # whole dispatch (the Thinker call).
            # full_loop: a pattern that escalates is a self-update signal —
            # record it (no LLM needed; the failing pattern is known).
            if self.config.mode == "full_loop":
                self._append_candidate({
                    "kind": "pattern_failure",
                    "query": message,
                    "pattern_id": decision.pattern_id,
                    "failure_reason": rr.reason,
                    "command_attempted": rr.command_generated,
                })
            tr = self.thinker.run(message)
            tr.route_taken = "escalated_after_reflexer"
            tr.pattern_id = decision.pattern_id
            # Carry the reflexer's attempted command through the escalation
            # so the log entry shows what the small LLM tried.
            tr.command_generated = rr.command_generated
            # If thinker also failed, count as full-pipeline pattern failure
            if tr.status != "success":
                try:
                    self.store.record_execution(
                        decision.pattern_id,
                        success=False,
                        failure_reason=rr.reason,
                    )
                except Exception:
                    pass
            self._log(
                message, mode, "escalated_after_reflexer", decision.pattern_id, tr, t_start
            )
            return tr

        # Reflexer returned success or failure (validator failed but no escalate)
        result = DispatchResult(
            status=rr.status,
            route_taken="reflexer",
            pattern_id=decision.pattern_id,
            output=rr.output,
            latency_ms=rr.total_latency_ms or int((time.time() - t_start) * 1000),
            reason=rr.reason,
            command_generated=rr.command_generated,
            llm_latency_ms=rr.llm_latency_ms,
        )
        if rr.reason == "command_cache_hit":
            result.cache = "command"
        self._log(message, mode, "reflexer", decision.pattern_id, result, t_start)
        return result

    # ── caching helpers (Stage-1 core, Workstream B) ──────────────────
    def _get_caches(self):
        """Lazy (CommandCache, ResponseCache) tuple, or None when caching is
        off or the backing store could not be opened."""
        if not (self.config.command_cache or self.config.response_cache):
            return None
        if not hasattr(self, "_caches"):
            try:
                from .cache import CommandCache, ResponseCache
                self._caches = (
                    CommandCache(self.config.cache_db),
                    ResponseCache(self.config.cache_db),
                )
            except Exception as e:
                print(
                    f"alfred: warning — cache init failed, caching disabled: {e}",
                    file=sys.stderr,
                )
                self._caches = None
        return self._caches

    def _cache_safe(self, fn, what: str):
        """Run one cache operation; ANY failure degrades to a miss (None).
        The cache must never break dispatch."""
        caches = self._get_caches()
        if caches is None:
            return None
        try:
            return fn(caches)
        except Exception as e:
            print(f"alfred: warning — cache {what} failed: {e}", file=sys.stderr)
            return None

    def _execute_cached_command(self, pattern, command: str) -> ReflexerResult | None:
        """Execute a command-cache hit, mirroring Reflexer.execute minus the
        LLM step (same timeout/retry/validator/on_failure semantics).

        Returns None when execution can't even be attempted (no steps, no
        bash runner) so the caller falls back to the normal Reflexer path."""
        bash = getattr(self.reflexer, "_bash", None)
        if bash is None or not pattern.steps:
            return None
        import subprocess

        from . import validators

        t_exec = time.perf_counter()
        step = pattern.steps[0]
        timeout = int(step.get("timeout", 10))
        retries = int(step.get("retries", 0))

        def _rr(status: str, reason: str = "", output: str = "") -> ReflexerResult:
            return ReflexerResult(
                status=status,  # type: ignore[arg-type]
                output=output,
                reason=reason,
                command_generated=command,
                steps_executed=0 if status == "escalated" else 1,
                total_latency_ms=int((time.perf_counter() - t_exec) * 1000),
                llm_latency_ms=0,
            )

        try:
            result = bash(command, timeout=timeout)
        except subprocess.TimeoutExpired:
            return _rr("escalated", f"timeout_after_{timeout}s")

        if result.exit_code != 0 and retries > 0:
            try:
                result = bash(command, timeout=timeout)
            except subprocess.TimeoutExpired:
                return _rr("escalated", "exec_error_after_retry")
            if result.exit_code != 0:
                return _rr("escalated", "exec_error_after_retry")
        elif result.exit_code != 0:
            return _rr("escalated", f"exec_error_{result.exit_code}")

        for v in pattern.validators:
            passed, reason = validators.check(v["assert"], result)
            if not passed:
                on_fail = step.get("on_failure", "escalate_to_thinker")
                if on_fail == "escalate_to_thinker":
                    return _rr("escalated", f"validator_failed_{reason}")
                return _rr("failure", f"validator_{reason}")

        self.store.record_execution(pattern.id, success=True)
        return _rr("success", "command_cache_hit", result.stdout)

    def _run_thinker(
        self,
        message: str,
        mode: str,
        t_start: float,
        pattern_id: str | None,
        route: str,
    ) -> DispatchResult:
        tr: DispatchResult = self.thinker.run(message)
        tr.route_taken = route
        tr.pattern_id = pattern_id
        self._log(message, mode, route, pattern_id, tr, t_start)
        # full_loop: no pattern matched — triage whether this query class is
        # distillable into a pattern or too complex. One small LLM call,
        # logged to candidates_log for the (Loom) mining pipeline.
        if mode == "full_loop" and route == "thinker":
            self._classify_distillable(message, tr)
        return tr

    # ── full-loop triage (Stage-1 UX) ─────────────────────────────────

    def _classify_distillable(self, message: str, tr: DispatchResult) -> None:
        """Best-effort: classify a thinker-served query as pattern-distillable
        or not. Never raises; failures are logged as unclassified."""
        chat = getattr(getattr(self.reflexer, "llm", None), "chat", None)
        entry: dict[str, Any] = {
            "kind": "novel_query",
            "query": message,
            "thinker_status": tr.status,
        }
        if chat is None:
            entry["distillable"] = None
            entry["triage_error"] = "no_chat_method"
            self._append_candidate(entry)
            return
        prompt = (
            "You triage user requests for a shell-command automation system.\n"
            "A request is DISTILLABLE when it could be served by ONE parameterized\n"
            "shell command in the future (fixed action, variable arguments — e.g.\n"
            '"run my backup script", "weather in <city>"). It is NOT distillable\n'
            "when it needs reasoning, multi-step planning, creativity, or coding\n"
            "work (e.g. \"refactor this module\", \"write a poem\").\n\n"
            f'Request: "{message}"\n\n'
            "Reply with exactly three lines:\n"
            "DISTILLABLE: yes|no\nDOMAIN: <one word>\nREASON: <one short sentence>"
        )
        try:
            reply, triage_ms = chat(prompt, max_tokens=96)
            entry["triage_ms"] = triage_ms
            for line in reply.splitlines():
                low = line.strip().lower()
                if low.startswith("distillable:"):
                    entry["distillable"] = "yes" in low.split(":", 1)[1]
                elif low.startswith("domain:"):
                    entry["domain"] = line.split(":", 1)[1].strip()
                elif low.startswith("reason:"):
                    entry["reason"] = line.split(":", 1)[1].strip()
            entry.setdefault("distillable", None)
        except Exception as e:
            entry["distillable"] = None
            entry["triage_error"] = f"{type(e).__name__}: {e}"[:200]
        self._append_candidate(entry)

    def _append_candidate(self, entry: dict[str, Any]) -> None:
        """Append one line to candidates_log. Never breaks dispatch."""
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            **entry,
        }
        try:
            path = Path(os.path.expanduser(self.config.candidates_log))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"alfred: warning — failed to append candidates log: {e}",
                  file=sys.stderr)

    # ── composite handling (v2) ───────────────────────────────────────
    def _match_composite(self, message: str):
        """Return the first composite whose trigger matches, or None.

        Composites are matched in file/load order; the §4.4 disjointness
        check ensures no two composites match the same prompt in practice."""
        for c in self.store.active_composites():
            compiled = self.store.composite_triggers.get(c.id)
            if compiled is not None and compiled.search(message):
                return c
        return None

    def _run_composite(self, composite, message: str, mode: str, t_start: float) -> DispatchResult:
        """Execute a composite via CompositeExecutor and adapt to DispatchResult."""
        # Lazy import to avoid circulars
        from .composite_executor import CompositeExecutor, LocalBashExecutor
        if not hasattr(self, "_composite_executor"):
            self._composite_executor = CompositeExecutor(
                store=self.store,
                llm_client=getattr(self.reflexer, "llm", None) or getattr(self.reflexer, "_llm", None),
                # Flight scans (fli) can take >30s; raise the per-atom bash timeout.
                bash_executor=LocalBashExecutor(timeout_s=120),
            )
        cr = self._composite_executor.execute(composite, message)
        result = DispatchResult(
            status=cr.status,
            route_taken="composite",
            pattern_id=composite.id,
            output=cr.output,
            latency_ms=cr.latency_ms,
            reason=cr.reason,
            command_generated="; ".join(s.command for s in cr.steps if not s.skipped),
            llm_latency_ms=0,  # composite extracts slots once but doesn't surface that separately yet
        )
        self._log(message, mode, "composite", composite.id, result, t_start)
        return result

    # ------------------------------------------------------------------ logging

    def _log(
        self,
        message: str,
        mode: str,
        route: str,
        pattern_id: str | None,
        result: DispatchResult | ReflexerResult,
        t_start: float,
    ) -> None:
        latency_ms = int((time.time() - t_start) * 1000)
        msg_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        entry: dict[str, Any] = {
            "ts": ts,
            "mode": mode,
            "route": route,
            "pattern_id": pattern_id,
            "message_hash": msg_hash,
            "result_status": getattr(result, "status", ""),
            "latency_ms": latency_ms,
            "reason": getattr(result, "reason", "") or "",
        }

        if route in ("reflexer", "escalated_after_reflexer"):
            entry["command_generated"] = getattr(result, "command_generated", "") or ""
            entry["llm_latency_ms"] = int(getattr(result, "llm_latency_ms", 0) or 0)
            # Stage-1 telemetry: which cache layer served this dispatch
            # ("command" | "response" | None) — feeds the thesis eval chapter.
            # Key only present when caching is enabled, so legacy-config log
            # lines stay byte-identical.
            if self.config.command_cache or self.config.response_cache:
                entry["cache"] = getattr(result, "cache", None)

        path = Path(os.path.expanduser(self.config.executions_log))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as e:
            print(
                f"alfred: warning — failed to append executions log {path}: {e}",
                file=sys.stderr,
            )
