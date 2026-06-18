#!/usr/bin/env python3
"""SET-2 `settings` script — Android-realistic, deliberately UNFORGIVING.

Mirrors `adb shell settings`: three namespaces (system / secure / global) and
`put`/`get`/`list`. Like real Android, `put` is **permissive** — it validates the
namespace but NOT the key name or the value encoding. So a wrong namespace, a wrong
key, or a wrong-scale value all "succeed" silently and simply fail to achieve the
goal. That realism is the point: a free-form model must KNOW the right namespace +
key + encoding (brightness 0-255, screen_off_timeout in milliseconds, location_mode
as an enum 0-3, booleans as 0/1); it cannot reliably guess them. A distilled pattern
encodes them.

State file: --state > env SET2_STATE > ./settings_schema.json (canonical, by script).
Output: one JSON line {"ok",..,"data",..,"error",..,"meta"}; exit 0/1/2.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_STATE = HERE / "settings_schema.json"
NAMESPACES = ("system", "secure", "global")


def _state_path(arg_state):
    return Path(arg_state or os.environ.get("SET2_STATE") or DEFAULT_STATE)


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"backend": "set2-android"}}))
    return 0 if ok else 1


def _load(p): return json.loads(Path(p).read_text())
def _save(p, o): Path(p).write_text(json.dumps(o, indent=2) + "\n")


def _coerce(raw):
    """Android stores strings, but we keep ints for numeric values for clean diffing."""
    s = str(raw).strip()
    try:
        return int(s)
    except ValueError:
        return s


def main(argv=None):
    p = argparse.ArgumentParser(prog="settings")
    p.add_argument("--state", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get"); g.add_argument("namespace"); g.add_argument("key")
    pu = sub.add_parser("put"); pu.add_argument("namespace"); pu.add_argument("key"); pu.add_argument("value")
    li = sub.add_parser("list"); li.add_argument("namespace")
    args = p.parse_args(argv)

    state_file = _state_path(args.state)
    if not state_file.is_file():
        return _emit(False, error={"message": f"state file not found: {state_file}"})
    state = _load(state_file)

    if args.cmd in ("get", "put", "list") and args.namespace not in NAMESPACES:
        return _emit(False, error={"message": f"unknown namespace '{args.namespace}' (use: {', '.join(NAMESPACES)})"})

    if args.cmd == "get":
        ns = state.setdefault(args.namespace, {})
        return _emit(True, {"namespace": args.namespace, "key": args.key, "value": ns.get(args.key)})

    if args.cmd == "put":
        # PERMISSIVE on purpose (like real Android): no key/value validation.
        ns = state.setdefault(args.namespace, {})
        ns[args.key] = _coerce(args.value)
        _save(state_file, state)
        return _emit(True, {"namespace": args.namespace, "key": args.key, "value": ns[args.key]})

    if args.cmd == "list":
        return _emit(True, {"namespace": args.namespace, "values": state.get(args.namespace, {})})

    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
