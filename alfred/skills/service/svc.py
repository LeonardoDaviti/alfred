#!/usr/bin/env python3
"""Service (systemd) skill CLI — MOCK backend (binding-only thesis benchmark).

Echoes a standard JSON status line WITHOUT touching real systemd, so the
benchmark can score command correctness with zero side effects and no privilege.
To target a live system, replace `_emit` bodies with `systemctl <cmd> <unit>`.

All commands print ONE JSON line on stdout:
    {"ok": bool, "data": {...}|null, "error": null|{...}, "meta": {"mock": true}}
Exit 0 on success, 2 on bad arguments. Python standard library only.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="svc")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("start", "stop", "restart", "status", "enable", "disable"):
        sp = sub.add_parser(name, help=f"{name} a systemd unit")
        sp.add_argument("--unit", required=True)

    args = p.parse_args(argv)

    if args.cmd == "status":
        # Mock status; a live backend would return the real ActiveState.
        return _emit(True, {"unit": args.unit, "action": "status", "active_state": "unknown"})
    return _emit(True, {"unit": args.unit, "action": args.cmd})


if __name__ == "__main__":
    sys.exit(main())
