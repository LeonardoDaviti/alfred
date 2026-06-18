"""Cache hierarchy — CommandCache (skips the Reflexer LLM) + ResponseCache
(skips execution too). Stage-1 core spec, Workstream B.

Both caches live in a single SQLite database (WAL mode) at an explicit
constructor path (``config.cache_db`` in production, a tempdir in tests).
The dispatcher is the only writer; every call is wrapped there so that a
cache failure degrades to a miss and can never break dispatch.

Key shapes
----------
- CommandCache:  ``(pattern_id, canon(message)) -> command``. Stored only
  after a successful validated execution. No TTL (commands are deterministic
  renderings of the message), but an entry is invalidated when its pattern's
  ``version`` no longer matches the stored one.
- ResponseCache: ``(pattern_id, command) -> stdout + validation status``.
  Only read-only patterns are cacheable, with a per-domain TTL and
  domain-scoped write-invalidation (a successful WRITE execution in domain D
  purges all of D's response entries).

Read/write classification
-------------------------
``signature`` may carry an optional ``"side_effect": true/false`` which wins
outright. When absent, classification is inferred from ``signature.action``:

- READ allowlist (matched against the full action string OR any of its
  underscore-separated tokens, e.g. ``read_inbox`` -> ``read``):
  ``get | list | search | read | check | find | lookup | geocode | forecast |
  current | distance | directions | nearby | cheapest | airports |
  export_route_link | travel_distance | find_nearby | triage``
- WRITE denylist (takes precedence over any read token, so e.g. a
  hypothetical ``delete_search_history`` stays WRITE):
  ``send | create | delete | add | set | update | remove | write | post |
  mark | cancel | notify | reply | move | archive``
- Anything else (unknown / empty action) -> WRITE, i.e. uncacheable.

Token matching (rather than exact matching) is required because live
pattern actions are compounds (``read_current_conditions``,
``cheapest_dates``, ``airport_lookup``); the denylist keeps it conservative.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .types import Pattern


# ── canonicalization ──────────────────────────────────────────────────────

# Leading-politeness tokens stripped by canon(). Keep this list short; each
# token only matches as a whole word (followed by space/comma/end-of-string).
_POLITENESS_PREFIXES = ("please", "hey", "can you", "could you", "alfred")


def canon(message: str) -> str:
    """Canonical form of a user message for command-cache keying.

    lowercase -> collapse whitespace -> strip terminal punctuation ->
    strip leading politeness tokens (repeatedly, so stacked prefixes like
    "hey alfred, can you please ..." all come off)."""
    s = " ".join(message.lower().split())
    s = s.rstrip(".!?").rstrip()
    changed = True
    while changed:
        changed = False
        for tok in _POLITENESS_PREFIXES:
            if s.startswith(tok):
                rest = s[len(tok):]
                if rest == "" or rest[0] in " ,":
                    s = rest.lstrip(" ,")
                    changed = True
    return s


# ── read/write classification ─────────────────────────────────────────────

READ_ACTION_TOKENS = frozenset({
    "get", "list", "search", "read", "check", "find", "lookup", "geocode",
    "forecast", "current", "distance", "directions", "nearby", "cheapest",
    "airports", "export_route_link", "travel_distance", "find_nearby",
    "triage",
})

WRITE_ACTION_TOKENS = frozenset({
    "send", "create", "delete", "add", "set", "update", "remove", "write",
    "post", "mark", "cancel", "notify", "reply", "move", "archive",
})


def is_read_pattern(pattern: "Pattern") -> bool:
    """True iff the pattern is side-effect-free (response-cacheable).

    Explicit ``signature.side_effect`` wins; otherwise infer from
    ``signature.action`` per the module docstring. Unknown -> WRITE."""
    sig = (pattern.raw or {}).get("signature", {}) or {}
    side_effect = sig.get("side_effect")
    if side_effect is not None:
        return not bool(side_effect)
    action = str(sig.get("action", "") or "").lower()
    if not action:
        return False
    if action in READ_ACTION_TOKENS:
        return True
    tokens = set(action.split("_"))
    if tokens & WRITE_ACTION_TOKENS:
        return False
    return bool(tokens & READ_ACTION_TOKENS)


# ── TTLs ──────────────────────────────────────────────────────────────────

DOMAIN_TTLS_S: dict[str, int] = {
    "weather": 1800,
    "flights": 900,
    "email": 300,
    "caldav": 600,
    "maps": 604800,
    "contacts": 604800,
}
DEFAULT_TTL_S = 600


def ttl_for(pattern: "Pattern") -> int:
    """Response TTL in seconds: pattern metadata ``cache_ttl_s`` override,
    else the per-domain default, else DEFAULT_TTL_S."""
    meta = (pattern.raw or {}).get("metadata", {}) or {}
    override = meta.get("cache_ttl_s")
    if isinstance(override, (int, float)) and not isinstance(override, bool) and override > 0:
        return int(override)
    return DOMAIN_TTLS_S.get(pattern.domain, DEFAULT_TTL_S)


# ── storage ───────────────────────────────────────────────────────────────

class _SqliteCache:
    """Shared SQLite plumbing: explicit path, parent mkdir, WAL, autocommit."""

    _SCHEMA: str = ""

    def __init__(self, db_path: str | Path, now: Callable[[], float] = time.time):
        self._now = now
        path = Path(os.path.expanduser(str(db_path)))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(self._SCHEMA)

    def close(self) -> None:
        self._conn.close()


class CommandCache(_SqliteCache):
    """(pattern_id, canon(message)) -> generated command. No TTL;
    invalidated when the pattern's version changes."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS command_cache (
            pattern_id      TEXT    NOT NULL,
            canon_message   TEXT    NOT NULL,
            pattern_version INTEGER NOT NULL,
            command         TEXT    NOT NULL,
            created_at      REAL    NOT NULL,
            PRIMARY KEY (pattern_id, canon_message)
        )
    """

    def lookup(self, pattern: "Pattern", message: str) -> str | None:
        key = canon(message)
        row = self._conn.execute(
            "SELECT command, pattern_version FROM command_cache"
            " WHERE pattern_id = ? AND canon_message = ?",
            (pattern.id, key),
        ).fetchone()
        if row is None:
            return None
        command, stored_version = row
        if int(stored_version) != int(pattern.version):
            # Pattern was rewritten since this command was generated.
            self._conn.execute(
                "DELETE FROM command_cache WHERE pattern_id = ? AND canon_message = ?",
                (pattern.id, key),
            )
            return None
        return command

    def store(self, pattern: "Pattern", message: str, command: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO command_cache"
            " (pattern_id, canon_message, pattern_version, command, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (pattern.id, canon(message), int(pattern.version), command, self._now()),
        )

    def invalidate(self, pattern: "Pattern", message: str) -> None:
        self._conn.execute(
            "DELETE FROM command_cache WHERE pattern_id = ? AND canon_message = ?",
            (pattern.id, canon(message)),
        )


class ResponseCache(_SqliteCache):
    """(pattern_id, command) -> stdout, read-only patterns only, per-domain
    TTL, domain-scoped write-invalidation."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS response_cache (
            pattern_id  TEXT    NOT NULL,
            command     TEXT    NOT NULL,
            domain      TEXT    NOT NULL,
            stdout      TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            created_at  REAL    NOT NULL,
            ttl_s       INTEGER NOT NULL,
            PRIMARY KEY (pattern_id, command)
        )
    """

    def lookup(self, pattern: "Pattern", command: str) -> str | None:
        if not is_read_pattern(pattern):
            return None
        row = self._conn.execute(
            "SELECT stdout, created_at, ttl_s FROM response_cache"
            " WHERE pattern_id = ? AND command = ?",
            (pattern.id, command),
        ).fetchone()
        if row is None:
            return None
        stdout, created_at, ttl_s = row
        if self._now() - float(created_at) > float(ttl_s):
            self._conn.execute(
                "DELETE FROM response_cache WHERE pattern_id = ? AND command = ?",
                (pattern.id, command),
            )
            return None
        return stdout

    def store(self, pattern: "Pattern", command: str, stdout: str,
              status: str = "success") -> None:
        if not is_read_pattern(pattern):
            return  # WRITE patterns are never response-cached
        self._conn.execute(
            "INSERT OR REPLACE INTO response_cache"
            " (pattern_id, command, domain, stdout, status, created_at, ttl_s)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pattern.id, command, pattern.domain, stdout, status,
             self._now(), ttl_for(pattern)),
        )

    def purge_domain(self, domain: str) -> None:
        self._conn.execute("DELETE FROM response_cache WHERE domain = ?", (domain,))

    def record_success(self, pattern: "Pattern", command: str, stdout: str) -> None:
        """Post-execution hook: store the response for read patterns;
        purge the pattern's domain for successful writes."""
        if is_read_pattern(pattern):
            self.store(pattern, command, stdout)
        else:
            self.purge_domain(pattern.domain)
