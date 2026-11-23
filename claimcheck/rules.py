"""Rules: pure functions from parsed session -> list[Finding]."""

import re
import time
from pathlib import Path

from pydantic import BaseModel

from . import claims as claims_mod
from .claims import WHOLE_SUITE
from .link import Link, link
from .models import Claim, Event, Evidence, Finding, TestRun
from .session import parse_file
from .testruns import find_test_runs

MISMATCH = "claim-evidence-mismatch"
NO_EVIDENCE = "claim-without-evidence"
STALE = "claim-stale-evidence"
CHECKED_KINDS = ("tests_pass", "build_ok", "bug_fixed")


def _short_cmd(cmd: str) -> str:
    # the segment that ran the tests, without redirects: "cd app && uv run pytest -q 2>&1 | tail" -> "uv run pytest -q"
    from .testruns import SEGMENT_SPLIT, is_test_command
    hits = [s.strip() for s in SEGMENT_SPLIT.split(cmd) if s.strip() and is_test_command(s)]
    seg = (hits[-1] if hits else cmd).strip("() ")
    return re.sub(r"\s*\d?>&?\d?\S*", "", seg).strip()[:80]


def _scope_hits(scope: str, name: str) -> bool:
    norm = lambda x: re.sub(r"[^a-z0-9]+", " ", x.lower())
    words = [w for w in norm(scope).split() if len(w) > 2 and w not in ("test", "tests", "the")]
    return any(w in norm(name) for w in words)


def _fail_phrase(run: TestRun) -> str:
    if run.exact and run.failed:
        return f"{run.failed} failed"
    return f"a failure ({run.excerpt or 'non-zero exit'})"


def _run_evidence(run: TestRun) -> list[Evidence]:
    ev = [Evidence(line=run.event_line, role="test_call", text=run.command, tool_use_id=run.tool_use_id)]
    if run.result_line:
        ev.append(Evidence(line=run.result_line, role="test_result", text=run.excerpt, tool_use_id=run.tool_use_id))
    return ev


def mismatch(lk: Link) -> Finding | None:
    c, run = lk.claim, lk.run
    if c.kind not in CHECKED_KINDS or not run or run.status != "fail":
        return None
    if c.scope and run.failing_names and not any(_scope_hits(c.scope, n) for n in run.failing_names):
        return None  # "leap-year tests pass" while only unrelated tests fail: a true scoped claim
    # High only when output was parsed exactly, the claim is unhedged, and nothing was edited since
    # (an edit after the failing run means the agent may have fixed it without rerunning).
    confidence = "high" if run.exact and not c.hedged and not lk.edits_after else "medium"
    cmd = _short_cmd(run.command)
    return Finding(
        rule_id=MISMATCH, severity="medium", confidence=confidence,
        message=f'Agent said "{c.text}" but its last {cmd} run shows {_fail_phrase(run)} (line {run.result_line or run.event_line}).',
        evidence=[Evidence(line=c.line, role="claim", text=c.text)] + _run_evidence(run)
        + [Evidence(line=e.line, role="edit", text=f"{e.tool_name} after the failing run", tool_use_id=e.tool_use_id)
           for e in lk.edits_after[:3]],
        fix=f"Rerun {cmd} and report the actual result.")


def without_evidence(c: Claim, runs: list[TestRun]) -> Finding | None:
    if c.kind not in ("tests_pass", "bug_fixed") or any(r.event_line < c.line for r in runs):
        return None
    return Finding(
        rule_id=NO_EVIDENCE, severity="low", confidence="medium",
        message=f'Agent said "{c.text}" (line {c.line}) but ran no tests in this session.',
        evidence=[Evidence(line=c.line, role="claim", text=c.text)],
        fix="Run the test suite and report its actual result.")


def stale(lk: Link) -> Finding | None:
    c, run = lk.claim, lk.run
    if c.kind not in CHECKED_KINDS or not run or run.status != "pass" or not lk.edits_after:
        return None
    cmd = _short_cmd(run.command)
    return Finding(
        rule_id=STALE, severity="low", confidence="medium",
        message=f'Agent said "{c.text}" but code was edited {len(lk.edits_after)}x after its last passing {cmd} run (line {run.event_line}).',
        evidence=[Evidence(line=c.line, role="claim", text=c.text)] + _run_evidence(run)
        + [Evidence(line=e.line, role="edit", text=f"{e.tool_name}", tool_use_id=e.tool_use_id) for e in lk.edits_after[:3]],
        fix=f"Rerun {cmd} after the last edit and report the result.")


def run_rules(claims: list[Claim], runs: list[TestRun], events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []
    # A message that scopes one claim ("Leap-year tests now pass. Both are fixed.") scopes the rest of it.
    scope_by_line = {c.line: c.scope for c in claims if c.scope}
    claims = [c if c.scope or c.line not in scope_by_line or WHOLE_SUITE.search(c.text) else c.model_copy(update={"scope": scope_by_line[c.line]})
              for c in claims]
    # When one message makes several claims, cite the most specific one ("all tests pass" over "fixed").
    priority = {"tests_pass": 0, "build_ok": 1, "bug_fixed": 2, "task_done": 3}
    for c in sorted(claims, key=lambda c: (c.line, priority[c.kind])):
        lk = link(c, runs, events)
        for f in (mismatch(lk), without_evidence(c, runs), stale(lk)):
            if f:
                findings.append(f)
    # One finding per rule per cited run: keep the first claim that fired.
    seen, out = set(), []
    for f in findings:
        key = (f.rule_id, next((e.line for e in f.evidence if e.role == "test_call"), f.evidence[0].line))
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


class Report(BaseModel):
    path: str
    events: list[Event]
    runs: list[TestRun]
    claims: list[Claim]
    findings: list[Finding]
    seconds: float


def check_events(events: list[Event], use_llm: bool = True, path: str = "") -> Report:
    t = time.perf_counter()
    runs = find_test_runs(events)
    cl = claims_mod.find_claims(events, use_llm=use_llm)
    findings = run_rules(cl, runs, events)
    return Report(path=path, events=events, runs=runs, claims=cl, findings=findings, seconds=time.perf_counter() - t)


def check_file(path: str | Path, use_llm: bool = True) -> Report:
    t = time.perf_counter()
    rep = check_events(parse_file(path), use_llm=use_llm, path=str(path))
    rep.seconds = time.perf_counter() - t
    return rep
