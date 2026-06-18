#!/usr/bin/env python3
"""App skill CLI — launch/close/switch applications — MOCK backend.

Echoes JSON; no side effects. A real backend would use the desktop launcher
(gtk-launch / xdg-open / wmctrl) to open, close, and focus windows.
Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="app")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("open", "close", "switch"):
        sp = sub.add_parser(name); sp.add_argument("--name", required=True)
    args = p.parse_args(argv)

    if args.cmd in ("open", "close", "switch"):
        return _emit(True, {"action": args.cmd, "name": args.name})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
