#!/usr/bin/env python3
"""Call skill CLI — telephony actions — MOCK backend (no real telephony).

Echoes JSON; no side effects. A real backend would bridge to a phone link
(e.g. KDE Connect / GSConnect, or a SIP client).
Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="call")
    sub = p.add_subparsers(dest="cmd", required=True)
    dial = sub.add_parser("dial"); dial.add_argument("--to", required=True)
    sub.add_parser("redial"); sub.add_parser("hangup"); sub.add_parser("answer")
    args = p.parse_args(argv)

    if args.cmd == "dial":
        return _emit(True, {"action": "dial", "to": args.to})
    if args.cmd in ("redial", "hangup", "answer"):
        return _emit(True, {"action": args.cmd})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
