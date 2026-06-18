#!/usr/bin/env python3
"""Clock skill CLI — unified timer + alarm + world-clock.

This is the ONE skill built to ACTUALLY fire. Two backends:
  * MOCK (default): echoes a JSON status line, no side effects — used by the
    binding-only benchmark (we score command correctness).
  * REAL (env ALFRED_CLOCK_REAL=1): schedules via `systemd-run --user`
    (timers: --on-active; alarms: --on-calendar) so they genuinely go off,
    and lists/cancels via `systemctl --user`. Survives logout via the user
    manager. No root, no cron file editing.

All commands print ONE JSON line:
    {"ok": bool, "data": {...}|null, "error": null|{...}, "meta": {...}}
Exit 0 on success, 2 on bad args. Python standard library only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

REAL = os.environ.get("ALFRED_CLOCK_REAL") == "1"
UNIT_PREFIX = "alfred-clock-"


def _emit(ok, data=None, error=None):
    print(json.dumps({"ok": ok, "data": data, "error": error,
                      "meta": {"mock": not REAL, "backend": "systemd-run" if REAL else "mock"}}))
    return 0 if ok else 1


def _duration_to_seconds(text):
    """'10m' -> 600, '90s' -> 90, '1h30m' -> 5400, bare int -> minutes."""
    text = text.strip().lower()
    if text.isdigit():
        return int(text) * 60
    total, found = 0, False
    for num, unit in re.findall(r"(\d+)\s*([hms])", text):
        found = True
        total += int(num) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total if found else None


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main(argv=None):
    p = argparse.ArgumentParser(prog="clock")
    sub = p.add_subparsers(dest="cmd", required=True)

    timer = sub.add_parser("timer", help="countdown timers")
    tsub = timer.add_subparsers(dest="op", required=True)
    tstart = tsub.add_parser("start"); tstart.add_argument("--duration", required=True)
    tstart.add_argument("--label", default="Timer")
    tsub.add_parser("cancel"); tsub.add_parser("list")

    alarm = sub.add_parser("alarm", help="absolute-time alarms")
    asub = alarm.add_subparsers(dest="op", required=True)
    aset = asub.add_parser("set"); aset.add_argument("--time", required=True)
    aset.add_argument("--label", default="Alarm")
    asub.add_parser("cancel"); asub.add_parser("list")

    now = sub.add_parser("now", help="current/world time"); now.add_argument("--city", default=None)

    args = p.parse_args(argv)

    if args.cmd == "timer":
        if args.op == "start":
            secs = _duration_to_seconds(args.duration)
            if secs is None or secs <= 0:
                return _emit(False, error={"message": f"bad duration: {args.duration!r}"})
            if REAL:
                r = _run(["systemd-run", "--user", f"--on-active={secs}",
                          f"--unit={UNIT_PREFIX}timer-{os.getpid()}",
                          "notify-send", "⏰ Timer", args.label])
                if r.returncode != 0:
                    return _emit(False, error={"message": r.stderr.strip()})
            return _emit(True, {"kind": "timer", "duration": args.duration, "seconds": secs, "label": args.label})
        if args.op == "cancel":
            if REAL:
                _run(["bash", "-c", f"systemctl --user stop '{UNIT_PREFIX}timer-*' 2>/dev/null; true"])
            return _emit(True, {"kind": "timer", "op": "cancel"})
        if args.op == "list":
            data = {"kind": "timer", "timers": []}
            if REAL:
                r = _run(["systemctl", "--user", "list-timers", f"{UNIT_PREFIX}timer-*", "--no-legend"])
                data["timers"] = [l for l in r.stdout.splitlines() if l.strip()]
            return _emit(True, data)

    if args.cmd == "alarm":
        if args.op == "set":
            cal = args.time  # real backend accepts systemd OnCalendar; mock just echoes
            if REAL:
                r = _run(["systemd-run", "--user", f"--on-calendar=*-*-* {args.time}:00",
                          f"--unit={UNIT_PREFIX}alarm-{os.getpid()}",
                          "notify-send", "⏰ Alarm", args.label])
                if r.returncode != 0:
                    return _emit(False, error={"message": r.stderr.strip()})
            return _emit(True, {"kind": "alarm", "time": cal, "label": args.label})
        if args.op == "cancel":
            if REAL:
                _run(["bash", "-c", f"systemctl --user stop '{UNIT_PREFIX}alarm-*' 2>/dev/null; true"])
            return _emit(True, {"kind": "alarm", "op": "cancel"})
        if args.op == "list":
            data = {"kind": "alarm", "alarms": []}
            if REAL:
                r = _run(["systemctl", "--user", "list-timers", f"{UNIT_PREFIX}alarm-*", "--no-legend"])
                data["alarms"] = [l for l in r.stdout.splitlines() if l.strip()]
            return _emit(True, data)

    if args.cmd == "now":
        import datetime
        return _emit(True, {"kind": "now", "city": args.city,
                            "time": datetime.datetime.now().strftime("%H:%M:%S")})

    return _emit(False, error={"message": "unknown command"})


if __name__ == "__main__":
    sys.exit(main())
