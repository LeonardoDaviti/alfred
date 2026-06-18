#!/usr/bin/env python3
"""Browser skill CLI — drive the user's real browser — MOCK backend here.

Binding-only mock: echoes JSON, runs no browser. The REAL backend (see
SKILL.md) uses Playwright `connect_over_cdp` to attach to the user's existing
Chromium/Brave/Chrome (preserving logins), with raw CDP (pychrome) as the
Raspberry-Pi fallback. The CLI surface below is identical for both backends so
binding scores transfer unchanged.

Output: {"ok",..,"data",..,"error",..,"meta":{"mock":true}}; exit 0/2.
"""
import argparse
import json
import sys


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error, "meta": {"mock": True, "backend": "mock"}}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="browser")
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open"); o.add_argument("--url", required=True)
    s = sub.add_parser("search"); s.add_argument("--query", required=True); s.add_argument("--engine", default="google")
    sub.add_parser("read-text").add_argument("--selector", default=None)
    c = sub.add_parser("click"); c.add_argument("--target", required=True)
    t = sub.add_parser("type"); t.add_argument("--selector", required=True); t.add_argument("--text", required=True)
    sc = sub.add_parser("screenshot"); sc.add_argument("--path", default="/tmp/_browser.png"); sc.add_argument("--full-page", action="store_true")
    sub.add_parser("tabs")
    ts = sub.add_parser("tab-switch"); ts.add_argument("--id", required=True)
    args = p.parse_args(argv)

    if args.cmd == "open":
        return _emit(True, {"action": "open", "url": args.url})
    if args.cmd == "search":
        return _emit(True, {"action": "search", "query": args.query, "engine": args.engine})
    if args.cmd == "read-text":
        return _emit(True, {"action": "read-text", "selector": args.selector, "text": "[mock page text]"})
    if args.cmd == "click":
        return _emit(True, {"action": "click", "target": args.target})
    if args.cmd == "type":
        return _emit(True, {"action": "type", "selector": args.selector, "text": args.text})
    if args.cmd == "screenshot":
        return _emit(True, {"action": "screenshot", "path": args.path, "full_page": args.full_page})
    if args.cmd == "tabs":
        return _emit(True, {"action": "tabs", "tabs": []})
    if args.cmd == "tab-switch":
        return _emit(True, {"action": "tab-switch", "id": args.id})
    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
