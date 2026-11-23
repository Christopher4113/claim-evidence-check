import { AnimatePresence, motion } from "motion/react";
import { Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LevelBadge, Mono, Terminal } from "@/components/bits";
import type { Event, Finding, SessionDetail, TestRun } from "@/lib/api";
import { cn } from "@/lib/utils";

type Step = { key: string; ev: Event; phase: "Request" | "Agent" | "Tool" | "Result"; run?: TestRun };

const QUIET_TOOLS = new Set(["TodoWrite", "ToolSearch", "Glob", "Grep", "LS", "Read", "Skill"]);

function buildSteps(s: SessionDetail): Step[] {
  const byCall = new Map(s.runs.map((r) => [r.tool_use_id, r]));
  const quietIds = new Set(s.events.filter((e) => e.kind === "tool_use" && QUIET_TOOLS.has(e.tool_name ?? "")).map((e) => e.tool_use_id));
  return s.events
    .filter((e) => !(e.tool_use_id && quietIds.has(e.tool_use_id)))
    .map((ev, i) => ({
      key: `${ev.line}-${i}`,
      ev,
      phase: ev.kind === "user" ? "Request" : ev.kind === "assistant_text" ? "Agent" : ev.kind === "tool_use" ? "Tool" : "Result",
      run: ev.tool_use_id ? byCall.get(ev.tool_use_id) : undefined,
    }));
}

function toolLabel(e: Event): string {
  const inp = (e.tool_input ?? {}) as Record<string, string>;
  if (e.tool_name === "Bash") return inp.command ?? "";
  return inp.file_path ?? inp.path ?? inp.pattern ?? JSON.stringify(inp).slice(0, 120);
}

function StepBody({ step }: { step: Step }) {
  const { ev, run } = step;
  if (ev.kind === "user") return <p className="text-sm text-foreground whitespace-pre-wrap">{ev.text}</p>;
  if (ev.kind === "assistant_text") return <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">{ev.text}</p>;
  if (ev.kind === "tool_use")
    return (
      <Terminal title={ev.tool_name}>
        <span className="text-foreground/90">{toolLabel(ev)}</span>
      </Terminal>
    );
  if (run)
    return (
      <Terminal title={`${run.status} · ${run.exact ? "parsed exactly" : "exit code only"}`} tone={run.status === "fail" ? "fail" : run.status === "pass" ? "pass" : undefined}>
        {run.excerpt || "(no summary line found: unknown)"}
        {run.failing_names.length > 0 && <span className="block text-muted-foreground">{run.failing_names.map((n) => `FAILED ${n}`).join("\n")}</span>}
      </Terminal>
    );
  const t = (ev.text ?? "").trim();
  return <Mono className="block truncate text-xs text-muted-foreground">{t.split("\n")[0]?.slice(0, 140) || "(empty)"}</Mono>;
}

export function FindingCard({ f }: { f: Finding }) {
  const claim = f.evidence.find((e) => e.role === "claim");
  const call = f.evidence.find((e) => e.role === "test_call");
  const result = f.evidence.find((e) => e.role === "test_result");
  const edits = f.evidence.filter((e) => e.role === "edit");
  return (
    <Card className={cn("gap-4 border p-5", f.notifies ? "border-danger/40" : "border-amber/30")}>
      <div className="flex flex-wrap items-center gap-2">
        <Mono className="text-foreground">{f.rule_id}</Mono>
        <LevelBadge label="severity" level={f.severity} />
        <LevelBadge label="confidence" level={f.confidence} />
        <span className={cn("ml-auto font-mono text-[11px]", f.notifies ? "text-danger" : "text-muted-foreground")}>
          {f.notifies ? "notifies" : "recorded"}
        </span>
      </div>
      {claim && (
        <p className="font-serif text-lg leading-snug">
          Agent said <em className="text-amber">"{claim.text}"</em> <Mono className="text-muted-foreground">(line {claim.line})</Mono>
        </p>
      )}
      {result && (
        <div>
          <div className="mb-1 font-mono text-[11px] text-muted-foreground">tool result · line {result.line}</div>
          <Terminal tone="fail">{result.text}</Terminal>
        </div>
      )}
      {call && (
        <div className="space-y-1 font-mono text-[12px] text-muted-foreground">
          <div>
            cited call <span className="text-foreground">{call.tool_use_id}</span> · line {call.line}
          </div>
          <div className="truncate text-foreground/80">$ {call.text}</div>
        </div>
      )}
      {edits.length > 0 && <div className="font-mono text-[11px] text-muted-foreground">edits after the run: {edits.map((e) => `line ${e.line}`).join(", ")}</div>}
      <div className="border-t border-border pt-3 text-sm">
        <span className="font-mono text-[11px] text-sage">fix </span>
        {f.fix}
      </div>
    </Card>
  );
}

export function Replay({ session, speed = 700 }: { session: SessionDetail; speed?: number }) {
  const steps = useMemo(() => buildSteps(session), [session]);
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(true);
  const listRef = useRef<HTMLOListElement>(null);

  const primary = session.findings.find((f) => f.notifies) ?? session.findings[0];
  const claimLine = primary?.evidence.find((e) => e.role === "claim")?.line;
  const cited = new Set(primary?.evidence.filter((e) => e.role !== "claim").map((e) => e.line));
  const claimIdx = claimLine ? steps.findIndex((s) => s.ev.line === claimLine && s.ev.kind === "assistant_text") : -1;
  const showFinding = primary && claimIdx >= 0 && pos >= claimIdx;

  useEffect(() => {
    setPos(0);
    setPlaying(true);
  }, [session.id]);
  useEffect(() => {
    if (!playing) return;
    if (pos >= steps.length - 1) {
      setPlaying(false);
      return;
    }
    // Linger on the false claim so the finding lands.
    const t = setTimeout(() => setPos((p) => p + 1), pos === claimIdx ? speed * 4 : speed);
    return () => clearTimeout(t);
  }, [playing, pos, steps.length, speed, claimIdx]);
  useEffect(() => {
    // Scroll the step list only, never the page.
    const list = listRef.current;
    const item = list?.querySelector<HTMLElement>(`[data-pos="${pos}"]`);
    if (list && item && item.offsetTop + item.offsetHeight > list.scrollTop + list.clientHeight)
      list.scrollTo({ top: item.offsetTop + item.offsetHeight - list.clientHeight + 8, behavior: "smooth" });
  }, [pos]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]" data-testid="replay">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => setPlaying((p) => !p)}>
            {playing ? <Pause /> : <Play />} {playing ? "Pause" : "Play"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => { setPos(0); setPlaying(true); }}>
            <RotateCcw /> Replay
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPos((p) => Math.min(p + 1, steps.length - 1))}>
            <SkipForward /> Step
          </Button>
          <Mono className="ml-auto text-xs text-muted-foreground">
            step {pos + 1}/{steps.length}
          </Mono>
        </div>
        <ol ref={listRef} data-testid="replay-steps" className="relative max-h-[68vh] space-y-2 overflow-y-auto pr-2">
          {steps.slice(0, pos + 1).map((s, i) => {
            const hot = cited.has(s.ev.line) || (s.ev.line === claimLine && s.ev.kind === "assistant_text");
            return (
              <motion.li
                key={s.key}
                data-pos={i}
                data-line={s.ev.line}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
                className={cn(
                  "grid grid-cols-[44px_72px_minmax(0,1fr)] items-start gap-3 rounded-md border px-3 py-2.5",
                  hot && showFinding ? "border-amber/50 bg-amber/[0.06]" : "border-transparent",
                  i === pos && !hot && "border-border bg-card/60",
                )}
              >
                <Mono className="pt-0.5 text-xs text-muted-foreground">L{s.ev.line}</Mono>
                <Mono className={cn("pt-0.5 text-xs", s.phase === "Request" ? "text-sage" : "text-muted-foreground")}>{s.phase}</Mono>
                <StepBody step={s} />
              </motion.li>
            );
          })}
        </ol>
      </div>
      <div className="lg:sticky lg:top-6 lg:self-start">
        <div className="mb-3 font-mono text-xs text-muted-foreground">
          Request → Agent → <span className="text-sage">claim-evidence-check</span> → Outcome
        </div>
        <AnimatePresence mode="wait">
          {showFinding ? (
            <motion.div key="f" data-testid="finding" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ type: "spring", stiffness: 260, damping: 28 }}>
              <FindingCard f={primary} />
              {session.findings.length > 1 && (
                <div className="mt-3 space-y-3">
                  {session.findings.filter((f) => f !== primary).map((f, i) => <FindingCard key={i} f={f} />)}
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div key="w" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Card className="border-dashed p-5 text-sm text-muted-foreground">
                {primary ? "Watching the session. Every finding cites the call it fired on." : pos >= steps.length - 1 ? "No findings. The claims in this session match the evidence." : "Watching the session…"}
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
