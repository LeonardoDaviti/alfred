"""Composite executor — runs a CompositePattern's atom sequence deterministically.

Composites are macros: a composite declares a list of atomic pattern IDs plus
slot bindings (literals, composite-extracted slots, runtime vars like {{TODAY}},
or references to previous step outputs). The executor:

  1. (optional) extracts composite_slots from the user query via one LLM call
  2. for each atom, resolves slot bindings, renders the command, runs it
  3. parses stdout per the composite's parse_schema
  4. renders the output_template

NO Reflexer LLM call between atoms — that's by design (Option A in the v2 plan).
Conditional skip via skip_if is supported but limited to one binary comparison
per atom; anything richer is deferred to "Option B agentic composites" in
future.md §7.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from time import time
from typing import Any

from alfred.runtime.types import (
    CompositeAtomRef,
    CompositePattern,
    CompositeResult,
    CompositeStepResult,
    LLMError,
)


class BindingError(Exception):
    pass


# ── runtime variable resolver ────────────────────────────────────────
_RUNTIME_VAR_RE = re.compile(r"^\s*(TODAY|TOMORROW|YESTERDAY|NOW)\s*(?:([+-])\s*(\d+)\s*([dhmw]))?\s*$")


def _resolve_runtime_var(token: str, today: date) -> str | None:
    """Resolve {{TODAY}}, {{TOMORROW}}, {{TODAY+7d}}, {{TODAY-1d}}, {{NOW}} etc.

    Returns ISO string for date vars, or None if `token` is not a runtime var.
    Supported units: d (days), w (weeks). h/m hours/minutes return current
    time-based ISO."""
    m = _RUNTIME_VAR_RE.match(token)
    if not m:
        return None
    base, sign, num, unit = m.groups()
    d = today
    if base == "TOMORROW":
        d = today + timedelta(days=1)
    elif base == "YESTERDAY":
        d = today - timedelta(days=1)
    if sign and num and unit:
        delta = int(num)
        if unit == "d":
            d = d + (timedelta(days=delta) if sign == "+" else timedelta(days=-delta))
        elif unit == "w":
            d = d + (timedelta(weeks=delta) if sign == "+" else timedelta(weeks=-delta))
    return d.isoformat()


# ── template / binding resolution ────────────────────────────────────
_REF_RE = re.compile(r"\{\{([^{}]+)\}\}")


def _lookup_step(expr: str, steps: list["CompositeStepResult"]) -> Any:
    """expr like 'step[0].first_free.start' — return value or raise."""
    m = re.match(r"step\[(\d+)\]\.(.+)", expr)
    if not m:
        raise BindingError(f"bad step ref: {expr!r}")
    idx = int(m.group(1))
    key = m.group(2)
    if idx >= len(steps):
        raise BindingError(f"step[{idx}] not yet executed (only {len(steps)} done)")
    parsed = steps[idx].parsed
    if key in parsed:
        return parsed[key]
    raise BindingError(f"step[{idx}].{key} not in parse_schema output")


def _resolve_value(raw: Any, slots: dict[str, Any], steps: list["CompositeStepResult"],
                   today: date) -> Any:
    """Resolve a single slot-binding value into a Python value.

    Forms supported:
      - literal: int / bool / non-templated string
      - {{TODAY}}, {{TOMORROW}}, {{TODAY+7d}} — runtime date var
      - {{composite_slot_name}} — extracted slot
      - {{step[N].key}} — output of prior atom
      - mixed: "Re: {{step[1].subject}}" — substring substitution
    """
    if not isinstance(raw, str):
        return raw  # int, bool, None pass through

    # Whole-string reference (single {{...}}) — preserve type when possible
    m_whole = re.fullmatch(r"\{\{([^{}]+)\}\}", raw)
    if m_whole:
        token = m_whole.group(1).strip()
        runtime = _resolve_runtime_var(token, today)
        if runtime is not None:
            return runtime
        if token.startswith("step["):
            return _lookup_step(token, steps)
        if token in slots:
            return slots[token]
        raise BindingError(f"unknown slot reference: {{{{{token}}}}}")

    # Mixed string with one-or-more references — substring substitution
    def _sub(match: re.Match) -> str:
        token = match.group(1).strip()
        runtime = _resolve_runtime_var(token, today)
        if runtime is not None:
            return runtime
        if token.startswith("step["):
            v = _lookup_step(token, steps)
            return str(v)
        if token in slots:
            return str(slots[token])
        raise BindingError(f"unknown slot reference: {{{{{token}}}}}")

    return _REF_RE.sub(_sub, raw)


def _resolve_bindings(bindings: dict[str, Any], slots: dict[str, Any],
                      steps: list["CompositeStepResult"], today: date) -> dict[str, Any]:
    return {name: _resolve_value(val, slots, steps, today) for name, val in bindings.items()}


# ── args_template rendering ──────────────────────────────────────────
_SLOT_REF_RE = re.compile(r"\{\{([a-zA-Z_][\w\-]*)\}\}")
_OPT_HEAD_RE = re.compile(r"\{\{\?([a-zA-Z_][\w\-]*):\s*")


def _render_command(args_template: str, resolved: dict[str, Any]) -> str:
    """Substitute {{slot}} and {{?slot: body}} per the atom's args_template grammar.

    Same grammar as alfred/runtime/llm_client.py's command-shape builder, but
    here we have CONCRETE values, not just types."""
    tmpl = args_template
    out: list[str] = []
    i = 0
    n = len(tmpl)
    while i < n:
        # Optional block: {{?name: body}}
        opt = _OPT_HEAD_RE.match(tmpl, i)
        if opt is not None:
            slot_name = opt.group(1)
            body_start = opt.end()
            # find matching }}
            depth = 1
            j = body_start
            body_chars: list[str] = []
            while j < n - 1 and depth > 0:
                if tmpl[j] == "{" and tmpl[j + 1] == "{":
                    inner = _SLOT_REF_RE.match(tmpl, j)
                    if inner:
                        body_chars.append(inner.group(0))
                        j = inner.end()
                        continue
                if tmpl[j] == "}" and tmpl[j + 1] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                body_chars.append(tmpl[j])
                j += 1
            body = "".join(body_chars)
            value = resolved.get(slot_name)
            if value is None or value == "" or value is False:
                pass  # omit
            else:
                body_rendered = _SLOT_REF_RE.sub(
                    lambda m: str(resolved.get(m.group(1), "")), body
                )
                # Ensure separation between the preceding literal and this block.
                # The template's optional blocks like `{{?max: --max {{max}}}}` have
                # no leading space; without this guard the previous literal sticks
                # to the body (e.g. `--format json--max 20`).
                if out and not out[-1].endswith((" ", "\n", "\t")) and not body_rendered.startswith(" "):
                    out.append(" ")
                out.append(body_rendered)
            i = j + 2
            continue
        # Required slot ref
        req = _SLOT_REF_RE.match(tmpl, i)
        if req:
            slot_name = req.group(1)
            value = resolved.get(slot_name, "")
            out.append(str(value))
            i = req.end()
            continue
        out.append(tmpl[i])
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


# ── parse_schema → step.parsed ───────────────────────────────────────
def _jsonpath_get(doc: Any, path: str) -> Any:
    """Limited JSONPath: '$.a.b[0].c' walks dicts and lists. No filters, no slicing."""
    if not path.startswith("$"):
        return None
    cur = doc
    # tokenize: . or [N]
    rest = path[1:]
    for tok in re.findall(r"\.([a-zA-Z_][\w\-]*)|\[(\d+)\]", rest):
        key, idx = tok
        if key:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        elif idx:
            if isinstance(cur, list) and int(idx) < len(cur):
                cur = cur[int(idx)]
            else:
                return None
        if cur is None:
            return None
    return cur


def _parse_step_output(stdout: str, step_index: int, parse_schema: dict[str, str]) -> dict[str, Any]:
    """Extract this step's fields from stdout per the composite's parse_schema.

    parse_schema is composite-wide: {'step[0].count': '$.resultSizeEstimate', ...}.
    For step_index N, we look at keys starting with 'step[N].' and apply each JSONPath."""
    try:
        doc = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        doc = {}
    prefix = f"step[{step_index}]."
    out: dict[str, Any] = {}
    for full_key, jsonpath in parse_schema.items():
        if not full_key.startswith(prefix):
            continue
        sub_key = full_key[len(prefix):]
        out[sub_key] = _jsonpath_get(doc, jsonpath)
    return out


# ── skip_if evaluation (limited) ─────────────────────────────────────
_SKIP_RE = re.compile(
    r"step\[(\d+)\]\.(\S+?)\s*(==|!=|<=|>=|<|>)\s*(\".+?\"|\S+)\s*$"
)


def _eval_skip(expr: str, steps: list["CompositeStepResult"]) -> bool:
    """True means SKIP this atom."""
    m = _SKIP_RE.match(expr.strip())
    if not m:
        return False
    idx, key, op, lit = m.groups()
    idx = int(idx)
    if idx >= len(steps):
        return False
    lhs = steps[idx].parsed.get(key)
    rhs: Any = lit.strip('"')
    # try numeric coercion for both sides
    try:
        rhs_n = float(rhs)
        if isinstance(lhs, (int, float)) or (isinstance(lhs, str) and lhs.replace(".", "").lstrip("-").isdigit()):
            lhs_n = float(lhs)
            lhs, rhs = lhs_n, rhs_n
    except (TypeError, ValueError):
        pass
    if op == "==": return lhs == rhs
    if op == "!=": return lhs != rhs
    if op == "<":  return lhs is not None and lhs < rhs
    if op == ">":  return lhs is not None and lhs > rhs
    if op == "<=": return lhs is not None and lhs <= rhs
    if op == ">=": return lhs is not None and lhs >= rhs
    return False


# ── bash runner ──────────────────────────────────────────────────────
@dataclass
class _BashOut:
    stdout: str
    stderr: str
    exit_code: int


class LocalBashExecutor:
    def __init__(self, timeout_s: int = 30):
        self.timeout_s = timeout_s

    def execute(self, cmd: str) -> _BashOut:
        try:
            res = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=self.timeout_s,
            )
            return _BashOut(stdout=res.stdout or "", stderr=res.stderr or "", exit_code=res.returncode)
        except subprocess.TimeoutExpired:
            return _BashOut(stdout="", stderr=f"timeout after {self.timeout_s}s", exit_code=124)
        except Exception as e:
            return _BashOut(stdout="", stderr=f"exec error: {e}", exit_code=1)


# ── executor ─────────────────────────────────────────────────────────
class CompositeExecutor:
    def __init__(self, store, llm_client, bash_executor=None):
        self.store = store
        self.llm = llm_client
        self.bash = bash_executor or LocalBashExecutor()

    def execute(self, composite: CompositePattern, query: str,
                today: date | None = None) -> CompositeResult:
        today = today or date.today()
        t_start = time()

        # 1. Extract composite_slots if any
        slots: dict[str, Any] = {}
        if composite.composite_slots:
            try:
                slots = self.llm.extract_composite_slots(
                    composite.composite_slots, query, today_iso=today.isoformat()
                )
            except (LLMError, Exception) as e:
                return CompositeResult.error(
                    composite.id, f"slot_extraction_failed: {type(e).__name__}: {e}"
                )
            # Apply declared defaults for slots the extractor left empty.
            # Defaults run through _resolve_value so runtime vars work
            # (e.g. "default": "{{TODAY+14d}}"). Before this, missing slots
            # rendered literally as "None" in commands.
            for spec in composite.composite_slots:
                name = spec.get("name")
                if name and slots.get(name) in (None, "", "None") and "default" in spec:
                    slots[name] = _resolve_value(spec["default"], slots, [], today)

        # 2. Run atoms
        step_results: list[CompositeStepResult] = []
        for i, atom_ref in enumerate(composite.atoms):
            # 2a. Skip check
            if atom_ref.skip_if and _eval_skip(atom_ref.skip_if, step_results):
                step_results.append(CompositeStepResult(
                    atom_id=atom_ref.pattern_id, skipped=True))
                continue

            # 2b. Resolve bindings against slots + prior steps + today
            try:
                resolved = _resolve_bindings(
                    atom_ref.slot_bindings, slots, step_results, today
                )
            except BindingError as e:
                return CompositeResult.error(
                    composite.id, f"binding_failed at atom[{i}] ({atom_ref.pattern_id}): {e}"
                )

            # 2c. Find atom + render command
            atom = self.store.patterns.get(atom_ref.pattern_id)
            if atom is None:
                return CompositeResult.error(
                    composite.id, f"missing atom: {atom_ref.pattern_id}"
                )
            if not atom.steps:
                return CompositeResult.error(
                    composite.id, f"atom {atom_ref.pattern_id} has no steps"
                )
            args_template = str(atom.steps[0].get("args_template", ""))
            cmd = _render_command(args_template, resolved)

            # 2d. Execute
            out = self.bash.execute(cmd)
            parsed = _parse_step_output(out.stdout, i, composite.parse_schema)
            step_results.append(CompositeStepResult(
                atom_id=atom_ref.pattern_id,
                command=cmd,
                stdout=out.stdout,
                stderr=out.stderr,
                exit_code=out.exit_code,
                parsed=parsed,
            ))

            # Record execution for stats (Option O1: composites count toward atom stats).
            # Only count as FAILURE when the command was structurally wrong; skill-backend
            # rejections of correct commands are not pattern-quality failures.
            try:
                if out.exit_code == 0:
                    self.store.record_execution(atom_ref.pattern_id, success=True)
                elif self.store.command_was_wrong(out.exit_code, out.stderr):
                    self.store.record_execution(
                        atom_ref.pattern_id, success=False,
                        failure_reason=out.stderr[:120],
                    )
                # else: backend rejected correct command — skip stats update
            except Exception:
                pass

        # 3. Render output template
        try:
            text = self._render_output_template(composite.output_template, slots, step_results, today)
        except BindingError as e:
            text = f"(output_template error: {e})"

        latency = int((time() - t_start) * 1000)
        # success only if all non-skipped atoms exit 0
        ok = all(s.exit_code == 0 or s.skipped for s in step_results)
        return CompositeResult(
            status="success" if ok else "failure",
            pattern_id=composite.id,
            output=text,
            steps=step_results,
            reason="" if ok else "one or more atoms failed",
            latency_ms=latency,
        )

    def _render_output_template(self, template: str, slots: dict[str, Any],
                                steps: list[CompositeStepResult], today: date) -> str:
        def _sub(m: re.Match) -> str:
            token = m.group(1).strip()
            runtime = _resolve_runtime_var(token, today)
            if runtime is not None:
                return runtime
            if token.startswith("step["):
                try:
                    v = _lookup_step(token, steps)
                except BindingError:
                    return f"<{token}?>"
                return "" if v is None else str(v)
            if token in slots:
                return str(slots[token])
            return f"<{token}?>"
        return _REF_RE.sub(_sub, template)
