// SET-2 runner — Android-realistic settings. THINKER (discover) vs REFLEXER (pattern).
// =====================================================================================
//
// Same invariants as SET-1: one task set, fresh sandbox per task, one end-state oracle.
// Variation = how much the model is told:
//   --mode thinker   generic SKILL.md only (namespaces + "encodings vary"); must
//                    discover the right namespace/key/encoding. ceiling 20 + backstop.
//   --mode reflexer  the distilled pattern for this intent is injected (exact
//                    namespace + key + encoding rule); just fill the value. ceiling 4.
// Both change state via `python3 SET-2/settings.py put ...` on a per-task sandbox; scored
// by SET-2/oracle.py (end state, not command match). Full command trace stored + printed.
//
// USAGE:
//   tsx SET-2/run.ts --mode thinker  --model qwen-3.5-2b
//   tsx SET-2/run.ts --mode reflexer --model qwen-3.5-2b
//   tsx SET-2/run.ts --mode thinker  --model qwen3.6-35b --backstop-ms 240000

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { Agent } from "@mariozechner/pi-agent-core/dist/agent.js";
import { createTools } from "../agents/agent-tools.js";
import { type ModelConfig } from "../agents/pi-agent.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const SET2 = __dirname;

interface Task { id: string; pattern?: string; query: string; initial: Record<string, unknown>; gold: Record<string, unknown>; }

const BASE = `You change Android device settings via the settings script (run with bash: python3 SET-2/settings.py). Make exactly the change the user asks for — nothing else. When done, stop.`;

function parseArgs(argv: string[]): Record<string, string> {
  const a: Record<string, string> = {};
  for (let i = 2; i < argv.length; i++) if (argv[i].startsWith("--")) { const k = argv[i].slice(2); const n = argv[i + 1]; if (n && !n.startsWith("--")) { a[k] = n; i++; } else a[k] = "true"; }
  return a;
}
function loadModel(name: string): ModelConfig {
  const raw = JSON.parse(readFileSync(join(ROOT, "config", "models.json"), "utf-8")) as { models: Array<Record<string, unknown>> };
  const m = raw.models.find((x) => x.name === name); if (!m) throw new Error(`model not found: ${name}`); return m as unknown as ModelConfig;
}
function flatten(o: any, p = ""): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(o)) { const path = p ? `${p}.${k}` : k; const v = o[k]; if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(out, flatten(v, path)); else out[path] = v; }
  return out;
}
function unflatten(flat: Record<string, unknown>): any {
  const root: any = {};
  for (const path of Object.keys(flat)) { const parts = path.split("."); let cur = root; for (let i = 0; i < parts.length - 1; i++) cur = (cur[parts[i]] ??= {}); cur[parts[parts.length - 1]] = flat[path]; }
  return root;
}
function harvest(messages: unknown[]): { calls: number; input: number; output: number; commands: string[] } {
  let input = 0, output = 0; const commands: string[] = [];
  for (const raw of messages) {
    const m = raw as Record<string, unknown>;
    if (m.role === "assistant" && Array.isArray(m.content)) {
      for (const part of m.content as Array<Record<string, unknown>>) if (part.type === "toolCall") {
        const a = (part.arguments as Record<string, unknown>) ?? {};
        const arg = a.command ?? a.path ?? a.file_path ?? JSON.stringify(a).slice(0, 160);
        commands.push(`${part.name}: ${typeof arg === "string" ? arg : JSON.stringify(arg)}`);
      }
      const u = m.usage as Record<string, unknown> | undefined; if (u) { input += (u.input as number) ?? 0; output += (u.output as number) ?? 0; }
    }
  }
  return { calls: commands.length, input, output, commands };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv);
  const mode = (args.mode ?? "thinker") as "thinker" | "reflexer";
  const modelName = args.model ?? "qwen-3.5-2b";
  const ceiling = args.ceiling ? Number(args.ceiling) : (mode === "reflexer" ? 4 : 20);
  const backstopMs = args["backstop-ms"] ? Number(args["backstop-ms"]) : 180000;
  const model = loadModel(modelName);

  const canonical = JSON.parse(readFileSync(join(SET2, "settings_schema.json"), "utf-8"));
  const patternsFile = args.patterns ? (args.patterns.includes("/") ? join(ROOT, args.patterns) : join(SET2, args.patterns)) : join(SET2, "patterns.json");
  const _praw = JSON.parse(readFileSync(patternsFile, "utf-8")) as Record<string, any>;
  const _psrc = _praw.atoms ?? _praw;   // accept {atoms:{slug:{command,encoding}}} or flat {slug:string}
  const patterns: Record<string, string> = {};
  for (const k of Object.keys(_psrc)) { const v = _psrc[k]; patterns[k] = typeof v === "string" ? v : `${v.command}   # ${v.encoding}`; }
  const tasksFile = args.tasks ? (args.tasks.includes("/") ? join(ROOT, args.tasks) : join(SET2, args.tasks)) : join(SET2, "tasks.json");
  let tasks = JSON.parse(readFileSync(tasksFile, "utf-8")) as Task[];
  if (args.limit) tasks = tasks.slice(0, Number(args.limit));
  const skillDoc = mode === "thinker" ? readFileSync(join(SET2, "SKILL.md"), "utf-8") : "";

  console.log(`▶ SET-2 ${mode} — model=${modelName} tasks=${tasks.length} ceiling=${ceiling} backstop=${backstopMs}ms`);
  const rows: Array<{ id: string; pattern: string; query: string; pass: boolean; calls: number; tokens: number; ms: number; detail: string; commands: string[] }> = [];

  for (const t of tasks) {
    const flat = flatten(canonical); Object.assign(flat, t.initial ?? {});
    const dir = mkdtempSync(join(tmpdir(), `set2-${t.id}-`));
    const statePath = join(dir, "state.json");
    writeFileSync(statePath, JSON.stringify(unflatten(flat), null, 2) + "\n");
    process.env.SET2_STATE = statePath;

    const tools = createTools(ROOT).filter((x: any) => ["bash", "read"].includes(x.name));
    const sys = mode === "thinker"
      ? `${BASE}\n\n${skillDoc}`
      : `${BASE}\n\nUse exactly this distilled command pattern for the request, substituting the value:\n  ${patterns[t.pattern ?? ""] ?? "(no distilled pattern for this task)"}\nRun it with bash.`;

    const agent = new Agent({ getApiKey: async () => "sk-no-key-required", initialState: { systemPrompt: sys, model: model as any, tools, messages: [] } });
    const t0 = Date.now();
    const p = agent.prompt(t.query);
    const timer = setInterval(() => { if (harvest(agent.state.messages as unknown[]).calls >= ceiling || Date.now() - t0 > backstopMs) { try { (agent as any).abort(); } catch { /* */ } clearInterval(timer); } }, 150);
    try { await p; } catch (e) { if (process.env.SET2_DEBUG) console.error("ERR", e); }
    clearInterval(timer); try { await agent.waitForIdle(); } catch { /* */ }
    const ms = Date.now() - t0;
    const { calls, input, output, commands } = harvest(agent.state.messages as unknown[]);

    let pass = false, detail = "", finalValid = true;
    try { JSON.parse(readFileSync(statePath, "utf-8")); } catch { finalValid = false; }
    if (!finalValid) { detail = "invalid_json"; }
    else {
      const o = spawnSync("python3", [join(SET2, "oracle.py"), "--final", statePath, "--task-id", t.id, "--task-file", tasksFile], { encoding: "utf-8" });
      try { const v = JSON.parse(o.stdout.trim()); pass = !!v.pass; detail = pass ? "" : `wrong=${JSON.stringify(v.wrong)}`; }
      catch { detail = `oracle-error: ${(o.stderr || o.stdout).slice(0, 80)}`; }
    }
    rows.push({ id: t.id, pattern: t.pattern ?? "", query: t.query, pass, calls, tokens: input + output, ms, detail, commands });
    process.stdout.write(`  [${pass ? "✓" : "✗"}] ${t.id} ${t.query.slice(0, 40).padEnd(42)} calls=${calls} tok=${input + output} ms=${ms}${pass ? "" : "  " + detail.slice(0, 80)}\n`);
    for (const c of commands) process.stdout.write(`        · ${c.slice(0, 130)}\n`);
    rmSync(dir, { recursive: true, force: true });
  }

  const n = rows.length, ok = rows.filter((r) => r.pass).length;
  const med = (xs: number[]) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  console.log(`\n== SET-2 ${mode} ==  model=${modelName}`);
  console.log(`oracle pass: ${ok}/${n} = ${(100 * ok / Math.max(1, n)).toFixed(1)}%`);
  console.log(`median calls: ${med(rows.map((r) => r.calls))}  median tokens: ${med(rows.map((r) => r.tokens))}  median ms: ${med(rows.map((r) => r.ms))}`);
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
  const outPath = join(ROOT, "benchmark", "reports", `set2-${mode}-${modelName}-${ts}.json`);
  writeFileSync(outPath, JSON.stringify({ mode, model: modelName, ceiling, backstopMs, total: n, ok, rows }, null, 2));
  console.log(`\n✓ report → ${outPath}`);
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
