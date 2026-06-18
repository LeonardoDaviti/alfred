#!/usr/bin/env python3
"""SET-1 `settings` script — a DEEP module over a mutable Pixel-style settings store.

Tiny interface (get / set / search) hiding: JSON path traversal, type inference,
range/enum validation, and error handling. The point of the script-vs-file-edit
ablation is exactly this hidden complexity — if the caller had to do it by hand
(experiment E1) it would be error-prone; the script "defines those errors out of
existence" for its caller (experiment E2).

State file resolution:  --state <path>  >  env SET1_STATE  >  ./settings_schema.json
(the canonical default, next to this script). Runners point SET1_STATE at a fresh
per-task sandbox copy so the canonical file is never mutated.

Value rules (type inferred from the existing value at the path):
  bool  -> on/off, true/false, 1/0, yes/no
  int   -> ranged 0..10 (out of range is REJECTED, not clamped)
  str   -> free text, taken as-is

Output: one JSON line {"ok",..,"data",..,"error",..,"meta"}; exit 0 ok / 1 fail / 2 args.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_STATE = HERE / "settings_schema.json"


def _state_path(arg_state):
    return Path(arg_state or os.environ.get("SET1_STATE") or DEFAULT_STATE)


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"backend": "set1"}}))
    return 0 if ok else 1


def _load(p):
    return json.loads(Path(p).read_text())


def _save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2) + "\n")


def _resolve(obj, path):
    """Return (parent_dict, leaf_key) for a dotted path, or (None, None) if missing."""
    parts = path.split(".")
    cur = obj
    for k in parts[:-1]:
        if not isinstance(cur, dict) or k not in cur:
            return None, None
        cur = cur[k]
    leaf = parts[-1]
    if not isinstance(cur, dict) or leaf not in cur:
        return None, None
    return cur, leaf


def _flatten(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, p))
        else:
            out[p] = v
    return out


def _coerce(current, raw):
    """Coerce raw string to the type of `current`. Returns (value, error|None)."""
    if isinstance(current, bool):
        s = str(raw).strip().lower()
        if s in ("on", "true", "1", "yes", "enable", "enabled"):
            return True, None
        if s in ("off", "false", "0", "no", "disable", "disabled"):
            return False, None
        return None, f"expected a boolean (on/off), got {raw!r}"
    if isinstance(current, int):
        try:
            n = int(str(raw).strip())
        except ValueError:
            return None, f"expected an integer 0-10, got {raw!r}"
        if not (0 <= n <= 10):
            return None, f"value {n} out of range 0-10"
        return n, None
    # string / free-text
    return str(raw), None


def main(argv=None):
    p = argparse.ArgumentParser(prog="settings")
    p.add_argument("--state", default=None, help="state file (else SET1_STATE env, else canonical)")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get"); g.add_argument("path")
    s = sub.add_parser("set"); s.add_argument("path"); s.add_argument("value")
    sr = sub.add_parser("search"); sr.add_argument("query")
    args = p.parse_args(argv)

    state_file = _state_path(args.state)
    if not state_file.is_file():
        return _emit(False, error={"message": f"state file not found: {state_file}"})
    state = _load(state_file)

    if args.cmd == "get":
        parent, leaf = _resolve(state, args.path)
        if parent is None:
            return _emit(False, error={"message": f"unknown path: {args.path}"})
        return _emit(True, {"path": args.path, "value": parent[leaf]})

    if args.cmd == "set":
        parent, leaf = _resolve(state, args.path)
        if parent is None:
            return _emit(False, error={"message": f"unknown path: {args.path}"})
        value, err = _coerce(parent[leaf], args.value)
        if err:
            return _emit(False, error={"message": err, "path": args.path})
        parent[leaf] = value
        _save(state_file, state)
        return _emit(True, {"path": args.path, "value": value})

    if args.cmd == "search":
        q = args.query.lower()
        flat = _flatten(state)
        hits = {path: val for path, val in flat.items()
                if q in path.lower() or q in path.split(".")[-1].lower()}
        return _emit(True, {"query": args.query, "matches": hits})

    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
