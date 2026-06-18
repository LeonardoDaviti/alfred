# Reproduce

Every number in the thesis and README traces to a saved run in `benchmarks/reports/`.
This file gives the exact command per headline. No number is estimated.

## 0. Setup

```bash
pip install -e .                       # numpy, matplotlib (+ optional sentence-transformers)
make setup                             # stage example patterns into ./data/patterns
```

Model runs need a local **OpenAI-compatible** endpoint. We serve Q4 GGUF models with
`llama.cpp` (`llama-server`). The reflexer-class models use these exact parameters —
**temperature 0.2** and **reasoning disabled**:

```bash
llama-server Qwen3.5-2B-UD-Q4_K_XL.gguf --alias qwen-3.5-2b \
  --host 0.0.0.0 --port 8005 --ctx-size 4072 --n-gpu-layers 999 --jinja \
  --threads 16 --temp 0.2 --top-p 0.95 --top-k 20 --min-p 0.00 \
  --presence_penalty 0.5 --cache-type-k q8_0 --cache-type-v q8_0 \
  --metrics --slots --flash-attn on --cache-ram 0 \
  --chat-template-kwargs '{"enable_thinking":false}'
```

`ministral-3-3b` uses the **same** parameters. The 35B thinker is run in its native
reasoning mode (thinking enabled). All models are **Q4**.

## 1. Figures (no model needed)

```bash
python thesis/figures/make_figures.py         # → thesis/figures/*.pdf (+ .png)
```

## 2. Binding-only (routing assumed perfect)

```bash
# reflexer (2B), atoms — expect 100%
ALFRED_LLM_MODEL=qwen-3.5-2b ALFRED_LLM_URL=http://127.0.0.1:8005/v1 \
  python -m alfred.eval.binding_only_eval alfred/eval/expansion_tasks_phase2.json
```
Reports: `binding-only-phase2-qwen2b*.txt`, `binding-only-qwen3.5-*-atoms.txt`,
`binding-only-all-ministral-2026-06-16.txt`.

## 3. SET-1 (clean API) and SET-2 (realistic Android API)

```bash
# SET-1: manual edit (E1) vs deep tool (E2)
tsx benchmarks/SET-1/run.ts --mode e2 --model qwen-3.5-2b
# SET-2: free-form thinker vs distilled reflexer
tsx benchmarks/SET-2/run.ts --mode thinker  --model qwen-3.5-2b
tsx benchmarks/SET-2/run.ts --mode reflexer --model qwen-3.5-2b --patterns ../../patterns/distilled_sonnet.json
# preflight (no model) sanity-checks the oracle + task set:
python benchmarks/SET-2/preflight.py
```
Reports: `set1-*`, `set2-*`.

## 4. Teacher comparison (cloud vs local distiller)

Run the SET-2 reflexer against each teacher's patterns and compare:

```bash
tsx benchmarks/SET-2/run.ts --mode reflexer --patterns ../../patterns/distilled_sonnet.json
tsx benchmarks/SET-2/run.ts --mode reflexer --patterns ../../patterns/distilled_local35b.json
```
Expect ~80% (cloud) vs ~60% (local). `distilled_local35b.json` is **frozen** — it is the
artifact under test and must not be edited after observing failures.
