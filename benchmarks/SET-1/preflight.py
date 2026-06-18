#!/usr/bin/env python3
"""SET-1 oracle pre-flight — runs BEFORE any model.

For each task: build a fresh sandbox = initial state, apply the gold values via the
`settings set` script, then run the oracle. Every task MUST pass. This proves
(a) the gold is achievable through the real script, (b) the script's validation
accepts the gold values, and (c) the oracle passes when it should. A broken oracle
that fails everyone is the worst silent failure; this rules it out.

Usage:  python SET-1/preflight.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANON = HERE / "settings_schema.json"
_TF = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "tasks.json"
if not _TF.is_absolute():
    _TF = HERE / _TF.name
TASKS = json.loads(_TF.read_text())


def flatten(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        p = f"{prefix}.{k}" if prefix else k
        out.update(flatten(v, p) if isinstance(v, dict) else {p: v})
    return out


def unflatten(flat):
    root = {}
    for path, val in flat.items():
        parts = path.split(".")
        cur = root
        for k in parts[:-1]:
            cur = cur.setdefault(k, {})
        cur[parts[-1]] = val
    return root


def main():
    canonical = json.loads(CANON.read_text())
    passed = 0
    for t in TASKS:
        # fresh sandbox = canonical + overrides
        flat = flatten(canonical); flat.update(t.get("initial", {}))
        sb = Path(tempfile.mkstemp(prefix=f"set1-pre-{t['id']}-", suffix=".json")[1])
        sb.write_text(json.dumps(unflatten(flat), indent=2) + "\n")
        env = {"SET1_STATE": str(sb)}
        # apply gold via the real script
        ok = True
        for path, val in t["gold"].items():
            r = subprocess.run([sys.executable, str(HERE / "settings.py"), "set", path, str(val)],
                               capture_output=True, text=True, env={**__import__("os").environ, **env})
            if r.returncode != 0:
                ok = False; print(f"  {t['id']} set {path}={val} FAILED: {r.stdout.strip()}"); break
        # oracle
        r = subprocess.run([sys.executable, str(HERE / "oracle.py"), "--final", str(sb), "--task-id", t["id"],
                            "--task-file", str(_TF)], capture_output=True, text=True)
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
