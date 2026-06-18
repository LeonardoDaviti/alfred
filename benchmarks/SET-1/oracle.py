#!/usr/bin/env python3
"""SET-1 oracle — the single success checker (invariant I3).

Success is defined by the END STATE, not the commands used: a task passes iff
  (a) every gold path == its gold value in the final state, AND
  (b) NO non-gold leaf changed from the task's initial state (no collateral edits).
This catches both "mechanism right / outcome wrong" (a) and over-editing (b).

Usage:
  python oracle.py --final <state.json> --task-id t07
  [--task-file SET-1/tasks.json] [--canonical SET-1/settings_schema.json]
Prints one JSON line {pass, wrong[], collateral[]}; exit 0 if pass else 1.
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
        if isinstance(v, dict):
            out.update(_flatten(v, p))
        else:
            out[p] = v
    return out


def initial_state(canonical, overrides):
    """canonical (flattened) with task overrides applied."""
    flat = _flatten(canonical)
    flat.update(overrides or {})
    return flat


def evaluate(final, canonical, task):
    fin = _flatten(final)
    init = initial_state(canonical, task.get("initial", {}))
    gold = task["gold"]
    wrong = [{"path": p, "want": v, "got": fin.get(p)} for p, v in gold.items() if fin.get(p) != v]
    collateral = [{"path": p, "from": init[p], "to": fin.get(p)}
                  for p in init
                  if p not in gold and fin.get(p) != init[p]]
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
    final = json.loads(Path(a.final).read_text())
    canonical = json.loads(Path(a.canonical).read_text())
    res = evaluate(final, canonical, tasks[a.task_id])
    print(json.dumps(res))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
