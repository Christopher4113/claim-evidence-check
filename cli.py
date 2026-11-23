"""claim-evidence-check CLI.

  python cli.py path/to/session.jsonl [--no-llm] [--json]
  python cli.py --all sessions/ [--no-llm] [--json]
"""

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from claimcheck.claims import LLMRateLimited
from claimcheck.rules import MISMATCH, NO_EVIDENCE, Report, check_file

console = Console()
EXPECTED_RULE = {"mismatch": MISMATCH, "no_tests": NO_EVIDENCE}


def load_env(path=".env"):
    p = Path(__file__).parent / path
    if p.exists():
        for ln in p.read_text().splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def print_report(rep: Report):
    exact = sum(r.exact for r in rep.runs)
    console.print(f"[bold]{rep.path}[/]  events={len(rep.events)} test_runs={len(rep.runs)} (exact {exact}) "
                  f"claims={len(rep.claims)} findings={len(rep.findings)}  {rep.seconds:.2f}s")
    for r in rep.runs:
        console.print(f"  [dim]run L{r.event_line}[/] {r.status:7} {r.command[:70]!r}  [dim]{r.excerpt.splitlines()[0] if r.excerpt else ''}[/]")
    for f in rep.findings:
        color = "red" if f.notifies else "yellow"
        console.print(f"\n[{color} bold]{f.rule_id}[/]  severity={f.severity} confidence={f.confidence}"
                      f"{'  [bold]NOTIFY[/]' if f.notifies else ''}")
        console.print(f"  {f.message}")
        for e in f.evidence:
            tid = f" {e.tool_use_id}" if e.tool_use_id else ""
            console.print(f"  [dim]L{e.line} {e.role}{tid}:[/] {e.text[:160]}")
        console.print(f"  fix: {f.fix}")


def run_all(folder: Path, use_llm: bool, as_json: bool):
    labels = json.loads((folder / "labels.json").read_text())
    rows, times, exact, unknown = [], [], 0, 0
    for name, lab in labels.items():
        rep = check_file(folder / name, use_llm=use_llm)
        times.append(rep.seconds)
        exact += sum(r.exact for r in rep.runs)
        unknown += sum(r.status == "unknown" for r in rep.runs)
        found = sorted({f.rule_id for f in rep.findings})
        mm = next((f for f in rep.findings if f.rule_id == MISMATCH), None)
        rows.append(dict(session=name, origin=lab["origin"], expected=lab["expected"], found=found,
                         severity=mm.severity if mm else None, confidence=mm.confidence if mm else None,
                         notifies=bool(mm and mm.notifies), seconds=round(rep.seconds, 3),
                         runs=len(rep.runs)))

    def pr(subset, notify_only=False):
        tp = sum(1 for r in subset if r["expected"] == "mismatch" and MISMATCH in r["found"] and (r["notifies"] or not notify_only))
        fp = sum(1 for r in subset if r["expected"] != "mismatch" and MISMATCH in r["found"] and (r["notifies"] or not notify_only))
        fn = sum(1 for r in subset if r["expected"] == "mismatch") - tp
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        return dict(tp=tp, fp=fp, fn=fn, precision=prec, recall=rec)

    natural = [r for r in rows if r["origin"] == "natural"]
    synthetic = [r for r in rows if r["origin"] == "synthetic"]
    from claimcheck.claims import FALLBACKS
    summary = dict(mode="llm" if use_llm else "no-llm", llm_fallbacks=len(FALLBACKS), all=pr(rows), notify=pr(rows, True), natural=pr(natural),
                   synthetic=pr(synthetic), exact_runs=exact, unknown_runs=unknown,
                   total_runs=sum(r["runs"] for r in rows), median_seconds=round(statistics.median(times), 3) if times else None,
                   rows=rows)
    if as_json:
        print(json.dumps(summary, indent=2))
        return summary
    t = Table(title=f"claim-evidence-check ({summary['mode']})")
    for col in ("session", "origin", "expected", "found", "sev", "conf", "s"):
        t.add_column(col)
    for r in rows:
        exp_rule = EXPECTED_RULE.get(r["expected"])
        ok = (exp_rule in r["found"]) if exp_rule else (MISMATCH not in r["found"])
        t.add_row(r["session"], r["origin"], r["expected"], ", ".join(r["found"]) or "-", r["severity"] or "-",
                  r["confidence"] or "-", f"{r['seconds']:.2f}", style=None if ok else "red")
    console.print(t)
    fmt = lambda x: "n/a" if x is None else f"{x:.2f}"
    for k in ("all", "notify", "natural", "synthetic"):
        m = summary[k]
        console.print(f"mismatch {k:9} precision={fmt(m['precision'])} recall={fmt(m['recall'])}  (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
    console.print(f"test runs parsed exactly: {exact}/{summary['total_runs']}  unknown: {unknown}  median time/session: {summary['median_seconds']}s")
    return summary


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--all", metavar="DIR")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    use_llm = not a.no_llm
    if use_llm and not os.environ.get("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY not set (see .env.example), or pass --no-llm")
    try:
        if a.all:
            run_all(Path(a.all), use_llm, a.json)
        elif a.path:
            rep = check_file(a.path, use_llm=use_llm)
            if a.json:
                print(json.dumps({"findings": [f.model_dump() for f in rep.findings],
                                  "runs": [r.model_dump() for r in rep.runs],
                                  "claims": [c.model_dump() for c in rep.claims]}, indent=2))
            else:
                print_report(rep)
            sys.exit(1 if any(f.notifies for f in rep.findings) else 0)
        else:
            ap.print_help()
    except LLMRateLimited as e:
        sys.exit(f"Groq rate limit hit: {e}\nRerun with --no-llm, or wait for the limit to reset.")


if __name__ == "__main__":
    main()
