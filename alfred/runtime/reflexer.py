"""Reflexer: small-LLM command generation -> bash -> validate.

The LLM produces a full shell command directly. On any failure the Reflexer
returns a ReflexerResult with status="escalated" carrying a tagged reason;
the dispatcher decides whether to fall back to the Thinker.

Disambiguation mode (v3, config.reflexer_disambiguation): when the Router's
RoutingDecision carries `ambiguous_between=[top1, top2]`, a single LLM call
presents BOTH patterns and asks for `PATTERN: <id>` on the first line, then
the command. Parse failure falls back to the provisional top-1.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from . import validators
from .llm_client import _build_command_shape, _strip_command


def _error_tail(result, limit: int = 600) -> str:
    """Diagnostic tail of a failed execution: prefer stderr, fall back to
    stdout, truncated from the left (the end usually has the actual error)."""
    text = (result.stderr or "").strip() or (result.stdout or "").strip()
    if len(text) > limit:
        text = "..." + text[-limit:]
    return text
from .types import (
    AlfredConfig,
    ExecutionResult,
    LLMError,
    LLMTimeout,
    Pattern,
    ReflexerResult,
    RoutingDecision,
)

if TYPE_CHECKING:
    from .llm_client import LLMClient
    from .store import PatternStore


_PATTERN_LINE_RE = re.compile(r"^\s*PATTERN:\s*[`\"']?([\w\-.]+)[`\"']?\s*$",
                              re.IGNORECASE)

_DISAMBIGUATION_TEMPLATE = (
    "Two patterns matched this query. Decide which ONE fits, then output its "
    "command.\n"
    "\n"
    "A) id: {a_id}\n"
    "   intent: {a_intent}\n"
    "   shape: {a_shape}\n"
    "\n"
    "B) id: {b_id}\n"
    "   intent: {b_intent}\n"
    "   shape: {b_shape}\n"
    "\n"
    "User query: \"{query}\"\n"
    "\n"
    "Output exactly two lines:\n"
    "PATTERN: <id>\n"
    "<the command>"
)


def _pattern_intent(p: Pattern) -> str:
    return ((p.raw.get("metadata") or {}).get("natural_language_intent") or p.id)


def _pattern_shape(p: Pattern) -> str:
    args_template = str(p.steps[0].get("args_template", "")) if p.steps else ""
    return _build_command_shape(args_template, p.slots) or "(unknown)"


def build_disambiguation_prompt(query: str, a: Pattern, b: Pattern) -> str:
    """Prompt presenting both candidates; kept short — the model is 3B."""
    return _DISAMBIGUATION_TEMPLATE.format(
        a_id=a.id, a_intent=_pattern_intent(a), a_shape=_pattern_shape(a),
        b_id=b.id, b_intent=_pattern_intent(b), b_shape=_pattern_shape(b),
        query=query,
    )


def parse_disambiguation_reply(
    text: str, valid_ids: set[str]
) -> tuple[str | None, str]:
    """Returns (chosen_pattern_id | None, command_text).

    chosen is None when the first non-empty line is not a valid
    `PATTERN: <known id>` line — the caller falls back to the
    provisional top-1 in that case."""
    lines = (text or "").splitlines()
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return None, ""
    m = _PATTERN_LINE_RE.match(lines[idx])
    if not m or m.group(1) not in valid_ids:
        return None, ""
    command = _strip_command("\n".join(lines[idx + 1:]))
    return m.group(1), command


# ── tail arbiter (regex-miss tail; embedding top-k + NONE escape) ──────────
# Mirrors the eval-proven prompt (alfred/eval/persona_eval.py): present the
# embedding top-k as A/B/C..., add a NONE option, ask for ONE letter. The NONE
# escape is what protects Thinker recall — the bare top-1 rescue has no way to
# say "none of these fit" and so dragged creative/chitchat queries into atoms.

_ARBITER_LETTERS = "ABCDEFGH"


def _arbiter_shape(p: Pattern) -> str:
    """Command shape for the arbiter — the subcommand IS the action signal.
    Composite-safe (composites have no .steps)."""
    if getattr(p, "steps", None):
        return _pattern_shape(p)
    return "(multi-step macro)"


def build_arbiter_prompt(query: str, patterns: list[Pattern]) -> str:
    """One-letter multiple-choice over embedding candidates + a NONE escape.

    Action-contrastive: each option shows its command SHAPE because the
    candidates often share a topic and differ only in the ACTION (the
    subcommand). Measured 2026-06-15: intent+shape @k=5 lifted selection
    accuracy 68.9%->79.5% on routable creative queries vs intents-only @k=3."""
    opts = "\n".join(
        f"{_ARBITER_LETTERS[i]}: {_pattern_intent(p)}\n   command: {_arbiter_shape(p)}"
        for i, p in enumerate(patterns)
    )
    none_letter = _ARBITER_LETTERS[len(patterns)]
    return (
        "Pick the ONE automation whose ACTION matches the request, or NONE if "
        "none fit (creative, math, coding, or general-knowledge requests fit "
        "NONE). The options may share a topic but differ in the ACTION they "
        "perform — look at each command to decide.\n\n"
        f'Request: "{query}"\n\n'
        f"{opts}\n{none_letter}: NONE of these\n\n"
        "Reply with exactly one letter."
    )


def parse_arbiter_reply(text: str, n_candidates: int) -> int | None:
    """Index of the chosen candidate, or None for the NONE escape / garbage.

    The first ascii letter in the reply decides; letters beyond the candidate
    range (the NONE option, or anything unparseable) -> None."""
    for ch in (text or ""):
        if ch.isalpha():
            idx = _ARBITER_LETTERS.find(ch.upper())
            if 0 <= idx < n_candidates:
                return idx
            return None
    return None


class Reflexer:
    def __init__(
        self,
        store: "PatternStore",
        llm: "LLMClient",
        config: AlfredConfig | None = None,
    ) -> None:
        self.store = store
        self.llm = llm
        self.config = config

    def execute(
        self,
        pattern: Pattern,
        query: str,
        decision: RoutingDecision | None = None,
    ) -> ReflexerResult:
        t_start = time.perf_counter()

        if self._should_arbitrate(decision):
            return self._execute_arbitrated(pattern, query, decision, t_start)

        if self._should_disambiguate(decision):
            return self._execute_disambiguated(pattern, query, decision, t_start)

        try:
            command, llm_ms = self.llm.generate_command(query, pattern)
        except LLMTimeout:
            return self._escalate("llm_timeout", 0, t_start, "", 0)
        except LLMError as e:
            return self._escalate(f"llm_error_{e.kind}", 0, t_start, "", 0)

        return self._run_steps(pattern, command, llm_ms, t_start)

    # ── tail arbiter (regex-miss tail) ──────────────────────────────────

    def _should_arbitrate(self, decision: RoutingDecision | None) -> bool:
        return (
            decision is not None
            and bool(getattr(decision, "arbiter_candidates", None))
            and self.config is not None
            and getattr(self.config, "tail_arbiter", False)
        )

    def _execute_arbitrated(
        self,
        pattern: Pattern,
        query: str,
        decision: RoutingDecision,
        t_start: float,
    ) -> ReflexerResult:
        cand_ids = [
            pid for pid in decision.arbiter_candidates
            if pid in self.store.patterns
        ]
        if not cand_ids:
            # Stale candidates — degrade to the provisional top-1 normal path.
            return self._generate_and_run(pattern, query, t_start, 0)

        cands = [self.store.patterns[pid] for pid in cand_ids]
        prompt = build_arbiter_prompt(query, cands)
        try:
            reply, llm_ms = self._chat(prompt)
        except LLMTimeout:
            return self._escalate("llm_timeout", 0, t_start, "", 0)
        except LLMError as e:
            return self._escalate(f"llm_error_{e.kind}", 0, t_start, "", 0)

        idx = parse_arbiter_reply(reply, len(cands))
        if idx is None:
            # NONE / unparseable -> Thinker (the precision guard's whole point).
            return self._escalate("arbiter_none", 0, t_start, "", llm_ms)
        return self._generate_and_run(cands[idx], query, t_start, llm_ms)

    # ── disambiguation (v3) ─────────────────────────────────────────────

    def _should_disambiguate(self, decision: RoutingDecision | None) -> bool:
        return (
            decision is not None
            and len(getattr(decision, "ambiguous_between", []) or []) == 2
            and self.config is not None
            and getattr(self.config, "reflexer_disambiguation", False)
        )

    def _execute_disambiguated(
        self,
        pattern: Pattern,
        query: str,
        decision: RoutingDecision,
        t_start: float,
    ) -> ReflexerResult:
        a_id, b_id = decision.ambiguous_between[:2]
        a = self.store.patterns.get(a_id)
        b = self.store.patterns.get(b_id)
        if a is None or b is None:
            # Stale decision — degrade to the normal path on the provisional.
            return self._generate_and_run(pattern, query, t_start, 0)

        prompt = build_disambiguation_prompt(query, a, b)
        try:
            reply, llm_ms = self._chat(prompt)
        except LLMTimeout:
            return self._escalate("llm_timeout", 0, t_start, "", 0)
        except LLMError as e:
            return self._escalate(f"llm_error_{e.kind}", 0, t_start, "", 0)

        chosen_id, command = parse_disambiguation_reply(reply, {a_id, b_id})
        if chosen_id is None:
            # Choice line missing/invalid — fall back to provisional top-1
            # via the normal single-pattern generation path.
            return self._generate_and_run(pattern, query, t_start, llm_ms)

        chosen = self.store.patterns[chosen_id]
        expected_binary = ""
        if chosen.steps:
            args_template = str(chosen.steps[0].get("args_template", ""))
            expected_binary = (args_template.strip().split(None, 1) or [""])[0]
        if not command or (
            expected_binary and command.split(None, 1)[0] != expected_binary
        ):
            # Choice was valid but the command line wasn't — regenerate for
            # the CHOSEN pattern.
            return self._generate_and_run(chosen, query, t_start, llm_ms)

        return self._run_steps(chosen, command, llm_ms, t_start)

    def _generate_and_run(
        self, pattern: Pattern, query: str, t_start: float, prior_llm_ms: int
    ) -> ReflexerResult:
        try:
            command, llm_ms = self.llm.generate_command(query, pattern)
        except LLMTimeout:
            return self._escalate("llm_timeout", 0, t_start, "", prior_llm_ms)
        except LLMError as e:
            return self._escalate(f"llm_error_{e.kind}", 0, t_start, "", prior_llm_ms)
        return self._run_steps(pattern, command, prior_llm_ms + llm_ms, t_start)

    def _chat(self, prompt: str) -> tuple[str, int]:
        """Raw chat call sharing the LLMClient's endpoint/model/system prompt.

        Kept here (not in llm_client.py) per Workstream C file ownership;
        stdlib urllib only. Tests stub this method."""
        body = {
            "model": self.llm.model,
            "messages": (
                [{"role": "system", "content": self.llm.system_prompt},
                 {"role": "user", "content": prompt}]
                if getattr(self.llm, "system_prompt", "")
                else [{"role": "user", "content": prompt}]
            ),
            "temperature": 0,
            "max_tokens": getattr(self.llm, "max_tokens", 1024),
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.llm.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.llm.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise LLMError("http_error", str(e))
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                raise LLMTimeout(detail=str(e))
            raise LLMError("http_error", str(e))
        except socket.timeout as e:
            raise LLMTimeout(detail=str(e))
        latency_ms = int((time.perf_counter() - t0) * 1000)
        try:
            payload = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"].get("content") or ""
        except (json.JSONDecodeError, KeyError, IndexError, TypeError,
                UnicodeDecodeError) as e:
            raise LLMError("malformed_response", str(e)[:200])
        return content, latency_ms

    # ── execution (shared by both paths) ────────────────────────────────

    def _run_steps(
        self, pattern: Pattern, command: str, llm_ms: int, t_start: float
    ) -> ReflexerResult:
        if not pattern.steps:
            return self._escalate("no_steps", 0, t_start, command, llm_ms)
        step = pattern.steps[0]
        timeout = int(step.get("timeout", 10))
        retries = int(step.get("retries", 0))

        try:
            result = self._bash(command, timeout=timeout)
        except subprocess.TimeoutExpired:
            return self._escalate(f"timeout_after_{timeout}s", 0, t_start, command, llm_ms)

        if result.exit_code != 0 and retries > 0:
            try:
                result = self._bash(command, timeout=timeout)
            except subprocess.TimeoutExpired:
                return self._escalate("exec_error_after_retry", 0, t_start, command, llm_ms)
            if result.exit_code != 0:
                return self._escalate("exec_error_after_retry", 0, t_start, command,
                                      llm_ms, output=_error_tail(result))
        elif result.exit_code != 0:
            return self._escalate(f"exec_error_{result.exit_code}", 0, t_start, command,
                                  llm_ms, output=_error_tail(result))

        for v in pattern.validators:
            passed, reason = validators.check(v["assert"], result)
            if not passed:
                on_fail = step.get("on_failure", "escalate_to_thinker")
                if on_fail == "escalate_to_thinker":
                    return self._escalate(
                        f"validator_failed_{reason}", 0, t_start, command, llm_ms,
                        output=_error_tail(result),
                    )
                return ReflexerResult(
                    status="failure",
                    reason=f"validator_{reason}",
                    output=_error_tail(result),
                    command_generated=command,
                    steps_executed=1,
                    total_latency_ms=int((time.perf_counter() - t_start) * 1000),
                    llm_latency_ms=llm_ms,
                )

        self.store.record_execution(pattern.id, success=True)
        return ReflexerResult(
            status="success",
            output=result.stdout,
            command_generated=command,
            steps_executed=1,
            total_latency_ms=int((time.perf_counter() - t_start) * 1000),
            llm_latency_ms=llm_ms,
        )

    def _escalate(
        self,
        reason: str,
        step_idx: int,
        t_start: float,
        command: str,
        llm_ms: int,
        output: str = "",
    ) -> ReflexerResult:
        return ReflexerResult(
            status="escalated",
            reason=reason,
            output=output,
            command_generated=command,
            steps_executed=step_idx,
            total_latency_ms=int((time.perf_counter() - t_start) * 1000),
            llm_latency_ms=llm_ms,
        )

    def _bash(self, command: str, timeout: int) -> ExecutionResult:
        cp = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ExecutionResult(stdout=cp.stdout, stderr=cp.stderr, exit_code=cp.returncode)
