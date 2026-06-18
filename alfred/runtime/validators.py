"""Validator assertion dispatch table."""
from __future__ import annotations

import json
import re
import warnings
from typing import Any

from alfred.runtime.types import ExecutionResult


def _try_json(s: str) -> Any:
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None


def _json_path(s: str, dotted: str) -> Any:
    obj = _try_json(s)
    if obj is None:
        return None
    for part in dotted.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None
    return obj


ASSERTIONS = {
    "stdout_parses_as_json": lambda r: _try_json(r.stdout) is not None,
    "ok == true": lambda r: _json_path(r.stdout, "ok") is True,
    "data.ok == true": lambda r: _json_path(r.stdout, "data.ok") is True,
    "data.threads is_list": lambda r: isinstance(_json_path(r.stdout, "data.threads"), list),
    "data.messages is_list": lambda r: isinstance(_json_path(r.stdout, "data.messages"), list),
    "data.events is_list": lambda r: isinstance(_json_path(r.stdout, "data.events"), list),
    "data.sent == true": lambda r: _json_path(r.stdout, "data.sent") is True,
    "error == null": lambda r: _json_path(r.stdout, "error") is None,
    "exit_code == 0": lambda r: r.exit_code == 0,
    # Gmail (`gws`) shape — no ok/data wrapping
    "messages is_list": lambda r: isinstance(_json_path(r.stdout, "messages"), list),
    "thread_id is_string": lambda r: isinstance(_json_path(r.stdout, "thread_id"), str),
    "id is_string": lambda r: isinstance(_json_path(r.stdout, "id"), str),
    # Maps (OSM/OSRM) shape — raw JSON, no ok/data wrapping
    "results is_list": lambda r: isinstance(_json_path(r.stdout, "results"), list),
    "steps is_list": lambda r: isinstance(_json_path(r.stdout, "steps"), list),
    "distance_km is_number": lambda r: isinstance(_json_path(r.stdout, "distance_km"), (int, float)),
    "timezone is_string": lambda r: isinstance(_json_path(r.stdout, "timezone"), str),
    "google_maps_url is_string": lambda r: isinstance(_json_path(r.stdout, "google_maps_url"), str),
    # Flights (`flights` wrapper) — ok/data envelope
    "data.outbound is_list": lambda r: isinstance(_json_path(r.stdout, "data.outbound"), list),
    "data.dates is_list": lambda r: isinstance(_json_path(r.stdout, "data.dates"), list),
    "data.airports is_list": lambda r: isinstance(_json_path(r.stdout, "data.airports"), list),
    # Contacts (CardDAV) — ok/data envelope
    "data.contacts is_list": lambda r: isinstance(_json_path(r.stdout, "data.contacts"), list),
}


# Generic assert grammar — covers the 13 live asserts that predate their
# handlers (e.g. "data.busy is_list", "data.deleted == true"). Fixed ASSERTIONS
# entries take precedence so existing behavior is byte-identical.
_GENERIC_ASSERT = re.compile(
    r"^(?:(?P<path>[A-Za-z0-9_.]+)\s+(?P<op>is_list|is_string|is_number|is_boolean|present)"
    r"|(?P<path2>[A-Za-z0-9_.]+)\s*==\s*(?P<lit>true|false|null))$"
)


def _generic_check(assertion: str, result: ExecutionResult) -> bool | None:
    """Return pass/fail for grammar-shaped asserts, None if not grammar-shaped."""
    m = _GENERIC_ASSERT.match(assertion.strip())
    if m is None:
        return None
    if m.group("path"):
        val = _json_path(result.stdout, m.group("path"))
        op = m.group("op")
        if op == "is_list":
            return isinstance(val, list)
        if op == "is_string":
            return isinstance(val, str)
        if op == "is_number":
            return isinstance(val, (int, float)) and not isinstance(val, bool)
        if op == "is_boolean":
            return isinstance(val, bool)
        return val is not None  # present
    val = _json_path(result.stdout, m.group("path2"))
    return val is {"true": True, "false": False, "null": None}[m.group("lit")]


def check(assertion: str, result: ExecutionResult) -> tuple[bool, str]:
    fn = ASSERTIONS.get(assertion)
    if fn is None:
        try:
            generic = _generic_check(assertion, result)
        except Exception:
            return (False, assertion)
        if generic is not None:
            return (True, "ok") if generic else (False, assertion)
        # Stage-1 hardening (spec defect 4): an unknown assert used to be a
        # silent pass, which inflated the success stats feeding the routing
        # score. Fail loudly instead: tagged reason + a warning for the logs.
        warnings.warn(
            f"unknown validator assert {assertion!r}: failing validation "
            "(add a handler to ASSERTIONS or fix the pattern)",
            stacklevel=2,
        )
        return (False, f"unknown_assert:{assertion}")
    try:
        return (True, "ok") if fn(result) else (False, assertion)
    except Exception:
        return (False, assertion)
