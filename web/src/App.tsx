import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LevelBadge, Mono, Section, Terminal } from "@/components/bits";
import { Replay } from "@/components/Replay";
import { getJSON, type Benchmark, type BenchMode, type HookAnswer, type SessionDetail, type SessionRow } from "@/lib/api";
import { cn } from "@/lib/utils";

const TABS = [
  ["sessions", "Sessions"],
  ["replay", "Replay"],
  ["check", "Check a session"],
  ["benchmark", "Benchmark"],
  ["steer", "Steer"],
] as const;

// ?demo keeps routing in memory: headless recorders treat a hash change as a page load.
const DEMO = new URLSearchParams(window.location.search).has("demo");
let memRoute = "";
export function go(path: string) {
  if (DEMO) {
    memRoute = path;
    window.dispatchEvent(new Event("hashchange"));
  } else window.location.hash = path;
}

function useHash(): [string, string | undefined] {
  const read = () => (DEMO ? memRoute : window.location.hash).replace(/^#\/?/, "").split("/");
  const [h, setH] = useState(read);
  useEffect(() => {
    const on = () => setH(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [h[0] || "sessions", h[1] ? decodeURIComponent(h[1]) : undefined];
}

function Header({ tab }: { tab: string }) {
  return (
    <header className="relative overflow-hidden border-b border-border">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[900px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgb(156 197 176 / 0.16), transparent)" }}
      />
      <div className="relative mx-auto max-w-6xl px-4 pt-10 pb-6 sm:px-6">
        <Mono className="text-xs text-sage">&gt;_ claim-evidence-mismatch</Mono>
        <h1 className="mt-3 max-w-3xl font-serif text-4xl leading-[1.08] sm:text-5xl">
          Agents say the tests pass. <em className="text-sage">Check what the tests said.</em>
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
          Reads Claude Code session logs, finds the success claim, links it to the test run it rests on, and raises a finding when the output says
          otherwise. Every finding cites the call it fired on.
        </p>
        <nav className="mt-7 flex flex-wrap gap-1">
          {TABS.map(([id, label]) => (
            <a
              key={id}
              href={`#/${id}`}
              onClick={(e) => { if (DEMO) { e.preventDefault(); go(`#/${id}`); } }}
              data-testid={`tab-${id}`}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                tab === id ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}

function Sessions({ rows }: { rows: SessionRow[] }) {
  return (
    <>
      <Section eyebrow="01 · sessions" title={<>Twenty Claude Code runs, <em>labelled by hand.</em></>}>
        Sixteen real runs on two demo repos (pytest and vitest), plus four synthetic rows: copies of a real session with only the final message edited. Click a row to replay it.
      </Section>
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              {["Session", "Repo", "Origin", "Expected", "Found", "Severity", "Confidence", "Time"].map((h) => (
                <TableHead key={h} className="font-mono text-[11px] font-normal text-muted-foreground">{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id} data-testid={`row-${r.name}`} className="cursor-pointer" onClick={() => go(`#/replay/${encodeURIComponent(r.id)}`)}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell><Mono className="text-muted-foreground">{r.repo}</Mono></TableCell>
                <TableCell className={r.origin === "synthetic" ? "text-amber" : "text-muted-foreground"}>{r.origin}</TableCell>
                <TableCell><Mono>{r.expected}</Mono></TableCell>
                <TableCell><Mono className={r.found.length ? "text-foreground" : "text-muted-foreground"}>{r.found.join(", ") || "none"}</Mono></TableCell>
                <TableCell><LevelBadge label="" level={r.severity} /></TableCell>
                <TableCell><LevelBadge label="" level={r.confidence} /></TableCell>
                <TableCell><Mono className="text-xs text-muted-foreground">{r.time ? new Date(r.time).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"}</Mono></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </>
  );
}

function ReplayScreen({ id, rows }: { id?: string; rows: SessionRow[] }) {
  const pick = id ?? rows.find((r) => r.expected === "mismatch" && r.origin === "natural")?.id ?? rows[0]?.id;
  const [s, setS] = useState<SessionDetail | null>(null);
  useEffect(() => {
    if (pick) getJSON<SessionDetail>(`/api/sessions/${encodeURIComponent(pick)}`).then(setS);
  }, [pick]);
  if (!s) return <p className="text-muted-foreground">Loading…</p>;
  return (
    <>
      <Section eyebrow={`02 · replay · ${s.repo ?? ""} · ${s.origin ?? ""}`} title={s.name ?? s.id}>
        Expected: <Mono>{s.expected}</Mono>. Events {s.events.length}, test runs {s.runs.length}, claims {s.claims.length}.
      </Section>
      <Replay session={s} />
    </>
  );
}

function Check() {
  const [llm, setLlm] = useState(false);
  const [stage, setStage] = useState<string[]>([]);
  const [res, setRes] = useState<SessionDetail | null>(null);
  const [err, setErr] = useState("");
  const [over, setOver] = useState(false);

  async function run(file: File) {
    setRes(null);
    setErr("");
    setStage(["uploading"]);
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/check?llm=${llm}`, { method: "POST", body: fd });
    if (!r.ok) {
      setErr(await r.text());
      setStage([]);
      return;
    }
    const d: SessionDetail = await r.json();
    const steps = [`${d.events.length} events`, `${d.runs.length} test runs`, `${d.claims.length} claims`, `${d.findings.length} findings`];
    for (let i = 1; i <= steps.length; i++) {
      setStage(steps.slice(0, i));
      await new Promise((ok) => setTimeout(ok, 280));
    }
    setRes({ ...d, id: file.name, name: file.name });
  }

  return (
    <>
      <Section eyebrow="03 · check" title={<>Drop a session log. <em>See what it claimed.</em></>}>
        Any Claude Code <Mono>.jsonl</Mono> from <Mono>~/.claude/projects/</Mono>. In <Mono>--no-llm</Mono> mode nothing leaves this machine; with the LLM on,
        only the candidate sentences are sent to Groq.
      </Section>
      <div className="mb-4 flex items-center gap-3 text-sm">
        <Switch checked={llm} onCheckedChange={setLlm} id="llm" />
        <label htmlFor="llm" className="font-mono text-xs">{llm ? "LLM (Groq, candidate sentences only)" : "--no-llm (fully local)"}</label>
      </div>
      <label
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) run(f); }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-12 text-center transition-colors",
          over ? "border-sage bg-sage/5" : "border-border hover:border-sage/50",
        )}
      >
        <input type="file" accept=".jsonl" className="sr-only" onChange={(e) => e.target.files?.[0] && run(e.target.files[0])} />
        <Mono className="text-sage">&gt;_ drop session.jsonl</Mono>
        <span className="mt-1 text-xs text-muted-foreground">or click to choose a file</span>
      </label>
      {stage.length > 0 && (
        <Mono className="mt-4 block text-xs text-muted-foreground">{["parse", "test runs", "claims", "findings"].map((s, i) => `${s}: ${stage[i] ?? "…"}`).join("   →   ")}</Mono>
      )}
      {err && <p className="mt-4 font-mono text-xs text-danger">{err}</p>}
      {res && <div className="mt-8"><Replay session={res} speed={250} /></div>}
    </>
  );
}

const pct = (x: number | null | undefined) => (x == null ? "n/a" : `${Math.round(x * 100)}%`);

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="gap-1 p-4">
      <Mono className="text-[11px] text-muted-foreground">{label}</Mono>
      <div className="font-serif text-3xl tabular-nums">{value}</div>
      {sub && <Mono className="text-[11px] text-muted-foreground">{sub}</Mono>}
    </Card>
  );
}

function ModeStats({ m, id }: { m: BenchMode; id: string }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid={`stats-${id}`}>
      <Stat label="precision · natural" value={pct(m.natural.precision)} sub={`tp ${m.natural.tp} fp ${m.natural.fp}`} />
      <Stat label="recall · natural" value={pct(m.natural.recall)} sub={`fn ${m.natural.fn}`} />
      <Stat label="precision · synthetic" value={pct(m.synthetic.precision)} sub={`tp ${m.synthetic.tp} fp ${m.synthetic.fp}`} />
      <Stat label="recall · synthetic" value={pct(m.synthetic.recall)} sub={`fn ${m.synthetic.fn}`} />
      <Stat label="notify-level precision" value={pct(m.notify.precision)} sub="severity ≥ medium and confidence high" />
      <Stat label="notify-level recall" value={pct(m.notify.recall)} />
      <Stat label="exact parse rate" value={pct(m.total_runs ? m.exact_runs / m.total_runs : null)} sub={`${m.exact_runs}/${m.total_runs} runs · ${m.unknown_runs} unknown`} />
      <Stat label="median time / session" value={`${Math.round(m.median_seconds * 1000)}ms`} />
    </div>
  );
}

function BenchmarkScreen() {
  const [b, setB] = useState<Benchmark | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<Benchmark>("/api/benchmark").then(setB).catch((e) => setErr(String(e))); }, []);
  if (err) return <p className="font-mono text-xs text-danger">{err}</p>;
  if (!b) return <p className="text-muted-foreground">Loading…</p>;
  return (
    <>
      <Section eyebrow="04 · benchmark" title={<>Precision before recall, <em>measured.</em></>}>
        claim-evidence-mismatch on the 20 labelled sessions, in both modes. Natural and synthetic sessions are reported separately.
      </Section>
      {(["no-llm", "llm"] as const).map((k) => b[k] && (
        <div key={k} className="mb-8">
          <Mono className="mb-3 block text-xs text-sage">{k === "llm" ? "LLM confirm (Groq)" : "--no-llm (regex only, fully local)"}</Mono>
          <ModeStats m={b[k]!} id={k} />
        </div>
      ))}
      {b.heldout?.["no-llm"] && (
        <div className="mb-8">
          <Mono className="mb-3 block text-xs text-sage">Held-out: 6 fresh sessions, labelled before the checker ran</Mono>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="false positives · --no-llm" value={String(b.heldout["no-llm"].all.fp)} sub="6 honest sessions" />
            <Stat label="false positives · LLM" value={String(b.heldout.llm?.all.fp ?? "n/a")} sub="6 honest sessions" />
            <Stat label="exact parse rate" value={pct(b.heldout["no-llm"].exact_runs / b.heldout["no-llm"].total_runs)} sub={`${b.heldout["no-llm"].exact_runs}/${b.heldout["no-llm"].total_runs} runs`} />
            <Stat label="natural mismatches" value="0" sub="none occurred, so no recall here" />
          </div>
        </div>
      )}
      {b.stacktrace && (
        <>
          <div data-testid="stacktrace"><Mono className="mb-3 block text-xs text-sage">Stacktrace live sidecar on the same sessions</Mono></div>
          <Card className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead className="font-mono text-[11px] font-normal">session</TableHead><TableHead className="font-mono text-[11px] font-normal">what the live sidecar showed</TableHead></TableRow></TableHeader>
              <TableBody>
                {b.stacktrace.map((r) => (
                  <TableRow key={r.session}><TableCell><Mono>{r.session}</Mono></TableCell><TableCell className="text-sm text-muted-foreground">{r.shown}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </>
  );
}

function HookCard({ sid }: { sid: string }) {
  const [h, setH] = useState<HookAnswer | null>(null);
  useEffect(() => { getJSON<HookAnswer>(`/api/hook/${encodeURIComponent(sid)}`).then(setH); }, [sid]);
  if (!h) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid="hook">
      <Terminal title="Stop hook · stdin">{JSON.stringify(h.input, null, 2)}</Terminal>
      <div data-testid="hook-out">
        <Terminal title={h.output ? "stdout · blocks the stop" : "stdout · allows the stop"} tone={h.output ? "fail" : "pass"}>
          {h.output ? JSON.stringify(h.output, null, 2) : "(no output, exit 0)"}
        </Terminal>
      </div>
    </div>
  );
}

function Steer() {
  const [live, setLive] = useState<SessionDetail[]>([]);
  const [syn, setSyn] = useState<SessionDetail | null>(null);
  useEffect(() => {
    getJSON<SessionDetail[]>("/api/steer").then(setLive);
    getJSON<SessionDetail>("/api/sessions/syn-py-two-funcs.jsonl").then(setSyn);
  }, []);
  return (
    <>
      <Section eyebrow="05 · steer" title={<>Block the false "done." <em>Hand back the evidence.</em></>}>
        A Claude Code Stop hook runs the rules locally (--no-llm) on the current turn. On a high-confidence mismatch it blocks the stop and tells the
        agent which run failed and what still fails. Otherwise it stays out of the way.
      </Section>
      <Mono className="mb-3 block text-xs text-sage">Block path: synthetic session syn-py-two-funcs ("All tests pass now.", last run 4 failed)</Mono>
      <div className="mb-6"><HookCard sid="syn-py-two-funcs.jsonl" /></div>
      {syn && <div className="mb-12"><Replay session={syn} speed={350} /></div>}
      <Mono className="mb-3 block text-xs text-sage">Live sessions with the hook installed</Mono>
      <p className="mb-4 max-w-2xl text-sm text-muted-foreground">
        Both prompts asked the agent to end with "All tests pass." Both times it refused and reported the failures, so the hook allowed the stop.
      </p>
      <div className="space-y-10">
        {live.map((s) => (
          <div key={s.id}>
            <div className="mb-2 font-serif text-xl">{s.name}</div>
            <p className="mb-3 text-sm text-muted-foreground">{s.note}</p>
            <Replay session={s} speed={200} />
          </div>
        ))}
      </div>
    </>
  );
}

export default function App() {
  const [tab, id] = useHash();
  const [rows, setRows] = useState<SessionRow[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<SessionRow[]>("/api/sessions").then(setRows).catch((e) => setErr(String(e))); }, []);
  const listed = rows;
  return (
    <div className="flex min-h-screen flex-col">
      <Header tab={tab} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6" style={DEMO ? { paddingBottom: "70vh" } : undefined}>
        {err && <p className="mb-4 font-mono text-xs text-danger">API unreachable: {err}. Start it with uv run uvicorn claimcheck.server:app --port 8000</p>}
        {tab === "sessions" && <Sessions rows={listed} />}
        {tab === "replay" && <ReplayScreen id={id} rows={listed} />}
        {tab === "check" && <Check />}
        {tab === "benchmark" && <BenchmarkScreen />}
        {tab === "steer" && <Steer />}
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-5 text-xs text-muted-foreground sm:px-6">
          <span>Prototype by Christopher Lam, not affiliated with Stacktrace.</span>
          <Mono className="text-xs">rule: claim-evidence-mismatch</Mono>
        </div>
      </footer>
    </div>
  );
}
