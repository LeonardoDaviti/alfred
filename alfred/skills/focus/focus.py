#!/usr/bin/env python3
"""Focus skill CLI — named focus profiles (work/sleep/personal) — MOCK backend.

Echoes JSON; no side effects. A real backend would drive the desktop's
do-not-disturb + notification policy per profile.
Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="focus")
    sub = p.add_subparsers(dest="cmd", required=True)
    on = sub.add_parser("on"); on.add_argument("--mode", required=True)
    sub.add_parser("off"); sub.add_parser("status")
    args = p.parse_args(argv)

    if args.cmd == "on":
        return _emit(True, {"focus": "on", "mode": args.mode})
    if args.cmd == "off":
        return _emit(True, {"focus": "off"})
    if args.cmd == "status":
        return _emit(True, {"focus": "off", "mode": None})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
