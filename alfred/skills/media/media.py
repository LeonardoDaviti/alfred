#!/usr/bin/env python3
"""Media skill CLI — generic OS media control (playerctl) — MOCK backend.

Echoes a JSON status line WITHOUT touching a real player, for binding-only
scoring. To target a live session, wire subcommands to `playerctl
play/pause/next/previous` and `playerctl volume <0-1>`.

Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="media")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("play"); sub.add_parser("pause")
    sub.add_parser("next"); sub.add_parser("previous")
    vol = sub.add_parser("volume"); vol.add_argument("--level", required=True, type=int)
    args = p.parse_args(argv)

    if args.cmd in ("play", "pause", "next", "previous"):
        return _emit(True, {"action": args.cmd})
    if args.cmd == "volume":
        return _emit(True, {"action": "volume", "level": args.level})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
