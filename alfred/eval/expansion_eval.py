"""Expansion-skill eval (frozen-core + expansion strategy).

Two studies, selected by ALFRED_EVAL_MODE:

  skills  (default) — route+bind the new-skill tasks against a MERGED store
                      (live core patterns + alfred/eval/expansion_patterns/).
                      Faithful to shipped `alfred chat`: full semantic stack +
                      tail/margin arbiter. Binding-only (no execution, no network,
                      never calls record_execution; ~/.alfred is read-only).

  growth          — library-growth degradation study: route the ORIGINAL 303
                      creative queries against (a) core-only and (b) merged store,
                      and report whether adding 30 new patterns degrades routing
                      of the existing library (and which queries leak to new ids).

Usage:
  .venv-eval/bin/python -m alfred.eval.expansion_eval                      # skills, canonical tasks
  ALFRED_EVAL_TASKS=alfred/eval/expansion_generated_queries.json \\
      .venv-eval/bin/python -m alfred.eval.expansion_eval                  # skills, creative tasks
  ALFRED_EVAL_MODE=growth .venv-eval/bin/python -m alfred.eval.expansion_eval
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from alfred.eval.routing_ablation import ALFRED_HOME
from alfred.runtime.embedder import SentenceTransformerBackend, build_pattern_index
from alfred.runtime.llm_client import LLMClient
from alfred.runtime.reflexer import build_arbiter_prompt, parse_arbiter_reply
from alfred.runtime.router import Router
from alfred.runtime.store import PatternStore
from alfred.runtime.types import AlfredConfig

EXPANSION_DIR = Path("alfred/eval/expansion_patterns")
EMB_MODEL = os.environ.get("ALFRED_EMB", "sentence-transformers/all-MiniLM-L6-v2")


def _build_store(tmp: Path, include_expansion: bool) -> PatternStore:
    """Copy core pattern files (read-only) + optionally expansion files into one
    tmp dir; copy stats so nothing writes back to ~/.alfred."""
    pdir = tmp / ("merged" if include_expansion else "core")
    pdir.mkdir(parents=True, exist_ok=True)
    for f in sorted((ALFRED_HOME / "patterns").glob("*.json")):
        shutil.copyfile(f, pdir / f.name)
    if include_expansion:
        for f in sorted(EXPANSION_DIR.glob("*.json")):
            shutil.copyfile(f, pdir / f"exp_{f.name}")
    stats_src = ALFRED_HOME / "stats" / "stats.json"
    stats_copy = tmp / f"stats_{pdir.name}.json"
    if stats_src.is_file():
        shutil.copyfile(stats_src, stats_copy)
    else:
        stats_copy.write_text("{}")
    return PatternStore(pdir, stats_copy, config=None)


def _make_router(store: PatternStore, tmp: Path, tag: str):
    cfg = AlfredConfig(
        position_weighted=True, margin_gating=True, score_v3=True,
        embedding_routing=True, semantic_rescue=True, tail_arbiter=True,
        confidence_threshold=0.45, embedding_cache=str(tmp / f"emb_{tag}.json"),
    )
    backend = SentenceTransformerBackend(EMB_MODEL)
    router = Router(store, cfg, embedder=backend)
    router._pattern_index = build_pattern_index(store, backend,
                                                cache_path=tmp / f"emb_{tag}.json")
    return router


_llm = None


def _llm_client():
    global _llm
    if _llm is None:
        _llm = LLMClient(os.environ.get("ALFRED_LLM_URL", "http://127.0.0.1:8003/v1"),
                         os.environ.get("ALFRED_LLM_MODEL", "ministral-3-3b"), timeout_s=30)
    return _llm


def _run_arbiter(store, query, cand_ids):
    cands = [store.patterns[p] for p in cand_ids if p in store.patterns]
    if not cands:
        return "thinker"
    try:
        reply, _ = _llm_client().chat(build_arbiter_prompt(query, cands), max_tokens=4)
    except Exception:
        return "thinker"
    idx = parse_arbiter_reply(reply, len(cands))
    return cands[idx].id if idx is not None else "thinker"


def route(store, router, query):
    for c in store.active_composites():
        compiled = store.composite_triggers.get(c.id)
        if compiled is not None and compiled.search(query):
            return c.id
    d = router.route(query)
    if d.route == "reflexer":
        if d.arbiter_candidates:
            return _run_arbiter(store, query, d.arbiter_candidates)
        return d.pattern_id
    return "thinker"


def expected_of(t):
    return t["expected_pattern_id"] if t["expected_route"] in ("reflexer", "composite") \
        else "thinker"


def run_skills():
    tasks_path = os.environ.get("ALFRED_EVAL_TASKS", "alfred/eval/expansion_tasks.json")
    tasks = json.loads(Path(tasks_path).read_text())
    tmp = Path(tempfile.mkdtemp(prefix="alfred-exp-"))
    store = _build_store(tmp, include_expansion=True)
    router = _make_router(store, tmp, "merged")
    llm = _llm_client()

    rows = []
    for t in tasks:
        exp = expected_of(t)
        pred = route(store, router, t["query"])
        routed_ok = pred == exp
        bind_ok, cmd = None, ""
        gold = t.get("gold_command_contains")
        if gold and pred in store.patterns:
            try:
                cmd, _ = llm.generate_command(t["query"], store.patterns[pred])
                bind_ok = all(g.lower() in cmd.lower() for g in gold)
            except Exception as e:
                cmd, bind_ok = f"<{type(e).__name__}>"[:60], False
        rows.append({**t, "exp": exp, "pred": pred, "routed_ok": routed_ok,
                     "bind_ok": bind_ok, "cmd": cmd})

    n = len(rows)
    rok = sum(r["routed_ok"] for r in rows)
    brows = [r for r in rows if r["bind_ok"] is not None]
    bok = sum(r["bind_ok"] for r in brows)
    e2e = sum(1 for r in rows if r["routed_ok"] and r["bind_ok"] in (None, True))
    print(f"== skills eval ==  tasks={n}  patterns(merged)={len(store.patterns)}+{len(store.composites)}c  emb={EMB_MODEL}")
    print(f"routing : {rok}/{n} = {100*rok/n:.1f}%")
    print(f"binding : {bok}/{len(brows)} = {100*bok/max(1,len(brows)):.1f}%  (routed atoms w/ gold tokens)")
    print(f"end2end : {e2e}/{n} = {100*e2e/n:.1f}%")

    doms = sorted({r["domain"] for r in rows})
    print("\nper domain (routing | binding):")
    for d in doms:
        sel = [r for r in rows if r["domain"] == d]
        ok = sum(r["routed_ok"] for r in sel)
        bs = [r for r in sel if r["bind_ok"] is not None]
        bo = sum(r["bind_ok"] for r in bs)
        print(f"  {d:16s} {ok}/{len(sel)}  |  {bo}/{len(bs)}")

    print("\nrouting misses:")
    for r in rows:
        if not r["routed_ok"]:
            print(f"  [{r['domain']:14s}] {r['query'][:46]:48s} exp={r['exp']:30s} got={r['pred']}")
    print("\nbinding misses (routed right, wrong command):")
    for r in rows:
        if r["routed_ok"] and r["bind_ok"] is False:
            print(f"  [{r['domain']:14s}] {r['query'][:40]:42s} -> {r['cmd'][:54]}")


def run_growth():
    orig = json.loads(Path("alfred/eval/generated_queries.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="alfred-grow-"))
    core = _build_store(tmp, include_expansion=False)
    merged = _build_store(tmp, include_expansion=True)
    r_core = _make_router(core, tmp, "core")
    r_merged = _make_router(merged, tmp, "merged")
    new_ids = {p.id for p in merged.active_patterns()} - {p.id for p in core.active_patterns()}
    new_ids |= {c.id for c in merged.active_composites()} - {c.id for c in core.active_composites()}

    def exp(t):
        return expected_of(t)

    n = len(orig)
    c_ok = m_ok = leaked = 0
    leaks = []
    for t in orig:
        e = exp(t)
        pc = route(core, r_core, t["query"])
        pm = route(merged, r_merged, t["query"])
        c_ok += pc == e
        m_ok += pm == e
        if pc == e and pm != e and pm in new_ids:
            leaked += 1
            leaks.append((t["query"], e, pm))
    print(f"== library-growth study ==  original creative queries={n}")
    print(f"new patterns added: {len(new_ids)}")
    print(f"core-only routing  : {c_ok}/{n} = {100*c_ok/n:.1f}%")
    print(f"merged   routing   : {m_ok}/{n} = {100*m_ok/n:.1f}%")
    print(f"delta              : {100*(m_ok-c_ok)/n:+.1f}pp")
    print(f"queries that leaked to a NEW pattern (regressions caused by expansion): {leaked}")
    for q, e, got in leaks[:20]:
        print(f"  '{q[:50]}' exp={e} -> {got}")


if __name__ == "__main__":
    mode = os.environ.get("ALFRED_EVAL_MODE", "skills")
    if mode == "growth":
        run_growth()
    else:
        run_skills()
