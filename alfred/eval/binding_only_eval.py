"""Binding-only eval — routing is ASSUMED PERFECT.

Isolates the reflexer's command-generation (binding) from routing: for every task
we hand the reflexer the GOLD pattern directly (no router, no arbiter) and check
whether the generated command contains the gold discriminating tokens
(`gold_command_contains`). This answers "if routing were always correct, how good
is binding?" — the ceiling the routing pipeline can never exceed.

No execution, no network, ~/.alfred read-only (stats copied), record_execution
never called. Atoms only (composites have no single gold command).

Usage:
  .venv-eval/bin/python -m alfred.eval.binding_only_eval                 # all expansion task files
  .venv-eval/bin/python -m alfred.eval.binding_only_eval tasksA.json tasksB.json
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from alfred.eval.routing_ablation import load_store
from alfred.runtime.llm_client import LLMClient

DEFAULT_TASKS = [
    "alfred/eval/expansion_tasks.json",
    "alfred/eval/expansion_generated_queries.json",
    "alfred/eval/expansion_tasks_exec.json",
    "alfred/eval/expansion_tasks_cross.json",
    "alfred/eval/expansion_tasks_phase2.json",
    "alfred/eval/expansion_tasks_phase2_cross.json",
]

task_files = sys.argv[1:] or DEFAULT_TASKS
tasks = []
for tf in task_files:
    p = Path(tf)
    if p.is_file():
        tasks.extend(json.loads(p.read_text()))

store = load_store(Path(tempfile.mkdtemp(prefix="alfred-bind-")))
llm = LLMClient(os.environ.get("ALFRED_LLM_URL", "http://127.0.0.1:8003/v1"),
                os.environ.get("ALFRED_LLM_MODEL", "ministral-3-3b"), timeout_s=30)

# Atoms with gold tokens and a resolvable gold pattern.
eligible = [t for t in tasks
            if t.get("gold_command_contains")
            and t.get("expected_pattern_id") in store.patterns]

rows = []
for t in eligible:
    pat = store.patterns[t["expected_pattern_id"]]
    try:
        cmd, ms = llm.generate_command(t["query"], pat)
    except Exception as e:
        cmd, ms = f"<{type(e).__name__}:{e}>"[:80], 0
    gold = t["gold_command_contains"]
    missing = [g for g in gold if g.lower() not in cmd.lower()]
    rows.append({"pid": pat.id, "domain": t.get("domain", ""), "query": t["query"],
                 "gold": gold, "missing": missing, "cmd": cmd, "ok": not missing})

n = len(rows)
ok = sum(r["ok"] for r in rows)
print(f"== binding-only (routing assumed correct) ==  model={os.environ.get('ALFRED_LLM_MODEL','ministral-3-3b')}")
print(f"tasks (atoms w/ gold tokens): {n}  from {len([f for f in task_files if Path(f).is_file()])} files")
print(f"binding accuracy: {ok}/{n} = {100*ok/max(1,n):.1f}%\n")

print("per domain:")
by = defaultdict(lambda: [0, 0])
for r in rows:
    by[r["domain"]][0] += r["ok"]; by[r["domain"]][1] += 1
for d in sorted(by):
    o, tot = by[d]
    print(f"  {d:16s} {o}/{tot} = {100*o/tot:.1f}%")

# miss taxonomy: which exact gold token was most often missing
tok_miss = defaultdict(int)
for r in rows:
    for m in r["missing"]:
        tok_miss[m] += 1
print("\nmost-missed gold tokens:")
for tok, c in sorted(tok_miss.items(), key=lambda x: -x[1])[:12]:
    print(f"  {c:3d}x  {tok!r}")

print(f"\nbinding misses ({n-ok}):")
for r in rows:
    if not r["ok"]:
        print(f"  [{r['domain']:14s}] {r['query'][:44]:46s} MISSING {r['missing']}")
        print(f"                   -> {r['cmd'][:80]}")
