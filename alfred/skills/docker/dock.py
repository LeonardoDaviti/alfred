#!/usr/bin/env python3
"""Docker skill CLI — MOCK backend (binding-only thesis benchmark).

Echoes a standard JSON status line WITHOUT touching a real Docker daemon, so the
benchmark can score command correctness with zero side effects and no daemon.
To target a live daemon, replace `_emit` bodies with `docker <cmd> <container>`.

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
    p = argparse.ArgumentParser(prog="dock")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("start", "stop", "restart", "remove", "logs"):
        sp = sub.add_parser(name, help=f"{name} a container")
        sp.add_argument("--container", required=True)
    sub.add_parser("ps", help="list running containers")

    args = p.parse_args(argv)

    if args.cmd == "ps":
        # Mock list; a live backend would return the real container table.
        return _emit(True, {"action": "ps", "containers": []})
    if args.cmd == "logs":
        return _emit(True, {"container": args.container, "action": "logs", "lines": []})
    return _emit(True, {"container": args.container, "action": args.cmd})


if __name__ == "__main__":
    sys.exit(main())
