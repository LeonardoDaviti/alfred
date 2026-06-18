#!/usr/bin/env python3
"""Spotify skill CLI — MOCK backend (binding-only thesis benchmark).

Echoes a standard JSON status line WITHOUT touching a real device or the Spotify
Web API, so the benchmark scores command correctness with zero side effects and
no network. To go live, replace each handler with a call to the Web API
(`/me/player/play`, `/me/player/pause`, `/search`, …) using an OAuth token.

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
    p = argparse.ArgumentParser(prog="spotify")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("play")
    pl.add_argument("--track")
    sub.add_parser("pause")
    sub.add_parser("next")
    sub.add_parser("previous")

    se = sub.add_parser("search")
    se.add_argument("--query", required=True)

    ad = sub.add_parser("add")
    ad.add_argument("--track", required=True)
    ad.add_argument("--playlist", required=True)

    vo = sub.add_parser("volume")
    vo.add_argument("--level", type=int, required=True)

    args = p.parse_args(argv)

    if args.cmd == "play":
        return _emit(True, {"action": "play", "track": args.track})
    if args.cmd in ("pause", "next", "previous"):
        return _emit(True, {"action": args.cmd})
    if args.cmd == "search":
        return _emit(True, {"action": "search", "query": args.query, "results": []})
    if args.cmd == "add":
        return _emit(True, {"action": "add", "track": args.track, "playlist": args.playlist})
    if args.cmd == "volume":
        return _emit(True, {"action": "volume", "level": args.level})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
