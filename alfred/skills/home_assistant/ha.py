#!/usr/bin/env python3
"""Home Assistant skill CLI — MOCK backend (binding-only thesis benchmark).

Echoes a standard JSON status line WITHOUT touching a real Home Assistant
instance, so the benchmark can score command correctness with zero side effects
and no network. To target a live instance, replace `_mock_call` with a REST call
to `${HASS_URL}/api/services/<domain>/<service>` using a long-lived token.

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
    p = argparse.ArgumentParser(prog="ha")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("call", help="call a service on an entity")
    c.add_argument("--domain", required=True)
    c.add_argument("--service", required=True)
    c.add_argument("--entity", required=True)
    c.add_argument("--temp", type=float)
    c.add_argument("--brightness", type=int)

    s = sub.add_parser("state", help="read an entity's state")
    s.add_argument("--entity", required=True)

    sc = sub.add_parser("scene", help="activate a scene")
    sc.add_argument("--name", required=True)

    args = p.parse_args(argv)

    if args.cmd == "call":
        data = {"domain": args.domain, "service": args.service, "entity": args.entity}
        if args.temp is not None:
            data["temperature"] = args.temp
        if args.brightness is not None:
            data["brightness"] = args.brightness
        return _emit(True, data)
    if args.cmd == "state":
        # Mock state; a live backend would return the real attributes.
        return _emit(True, {"entity": args.entity, "state": "unknown", "attributes": {}})
    if args.cmd == "scene":
        return _emit(True, {"scene": args.name, "activated": True})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
