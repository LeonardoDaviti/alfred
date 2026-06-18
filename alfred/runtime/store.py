"""PatternStore — load patterns + stats, compile triggers, record executions.

Lifecycle overlay (Stage-1 core spec wave 2, Workstream D): pattern JSON
files are immutable artifacts; lifecycle state (shadow/active/quarantined)
is a runtime overlay stored in the stats sidecar under the optional keys
`lifecycle`, `shadow_uses`, `shadow_successes`. Entries without an overlay
are `active` (legacy compat). All lifecycle behavior is gated behind
`config.lifecycle_enabled` / `config.skill_hash_check` — with the flags off
(or no config passed) the store is bit-identical to the pre-lifecycle one.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from alfred.runtime.router import wilson_lower
from alfred.runtime.types import AlfredConfig, CompositePattern, Pattern


class PatternStore:
    def __init__(self, patterns_dir: Path, stats_file: Path,
                 config: AlfredConfig | None = None):
        self.patterns_dir = Path(patterns_dir).expanduser() if not isinstance(patterns_dir, Path) else patterns_dir.expanduser()
        self.stats_file = Path(stats_file).expanduser() if not isinstance(stats_file, Path) else stats_file.expanduser()
        self.config = config                  # None = all lifecycle flags off
        self.patterns: dict[str, Pattern] = {}
        self.by_skill: dict[str, list[Pattern]] = {}
        self.compiled_triggers: dict[str, re.Pattern] = {}
        self.composites: dict[str, CompositePattern] = {}
        self.composite_triggers: dict[str, re.Pattern] = {}
        self.stats: dict[str, dict] = {}
        self.broken: list[tuple[str, str]] = []
        self._load()
        if self._cfg("skill_hash_check", False):
            self._check_skill_hashes()

    def _load(self) -> None:
        if self.patterns_dir.is_dir():
            for path in sorted(self.patterns_dir.glob("*.json")):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        items = json.load(f)
                except (OSError, json.JSONDecodeError) as e:
                    self.broken.append((path.name, f"file_load_error: {e}"))
                    continue
                if not isinstance(items, list):
                    self.broken.append((path.name, "file_not_a_list"))
                    continue
                for item in items:
                    pid = item.get("id", "<unknown>") if isinstance(item, dict) else "<unknown>"
                    # Composite patterns: dispatched first, separate registry
                    if isinstance(item, dict) and item.get("type") == "composite":
                        try:
                            comp = CompositePattern.from_dict(item)
                        except (KeyError, ValueError, TypeError) as e:
                            self.broken.append((pid, f"composite_parse_error: {e}"))
                            continue
                        try:
                            compiled = re.compile(comp.trigger_regex)
                        except re.error as e:
                            self.broken.append((comp.id, f"composite_regex_error: {e}"))
                            continue
                        self.composites[comp.id] = comp
                        self.composite_triggers[comp.id] = compiled
                        continue
                    try:
                        pattern = Pattern.from_dict(item)
                    except (KeyError, ValueError, TypeError) as e:
                        self.broken.append((pid, f"parse_error: {e}"))
                        continue
                    try:
                        compiled = re.compile(pattern.trigger_regex)
                    except re.error as e:
                        self.broken.append((pattern.id, f"regex_error: {e}"))
                        continue
                    self.patterns[pattern.id] = pattern
                    self.compiled_triggers[pattern.id] = compiled
                    self.by_skill.setdefault(pattern.domain, []).append(pattern)

        if self.stats_file.is_file():
            try:
                with self.stats_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.stats = data
            except (OSError, json.JSONDecodeError):
                self.stats = {}

    def active_patterns(self) -> list[Pattern]:
        if self._cfg("lifecycle_enabled", False):
            # Quarantined patterns don't route; shadow patterns DO (shadow
            # means "on probation", not "hidden").
            return [
                p for p in self.patterns.values()
                if p.status == "active"
                and self.lifecycle_state(p.id) != "quarantined"
            ]
        return [p for p in self.patterns.values() if p.status == "active"]

    def quarantined_patterns(self) -> list[Pattern]:
        """Quarantined-overlay patterns — the Router's exploration_quarantined
        branch regex-matches against these when no active candidate matched."""
        return [
            p for p in self.patterns.values()
            if p.status == "active"
            and self.lifecycle_state(p.id) == "quarantined"
        ]

    def lifecycle_state(self, pattern_id: str) -> str:
        """Overlay state for a pattern; entries (or keys) absent = "active"."""
        entry = self.stats.get(pattern_id)
        if not isinstance(entry, dict):
            return "active"
        return entry.get("lifecycle", "active")

    def draftable_patterns(self) -> list[Pattern]:
        return [p for p in self.patterns.values() if p.status in ("active", "draft")]

    def active_composites(self) -> list[CompositePattern]:
        return [c for c in self.composites.values() if c.status == "active"]

    @staticmethod
    def command_was_wrong(exit_code: int, stderr: str) -> bool:
        """Distinguish 'pattern emitted wrong command' from 'skill backend rejected correct command'.

        We only want pattern stats to record failure when the COMMAND was wrong
        (binary not found, unrecognized arg, usage error). When the backend
        rejected a structurally correct command (config missing, auth missing,
        empty inbox), the pattern is fine — don't penalize it.

        This is a heuristic; we err on the side of NOT recording failures."""
        s = (stderr or "").lower()
        if "usage:" in s:
            return True
        if "unrecognized argument" in s:
            return True
        if "no such option" in s:
            return True
        if "unrecognized arguments" in s:
            return True
        if exit_code == 127:  # command not found
            return True
        if exit_code == 2 and ("usage:" in s or "error:" in s):
            return True
        return False

    def record_execution(
        self, pattern_id: str, success: bool, failure_reason: str | None = None
    ) -> None:
        entry = self.stats.get(pattern_id)
        if entry is None:
            entry = {
                "use_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_used_at": None,
                "last_failure_reason": None,
            }
            self.stats[pattern_id] = entry
        entry["use_count"] = entry.get("use_count", 0) + 1
        if success:
            entry["success_count"] = entry.get("success_count", 0) + 1
        else:
            entry["failure_count"] = entry.get("failure_count", 0) + 1
            entry["last_failure_reason"] = failure_reason
        entry["last_used_at"] = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )
        if self._cfg("lifecycle_enabled", False):
            self._apply_lifecycle_transitions(pattern_id, entry, success)
        self._write_stats()

    # ── lifecycle overlay (Stage-1 wave 2, Workstream D) ───────────────

    def register_shadow(self, pattern_id: str) -> None:
        """Enter a NEW pattern at lifecycle="shadow" with zeroed probation
        counters. Called by the distiller/Loom pipeline; nothing else yet."""
        entry = self.stats.get(pattern_id)
        if entry is None:
            entry = {
                "use_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_used_at": None,
                "last_failure_reason": None,
            }
            self.stats[pattern_id] = entry
        prev = entry.get("lifecycle", "active")
        entry["lifecycle"] = "shadow"
        entry["shadow_uses"] = 0
        entry["shadow_successes"] = 0
        self._append_audit(pattern_id, prev, "shadow", "registered_shadow")
        self._write_stats()

    def _apply_lifecycle_transitions(
        self, pattern_id: str, entry: dict, success: bool
    ) -> None:
        """State machine on top of the just-updated counters (spec item 2).

        shadow: probation is strict — any failure quarantines immediately;
        successes accumulate until shadow_promote_n, then promote iff
        shadow_successes >= shadow_promote_min_success, else quarantine.
        active: failure-only check — quarantine when the Wilson lower bound
        drops below quarantine_wilson_threshold AND n >= 5 (no demotion on
        thin evidence). quarantined: a recorded SUCCESS re-enters shadow
        (spec states line "re-entry: quarantined -> shadow via exploration" —
        a quarantined pattern only executes via exploration_quarantined),
        counting that success as the first probation point."""
        state = entry.get("lifecycle", "active")
        if state == "shadow":
            if not success:
                self._transition(pattern_id, entry, "shadow", "quarantined",
                                 "shadow_failure")
                return
            entry["shadow_uses"] = entry.get("shadow_uses", 0) + 1
            entry["shadow_successes"] = entry.get("shadow_successes", 0) + 1
            if entry["shadow_uses"] >= int(self._cfg("shadow_promote_n", 5)):
                if entry["shadow_successes"] >= int(
                    self._cfg("shadow_promote_min_success", 4)
                ):
                    self._transition(pattern_id, entry, "shadow", "active",
                                     "shadow_promoted")
                else:
                    self._transition(pattern_id, entry, "shadow",
                                     "quarantined", "shadow_promotion_failed")
        elif state == "active":
            if success:
                return
            n = entry.get("use_count", 0)
            s = entry.get("success_count", 0)
            wilson = wilson_lower(s, n, float(self._cfg("wilson_z", 1.96)))
            if n >= 5 and wilson < float(
                self._cfg("quarantine_wilson_threshold", 0.4)
            ):
                self._transition(pattern_id, entry, "active", "quarantined",
                                 "wilson_below_threshold")
        elif state == "quarantined":
            if success:
                entry["shadow_uses"] = 1
                entry["shadow_successes"] = 1
                self._transition(pattern_id, entry, "quarantined", "shadow",
                                 "exploration_recovery")

    def _transition(self, pattern_id: str, entry: dict,
                    from_state: str, to_state: str, reason: str) -> None:
        entry["lifecycle"] = to_state
        self._append_audit(pattern_id, from_state, to_state, reason)

    def _append_audit(self, pattern_id: str, from_state: str,
                      to_state: str, reason: str) -> None:
        """One JSON line per transition, lifecycle.jsonl next to the stats
        file (tests always point stats_file at a tempdir)."""
        path = self.stats_file.parent / "lifecycle.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            "pattern_id": pattern_id,
            "from": from_state,
            "to": to_state,
            "reason": reason,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")

    # ── skill-hash coupling (spec item 4, gated by skill_hash_check) ───

    @staticmethod
    def skill_binary_sha256(args_template: str) -> str | None:
        """sha256 of the binary behind a step's args_template: resolve the
        first whitespace token via shutil.which, follow symlinks, hash the
        file. None when the binary is not on PATH (or template is empty)."""
        tokens = (args_template or "").split()
        if not tokens:
            return None
        located = shutil.which(tokens[0])
        if located is None:
            return None
        try:
            resolved = Path(located).resolve()
            return hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError:
            return None

    def _check_skill_hashes(self) -> None:
        """At load: patterns carrying metadata.skill_sha256 are verified
        against the resolved CLI file. Mismatch -> forced "shadow"
        (re-probation, counters zeroed); missing binary -> "quarantined".
        Patterns WITHOUT the field are untouched (legacy). Idempotent:
        already-correct overlay states append no new audit lines."""
        dirty = False
        for p in self.patterns.values():
            expected = (p.raw.get("metadata") or {}).get("skill_sha256")
            if not expected:
                continue
            template = p.steps[0].get("args_template", "") if p.steps else ""
            actual = self.skill_binary_sha256(template)
            if actual is None:
                target, reason = "quarantined", "skill_missing"
            elif actual != expected:
                target, reason = "shadow", "skill_hash_mismatch"
            else:
                continue
            if self.lifecycle_state(p.id) == target:
                continue  # already there — no duplicate audit lines on reload
            entry = self.stats.get(p.id)
            if entry is None:
                entry = {
                    "use_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_used_at": None,
                    "last_failure_reason": None,
                }
                self.stats[p.id] = entry
            prev = entry.get("lifecycle", "active")
            if target == "shadow":
                entry["shadow_uses"] = 0
                entry["shadow_successes"] = 0
            self._transition(p.id, entry, prev, target, reason)
            dirty = True
        if dirty:
            self._write_stats()

    def _cfg(self, name: str, default):
        if self.config is None:
            return default
        return getattr(self.config, name, default)

    def _write_stats(self) -> None:
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.stats_file.with_suffix(self.stats_file.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2, sort_keys=True)
        tmp.replace(self.stats_file)
