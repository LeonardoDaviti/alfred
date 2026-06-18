// SET-1 runner — thinker on a mutable settings backend, scored by the END-STATE oracle.
// =====================================================================================
//
// Invariants (shared by every mode): one task set, a FRESH sandbox per task, the single
// oracle (SET-1/oracle.py). Variation = the mode:
//   --mode e1  Manual edit: tools = read/edit (NO bash, NO settings script).
//   --mode e2  Settings script: tools = bash + read, SKILL.md loaded; only the
//              `settings` script can change state.
// Success = oracle pass (final sandbox state == gold, no collateral edits), NOT command
// matching — so "did the right thing for the wrong reason" / over-editing both fail.
// Kill policy: ceiling 20 tool calls + wall-clock backstop (default 180s).
//
// USAGE:
//   tsx SET-1/run.ts --mode e2 --model qwen-3.5-2b
//   tsx SET-1/run.ts --mode e1 --model qwen3.6-35b --limit 4 --backstop-ms 240000

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
const SET1 = __dirname;

interface Task { id: string; type: string; query: string; initial: Record<string, unknown>; gold: Record<string, unknown>; }

const BASE_PROMPT = `You are an assistant that changes phone settings. Make exactly the change the user asks for — nothing else. When done, stop.`;

function parseArgs(argv: string[]): Record<string, string> {
  const a: Record<string, string> = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith("--")) { const k = argv[i].slice(2); const n = argv[i + 1]; if (n && !n.startsWith("--")) { a[k] = n; i++; } else a[k] = "true"; }
  }
  return a;
}
function loadModel(name: string): ModelConfig {
  const raw = JSON.parse(readFileSync(join(ROOT, "config", "models.json"), "utf-8")) as { models: Array<Record<string, unknown>> };
  const m = raw.models.find((x) => x.name === name);
  if (!m) throw new Error(`model not found: ${name}`);
  return m as unknown as ModelConfig;
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
      for (const part of m.content as Array<Record<string, unknown>>) {
        if (part.type === "toolCall") {
          const a = (part.arguments as Record<string, unknown>) ?? {};
          const arg = a.command ?? a.path ?? a.file_path ?? a.filePath ?? JSON.stringify(a).slice(0, 160);
          commands.push(`${part.name}: ${typeof arg === "string" ? arg : JSON.stringify(arg)}`);
        }
      }
      const u = m.usage as Record<string, unknown> | undefined; if (u) { input += (u.input as number) ?? 0; output += (u.output as number) ?? 0; }
    }
  }
  return { calls: commands.length, input, output, commands };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv);
  const mode = (args.mode ?? "e2") as "e1" | "e2";
  const modelName = args.model ?? "qwen-3.5-2b";
  const ceiling = args.ceiling ? Number(args.ceiling) : 20;
  const backstopMs = args["backstop-ms"] ? Number(args["backstop-ms"]) : 180000;
  const model = loadModel(modelName);

  const canonical = JSON.parse(readFileSync(join(SET1, "settings_schema.json"), "utf-8"));
  const tasksFile = args.tasks
    ? (args.tasks.includes("/") ? join(ROOT, args.tasks) : join(SET1, args.tasks))
    : join(SET1, "tasks.json");
  const tasksTag = tasksFile.replace(/.*\//, "").replace(/\.json$/, "");
  let tasks = JSON.parse(readFileSync(tasksFile, "utf-8")) as Task[];
  if (args.limit) tasks = tasks.slice(0, Number(args.limit));

  const skillDoc = mode === "e2" ? readFileSync(join(SET1, "SKILL.md"), "utf-8") : "";
  console.log(`▶ SET-1 ${mode} — model=${modelName} tasks=${tasks.length} ceiling=${ceiling} backstop=${backstopMs}ms`);

  const rows: Array<{ id: string; type: string; query: string; pass: boolean; calls: number; tokens: number; ms: number; detail: string; commands: string[] }> = [];

  for (const t of tasks) {
    // fresh sandbox = canonical + overrides
    const flat = flatten(canonical); Object.assign(flat, t.initial ?? {});
    const dir = mkdtempSync(join(tmpdir(), `set1-${t.id}-`));
    const statePath = join(dir, "state.json");
    writeFileSync(statePath, JSON.stringify(unflatten(flat), null, 2) + "\n");
    process.env.SET1_STATE = statePath;                       // bash tool (e2) inherits this

    const all = createTools(ROOT);
    const tools = mode === "e1"
      ? all.filter((x: any) => x.name !== "bash")              // no script, manual edit only
      : all.filter((x: any) => ["bash", "read"].includes(x.name)); // script only

    const sys = mode === "e2"
      ? `${BASE_PROMPT}\n\n${skillDoc}`
      : `${BASE_PROMPT}\n\nThe settings file is JSON at: ${statePath}\nRead it, change ONLY the requested value(s), and save. Structure: connectivity.*, display.* (ints 0-10), device.* (text), apps.<app>.*`;

    const agent = new Agent({
      getApiKey: async () => "sk-no-key-required",
      initialState: { systemPrompt: sys, model: model as any, tools, messages: [] },
    });

    const t0 = Date.now();
    const p = agent.prompt(t.query);
    const timer = setInterval(() => {
      if (harvest(agent.state.messages as unknown[]).calls >= ceiling || Date.now() - t0 > backstopMs) {
        try { (agent as any).abort(); } catch { /* */ } clearInterval(timer);
      }
    }, 150);
    try { await p; } catch (e) { if (process.env.SET1_DEBUG) console.error("PROMPT ERR:", e); }
    clearInterval(timer);
    try { await agent.waitForIdle(); } catch { /* */ }
    const ms = Date.now() - t0;
    const { calls, input, output, commands } = harvest(agent.state.messages as unknown[]);

    // oracle — first guard: did the agent leave a parseable state file?
    let pass = false, detail = "";
    let finalValid = true;
    try { JSON.parse(readFileSync(statePath, "utf-8")); } catch { finalValid = false; }
    if (!finalValid) {
      detail = "invalid_json (agent corrupted the state file)";
    } else {
      const o = spawnSync("python3", [join(SET1, "oracle.py"), "--final", statePath, "--task-id", t.id, "--task-file", tasksFile], { encoding: "utf-8" });
      try { const v = JSON.parse(o.stdout.trim()); pass = !!v.pass; detail = pass ? "" : `wrong=${JSON.stringify(v.wrong)} collateral=${JSON.stringify(v.collateral)}`; }
      catch { detail = `oracle-error: ${(o.stderr || o.stdout).slice(0, 80)}`; }
    }

    rows.push({ id: t.id, type: t.type, query: t.query, pass, calls, tokens: input + output, ms, detail, commands });
    process.stdout.write(`  [${pass ? "✓" : "✗"}] ${t.id} ${t.type.padEnd(10)} ${t.query.slice(0, 44).padEnd(46)} calls=${calls} tok=${input + output} ms=${ms}${pass ? "" : "  " + detail.slice(0, 80)}\n`);
    for (const c of commands) process.stdout.write(`        · ${c.slice(0, 130)}\n`);   // full observability
    rmSync(dir, { recursive: true, force: true });
  }

  const n = rows.length, ok = rows.filter((r) => r.pass).length;
  const byType: Record<string, [number, number]> = {};
  for (const r of rows) { (byType[r.type] ??= [0, 0])[1]++; if (r.pass) byType[r.type][0]++; }
  const med = (xs: number[]) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  console.log(`\n== SET-1 ${mode} ==  model=${modelName}`);
  console.log(`oracle pass: ${ok}/${n} = ${(100 * ok / Math.max(1, n)).toFixed(1)}%`);
  console.log(`median calls: ${med(rows.map((r) => r.calls))}  median tokens: ${med(rows.map((r) => r.tokens))}  median ms: ${med(rows.map((r) => r.ms))}`);
  console.log("per type:");
  for (const ty of Object.keys(byType).sort()) { const [o2, tot] = byType[ty]; console.log(`  ${ty.padEnd(11)} ${o2}/${tot} = ${(100 * o2 / tot).toFixed(1)}%`); }

  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
  const outPath = join(ROOT, "benchmark", "reports", `set1-${mode}-${tasksTag}-${modelName}-${ts}.json`);
  writeFileSync(outPath, JSON.stringify({ mode, model: modelName, tasks: tasksTag, ceiling, backstopMs, total: n, ok, rows }, null, 2));
  console.log(`\n✓ report → ${outPath}`);
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
