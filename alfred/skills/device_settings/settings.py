#!/usr/bin/env python3
"""Device-settings skill CLI — connectivity + UI toggles — MOCK backend.

All toggles share `--state on|off`; the subcommand is the discriminator.
Echoes JSON; no side effects. A real backend would use nmcli (wifi),
bluetoothctl/rfkill (bluetooth/airplane), and the desktop's DND/theme APIs.
Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys

TOGGLES = ["wifi", "bluetooth", "airplane", "dnd", "dark-mode", "light-mode"]


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="settings")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in TOGGLES:
        sp = sub.add_parser(name)
        sp.add_argument("--state", required=True, choices=["on", "off"])
    args = p.parse_args(argv)

    if args.cmd in TOGGLES:
        return _emit(True, {"setting": args.cmd, "state": args.state})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
