#!/usr/bin/env python3
"""System (local machine) skill CLI — MOCK backend (binding-only thesis benchmark).

Echoes a standard JSON status line WITHOUT touching real hardware, so the
benchmark can score command correctness with zero side effects. To target a live
machine, wire the subcommands to pactl/wpctl, brightnessctl, loginctl, etc.

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
    p = argparse.ArgumentParser(prog="sys")
    sub = p.add_subparsers(dest="cmd", required=True)

    vol = sub.add_parser("volume", help="control audio volume")
    vsub = vol.add_subparsers(dest="direction", required=True)
    vsub.add_parser("up", help="volume up")
    vsub.add_parser("down", help="volume down")
    vsub.add_parser("mute", help="mute/unmute")
    vset = vsub.add_parser("set", help="set volume to a level")
    vset.add_argument("--level", required=True, type=int)

    bri = sub.add_parser("brightness", help="control screen brightness")
    bsub = bri.add_subparsers(dest="direction", required=True)
    bset = bsub.add_parser("set", help="set brightness to a level")
    bset.add_argument("--level", required=True, type=int)

    sub.add_parser("lock", help="lock the screen")
    sub.add_parser("suspend", help="suspend the machine")

    args = p.parse_args(argv)

    if args.cmd == "volume":
        data = {"action": "volume", "direction": args.direction}
        if args.direction == "set":
            data["level"] = args.level
        return _emit(True, data)
    if args.cmd == "brightness":
        return _emit(True, {"action": "brightness", "direction": args.direction, "level": args.level})
    if args.cmd in ("lock", "suspend"):
        return _emit(True, {"action": args.cmd})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
