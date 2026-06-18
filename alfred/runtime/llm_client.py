"""OpenAI-compatible client for the small command-generating LLM.

Stdlib-only: uses urllib.request. POSTs to /chat/completions and asks the
model to produce a single shell command directly. No JSON, no slot template.

Reasoning-model handling: some models emit chain-of-thought in
`message.reasoning_content` and put the answer in `message.content`. If
content is empty we fall back to extracting a command line from reasoning.
"""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import date
from typing import TYPE_CHECKING

from .types import LLMError, LLMTimeout

if TYPE_CHECKING:
    from .types import Pattern


_TYPE_PLACEHOLDER = {
    "number": "N",
    "integer": "N",
    "int": "N",
    "string": "STR",
    "date": "DATE",
    "datetime": "DATETIME",
    "boolean": "BOOL",
    "bool": "BOOL",
}

_SLOT_REF_RE = re.compile(r"\{\{([a-zA-Z_][\w\-]*)\}\}")
_OPT_HEAD_RE = re.compile(r"\{\{\?([a-zA-Z_][\w\-]*):\s*")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```\s*$")


def _match_optional_block(text: str, start: int) -> tuple[str, str, int] | None:
    """Match {{?name: body}} starting at `start`, where body may contain {{slot}} refs.

    Returns (slot_name, body, end_index_exclusive) or None.
    Body terminates at the first `}}` that is NOT part of an inner `{{...}}` ref.
    """
    head = _OPT_HEAD_RE.match(text, start)
    if not head:
        return None
    slot_name = head.group(1)
    i = head.end()
    body_chars: list[str] = []
    n = len(text)
    while i < n - 1:
        if text[i] == "{" and i + 1 < n and text[i + 1] == "{":
            ref = _SLOT_REF_RE.match(text, i)
            if ref:
                body_chars.append(ref.group(0))
                i = ref.end()
                continue
            return None
        if text[i] == "}" and text[i + 1] == "}":
            return slot_name, "".join(body_chars), i + 2
        body_chars.append(text[i])
        i += 1
    return None

_PROMPT_TEMPLATE = (
    "You output ONE shell command. No prose, no markdown, no explanation.\n"
    "\n"
    "Command shape:\n"
    "  {shape}\n"
    "\n"
    "Arguments:\n"
    "{slot_descriptions}\n"
    "\n"
    "User query: \"{query}\"\n"
    "\n"
    "Command:"
)


def _placeholder_for(slot_type: str) -> str:
    return _TYPE_PLACEHOLDER.get((slot_type or "").lower(), "VAL")


def _build_command_shape(args_template: str, slots: list[dict]) -> str:
    tmpl = (args_template or "").strip()
    if not tmpl:
        return ""
    parts = tmpl.split(None, 2)
    if len(parts) < 2:
        return tmpl
    binary, subcommand = parts[0], parts[1]
    remainder = parts[2] if len(parts) == 3 else ""

    types_by_name = {s.get("name", ""): s.get("type", "string") for s in slots}

    try:
        out: list[str] = []
        i = 0
        while i < len(remainder):
            opt = _match_optional_block(remainder, i)
            if opt is not None:
                _slot_name, inner, end = opt
                simplified = _SLOT_REF_RE.sub(
                    lambda m: _placeholder_for(types_by_name.get(m.group(1), "string")),
                    inner,
                ).strip()
                out.append(f"[{simplified}]")
                i = end
                continue
            req = _SLOT_REF_RE.match(remainder, i)
            if req:
                out.append(f"<{req.group(1).upper()}>")
                i = req.end()
                continue
            out.append(remainder[i])
            i += 1
        shape_tail = "".join(out)
        shape_tail = re.sub(r"\s+", " ", shape_tail).strip()
        return f"{binary} {subcommand}" + (f" {shape_tail}" if shape_tail else "")
    except Exception:
        return f"{binary} {subcommand} [args...]"


def _build_slot_descriptions(slots: list[dict]) -> str:
    if not slots:
        return "  (none)"
    lines: list[str] = []
    name_width = min(max((len(s.get("name", "")) for s in slots), default=0), 16)
    for s in slots:
        name = s.get("name", "")
        typ = s.get("type", "string")
        required = "required" if s.get("required") else "optional"
        if "default" in s and s.get("default") is not None:
            meta = f"({typ}, {required}, default={s['default']})"
        else:
            meta = f"({typ}, {required})"
        desc = s.get("description", "")
        line = f"  {name.ljust(name_width)}  {meta}  {desc}".rstrip()
        if len(line) > 80:
            line = line[:77] + "..."
        lines.append(line)
    return "\n".join(lines)


def _strip_command(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    # Strip surrounding code fences (multi-line)
    if s.startswith("```"):
        # Drop first fence line
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[: -3]
        s = s.strip()
    # Walk non-empty lines, prefer the first that doesn't look like prose
    for raw_line in s.splitlines():
        line = raw_line.strip()
        # Disambiguation-style "PATTERN: <id>" lines are never commands.
        # (Live 3B models were observed prefixing them even in normal mode
        # while the disambiguation section lived in the system prompt.)
        if re.match(r"(?i)^PATTERN\s*:", line):
            continue
        if not line:
            continue
        # Strip an inline single-line fence ``` at start/end
        line = _FENCE_RE.sub("", line).strip()
        # Strip wrapping backticks
        if line.startswith("`") and line.endswith("`") and len(line) >= 2:
            line = line[1:-1].strip()
        if line:
            return line
    return ""


_SYSTEM_PROMPT_PATH = __file__.replace("llm_client.py", "reflexer_system_prompt.md")


def _load_system_prompt() -> str:
    try:
        with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: int = 8,
        max_tokens: int = 1024,
        system_prompt: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        raw_prompt = system_prompt if system_prompt is not None else _load_system_prompt()
        self.system_prompt = raw_prompt.replace("{TODAY}", date.today().isoformat())
        # Usage of the most recent call ({"prompt_tokens": n, "completion_tokens": n}
        # when the server reports it, {} otherwise). Read by the REPL runner.
        self.last_usage: dict = {}

    def generate_command(self, query: str, pattern: "Pattern") -> tuple[str, int]:
        args_template = ""
        if pattern.steps:
            args_template = str(pattern.steps[0].get("args_template", ""))
        expected_binary = (args_template.strip().split(None, 1) or [""])[0]

        prompt = self._build_prompt(query, pattern, args_template)
        body = {
            "model": self.model,
            "messages": (
                [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
                if self.system_prompt
                else [{"role": "user", "content": prompt}]
            ),
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
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
            message = payload["choices"][0]["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError) as e:
            raise LLMError("malformed_response", str(e)[:200])
        self.last_usage = payload.get("usage") or {}

        command = _strip_command(content)
        if not command and reasoning:
            # Look for a final code-fence block or the last non-empty line
            command = _strip_command(self._extract_from_reasoning(reasoning))
        if not command:
            raise LLMError("empty_command", detail=(content or reasoning)[:200])

        if expected_binary and command.split(None, 1)[0] != expected_binary:
            raise LLMError("wrong_binary", detail=command[:200])

        return command, latency_ms

    # ── generic chat (full-loop triage + future consolidation point) ──

    def chat(
        self,
        prompt: str,
        max_tokens: int = 128,
        system: str | None = None,
    ) -> tuple[str, int]:
        """One-shot chat call. Returns (content, latency_ms). Raises LLMError /
        LLMTimeout like generate_command. Updates self.last_usage."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
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
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError) as e:
            raise LLMError("malformed_response", str(e)[:200])
        self.last_usage = payload.get("usage") or {}
        return content.strip(), latency_ms

    # ── margin-gated disambiguation (v2) ──────────────────────────
    #
    # When the Router can't decide between two patterns (margin < threshold),
    # this tiny call asks the model to pick A or B. Single-letter output, ~30-80ms.

    def disambiguate_pair(
        self,
        query: str,
        pattern_a_id: str,
        pattern_a_intent: str,
        pattern_b_id: str,
        pattern_b_intent: str,
    ) -> tuple[str, int]:
        """Returns (chosen_pattern_id, latency_ms). Falls back to A on malformed reply."""
        prompt = (
            "You are choosing between two patterns to handle a user query.\n\n"
            f'User query: "{query}"\n\n'
            f"Option A: {pattern_a_intent}\n"
            f"Option B: {pattern_b_intent}\n\n"
            "Reply with exactly one letter: A or B."
        )
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 4,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout):
            return (pattern_a_id, 0)  # fallback to top-1 on any failure
        latency_ms = int((time.perf_counter() - t0) * 1000)
        try:
            payload = json.loads(raw.decode("utf-8"))
            content = (payload["choices"][0]["message"].get("content") or "").strip().upper()
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return (pattern_a_id, latency_ms)
        # First letter is what we care about
        first = content[:1] if content else ""
        if first == "B":
            return (pattern_b_id, latency_ms)
        return (pattern_a_id, latency_ms)

    # ── composite-slot extraction (v2) ─────────────────────────────
    #
    # New mode: extract multiple slots from a user query for a composite pattern.
    # Single LLM call returns flat JSON {slot_name: value}.

    def extract_composite_slots(
        self,
        composite_slots: list[dict],
        query: str,
        today_iso: str | None = None,
    ) -> dict:
        """Extract values for each composite_slot from the user query.

        Returns a flat dict {slot_name: value}. Raises LLMError on malformed
        response. Values are returned as-is from the model (caller may need
        to cast for typing)."""
        from datetime import date as _date
        today_iso = today_iso or _date.today().isoformat()

        slot_lines = []
        for s in composite_slots:
            name = s.get("name", "")
            typ = s.get("type", "string")
            desc = s.get("description", "")
            default = s.get("default")
            d = f" (default: {default})" if default is not None else ""
            slot_lines.append(f"- {name} ({typ}){d}: {desc}")
        slot_block = "\n".join(slot_lines)

        system_prompt = (
            "You are Reflexer in slot-extraction mode for a composite pattern.\n\n"
            f"Today is {today_iso}.\n\n"
            "Your job: given a user query and a list of slots, extract the value "
            "for each slot from the query. Output ONLY valid JSON: a flat object "
            "mapping slot name to value. No prose, no fences, no explanation.\n\n"
            "Rules:\n"
            "- If a slot is not present in the query and has no default, use null.\n"
            "- For date slots, return ISO YYYY-MM-DD. Resolve 'today', 'tomorrow', "
            "'next monday', etc. against the date above.\n"
            "- For string slots, extract the literal substring from the query "
            "(do not paraphrase). Quote-strip if the user used surrounding quotes.\n"
            "- For integer/boolean slots, parse exactly.\n"
            "- Never invent values not derivable from the query.\n"
        )
        user_prompt = (
            f"Slots to extract:\n{slot_block}\n\n"
            f'User query: "{query}"\n\n'
            "Output JSON:"
        )

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": min(self.max_tokens, 512),
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise LLMError("http_error", str(e))
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                raise LLMTimeout(detail=str(e))
            raise LLMError("http_error", str(e))
        except socket.timeout as e:
            raise LLMTimeout(detail=str(e))

        try:
            payload = json.loads(raw.decode("utf-8"))
            content = (payload["choices"][0]["message"].get("content") or "").strip()
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            raise LLMError("malformed_response", str(e)[:200])

        # Strip code fences if the model wrapped output
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```\s*$", "", content)
        try:
            extracted = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError("composite_slots_not_json", f"{e}: {content[:200]}")
        if not isinstance(extracted, dict):
            raise LLMError("composite_slots_not_object", f"got {type(extracted).__name__}")
        return extracted

    def _extract_from_reasoning(self, reasoning: str) -> str:
        # Prefer the last fenced block content
        fences = re.findall(r"```[a-zA-Z]*\n?(.*?)```", reasoning, flags=re.DOTALL)
        if fences:
            for block in reversed(fences):
                stripped = block.strip()
                if stripped:
                    return stripped
        # Otherwise the last non-empty line
        for line in reversed(reasoning.splitlines()):
            if line.strip():
                return line.strip()
        return ""

    def _build_prompt(self, query: str, pattern: "Pattern", args_template: str) -> str:
        shape = _build_command_shape(args_template, pattern.slots)
        slot_descriptions = _build_slot_descriptions(pattern.slots)
        return _PROMPT_TEMPLATE.format(
            shape=shape or "(unknown)",
            slot_descriptions=slot_descriptions,
            query=query,
        )
