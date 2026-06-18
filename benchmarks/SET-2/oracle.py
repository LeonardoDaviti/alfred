#!/usr/bin/env python3
"""SET-2 oracle — end-state checker (same contract as SET-1).

Pass iff every gold path == gold value in the final state, AND no non-gold leaf
changed from the task's initial state. Paths are `namespace.key`.

Usage: python oracle.py --final <state.json> --task-id s01 [--task-file ...] [--canonical ...]
Prints {pass, wrong[], collateral[]}; exit 0 if pass else 1.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _flatten(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        p = f"{prefix}.{k}" if prefix else k
        out.update(_flatten(v, p) if isinstance(v, dict) else {p: v})
    return out


def initial_state(canonical, overrides):
    flat = _flatten(canonical); flat.update(overrides or {}); return flat


def evaluate(final, canonical, task):
    fin = _flatten(final)
    init = initial_state(canonical, task.get("initial", {}))
    gold = task["gold"]
    wrong = [{"path": p, "want": v, "got": fin.get(p)} for p, v in gold.items() if fin.get(p) != v]
    collateral = [{"path": p, "from": init[p], "to": fin.get(p)}
                  for p in init if p not in gold and fin.get(p) != init[p]]
    return {"pass": not wrong and not collateral, "wrong": wrong, "collateral": collateral}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oracle")
    ap.add_argument("--final", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--task-file", default=str(HERE / "tasks.json"))
    ap.add_argument("--canonical", default=str(HERE / "settings_schema.json"))
    a = ap.parse_args(argv)
    tasks = {t["id"]: t for t in json.loads(Path(a.task_file).read_text())}
    if a.task_id not in tasks:
        print(json.dumps({"pass": False, "error": f"unknown task {a.task_id}"})); return 2
    res = evaluate(json.loads(Path(a.final).read_text()), json.loads(Path(a.canonical).read_text()), tasks[a.task_id])
    print(json.dumps(res)); return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
