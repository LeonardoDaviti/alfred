#!/usr/bin/env python3
"""SET-2 oracle pre-flight. For each task: fresh sandbox = initial, apply gold via the
real `settings put <ns> <key> <value>`, then oracle. All must pass — proves the gold is
reachable through the script and the oracle is sound. Usage: python SET-2/preflight.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANON = HERE / "settings_schema.json"
TASKS = json.loads((HERE / "tasks.json").read_text())


def flatten(o, p=""):
    out = {}
    for k, v in o.items():
        path = f"{p}.{k}" if p else k
        out.update(flatten(v, path) if isinstance(v, dict) else {path: v})
    return out


def unflatten(flat):
    root = {}
    for path, val in flat.items():
        parts = path.split("."); cur = root
        for k in parts[:-1]:
            cur = cur.setdefault(k, {})
        cur[parts[-1]] = val
    return root


def main():
    canonical = json.loads(CANON.read_text()); passed = 0
    for t in TASKS:
        flat = flatten(canonical); flat.update(t.get("initial", {}))
        sb = Path(tempfile.mkstemp(prefix=f"set2-pre-{t['id']}-", suffix=".json")[1])
        sb.write_text(json.dumps(unflatten(flat), indent=2) + "\n")
        env = {**os.environ, "SET2_STATE": str(sb)}
        ok = True
        for path, val in t["gold"].items():
            ns, key = path.split(".", 1)
            r = subprocess.run([sys.executable, str(HERE / "settings.py"), "put", ns, key, str(val)],
                               capture_output=True, text=True, env=env)
            if r.returncode != 0:
                ok = False; print(f"  {t['id']} put {ns} {key}={val} FAILED: {r.stdout.strip()}"); break
        r = subprocess.run([sys.executable, str(HERE / "oracle.py"), "--final", str(sb), "--task-id", t["id"]],
                           capture_output=True, text=True)
        verdict = json.loads(r.stdout or "{}")
        good = ok and verdict.get("pass")
        passed += bool(good)
        if not good:
            print(f"  [FAIL] {t['id']} {t['query']!r} -> {verdict}")
        sb.unlink(missing_ok=True)
    print(f"\npreflight: {passed}/{len(TASKS)} tasks achievable + oracle-valid")
    return 0 if passed == len(TASKS) else 1


if __name__ == "__main__":
    sys.exit(main())
