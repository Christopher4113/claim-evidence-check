export type Level = "low" | "medium" | "high";

export type Event = {
  line: number;
  kind: "user" | "assistant_text" | "tool_use" | "tool_result";
  text?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_use_id?: string;
  is_error?: boolean;
  timestamp?: string;
};

export type TestRun = {
  event_line: number;
  result_line: number | null;
  tool_use_id: string;
  command: string;
  status: "pass" | "fail" | "unknown";
  exact: boolean;
  passed: number | null;
  failed: number | null;
  failing_names: string[];
  excerpt: string;
};

export type Evidence = { line: number; role: "claim" | "test_call" | "test_result" | "edit"; text: string; tool_use_id?: string | null };

export type Finding = {
  rule_id: string;
  severity: Level;
  confidence: Level;
  message: string;
  evidence: Evidence[];
  fix: string;
  notifies: boolean;
};

export type Claim = { line: number; text: string; kind: string; hedged: boolean; scope: string | null };

export type SessionDetail = {
  id: string;
  note?: string;
  name?: string;
  repo?: string;
  origin?: string;
  expected?: string;
  events: Event[];
  runs: TestRun[];
  claims: Claim[];
  findings: Finding[];
  seconds: number;
};

export type SessionRow = {
  id: string;
  name: string;
  repo: string;
  origin: "natural" | "synthetic";
  expected: string;
  found: string[];
  severity: Level | null;
  confidence: Level | null;
  time: string | null;
  events: number;
  runs: number;
  stacktrace?: string;
};

export type PR = { tp: number; fp: number; fn: number; precision: number | null; recall: number | null };
export type BenchMode = {
  mode: string;
  all: PR;
  notify: PR;
  natural: PR;
  synthetic: PR;
  exact_runs: number;
  unknown_runs: number;
  total_runs: number;
  median_seconds: number;
};
export type Benchmark = {
  llm?: BenchMode;
  "no-llm"?: BenchMode;
  heldout?: { llm?: BenchMode; "no-llm"?: BenchMode };
  stacktrace?: { session: string; shown: string }[];
};
export type HookAnswer = { input: Record<string, unknown>; output: { decision: string; reason: string } | null };

export async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
