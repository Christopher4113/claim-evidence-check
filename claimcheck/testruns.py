"""Detect Bash calls that ran tests, and parse their output exactly.

Never guess: if no runner summary line is found the run is `unknown`, unless the
tool result is flagged as an error with a non-zero exit code (then `fail`, exact=False).
"""

import re
import shlex

from .models import Event, TestRun

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
WRAPPERS = {"uv", "run", "poetry", "pipenv", "npx", "pnpx", "bunx", "exec", "env", "time", "command", "sudo", "dotenv", "--"}
TEST_RUNNERS = {"pytest", "py.test", "jest", "vitest"}
SUBCMD_RUNNERS = {("go", "test"), ("cargo", "test"), ("make", "test"), ("npm", "test"), ("pnpm", "test"),
                  ("yarn", "test"), ("bun", "test"), ("npm", "t")}


def _segment_runs_tests(seg: str) -> bool:
    seg = seg.strip().lstrip("(").rstrip(")").strip()  # (subshell)
    try:
        toks = shlex.split(seg)
    except ValueError:
        toks = seg.split()
    i, in_wrapper = 0, False
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t) or t in WRAPPERS:
            in_wrapper = t in WRAPPERS
            i += 1
        elif in_wrapper and t.startswith("-"):  # uv run --offline --frozen pytest
            i += 1
        elif t == "timeout" and i + 1 < len(toks):
            i += 2
        elif re.fullmatch(r"python[0-9.]*", t) and toks[i + 1:i + 3] == ["-m", "pytest"]:
            return True
        else:
            break
    rest = toks[i:]
    if not rest:
        return False
    head = rest[0].rsplit("/", 1)[-1]
    if head in TEST_RUNNERS:
        return True
    if len(rest) >= 2 and (head, rest[1]) in SUBCMD_RUNNERS:
        return True
    # npm|pnpm|yarn run test[:x]
    if head in ("npm", "pnpm", "yarn", "bun") and len(rest) >= 3 and rest[1] == "run" and rest[2].startswith("test"):
        return True
    return False


def is_test_command(cmd: str) -> bool:
    return any(_segment_runs_tests(s.strip()) for s in SEGMENT_SPLIT.split(cmd or "") if s.strip())


def _counts(s: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for n, word in re.findall(r"(\d+)\s+(failed|passed|errors?|skipped|xfailed|xpassed|todo|total)", s):
        key = "error" if word.startswith("error") else word
        out[key] = out.get(key, 0) + int(n)
    return out


def _pytest(text: str):
    lines = text.splitlines()
    summary = None
    for ln in reversed(lines):
        s = ln.strip().strip("=").strip()
        if re.search(r"\bin [\d.]+s\b", s) and re.search(r"\d+ (failed|passed|errors?|skipped)", s):
            summary = ln.strip()
            break
        if re.search(r"\bno tests ran\b", s):
            return dict(status="unknown", exact=True, excerpt=ln.strip())
    if not summary:
        return None
    c = _counts(summary)
    failed = c.get("failed", 0) + c.get("error", 0)
    names = [m for m in re.findall(r"^(?:FAILED|ERROR)\s+(\S+)", text, re.M)]
    return dict(status="fail" if failed else ("pass" if c.get("passed") else "unknown"), exact=True,
                passed=c.get("passed", 0), failed=failed, failing_names=names, excerpt=summary)


def _jest_vitest(text: str):
    tests = re.search(r"^\s*Tests:?\s+(.*\d+\s+(?:failed|passed).*)$", text, re.M)
    files = re.search(r"^\s*Test Files:?\s+(.*\d+\s+(?:failed|passed).*)$", text, re.M)
    if not tests and not files:
        return None
    excerpt = "\n".join(m.group(0).strip() for m in (files, tests) if m)
    c = _counts(tests.group(1) if tests else files.group(1))
    failed = c.get("failed", 0)
    if not tests and files:  # only file counts known
        failed = _counts(files.group(1)).get("failed", 0)
    names = re.findall(r"^\s*(?:FAIL|×|✗|✕)\s+(.+?)\s*$", text, re.M)
    names = [re.sub(r"\s+\d+(?:\.\d+)?m?s$", "", n) for n in names]  # drop vitest timings
    names = [n for n in dict.fromkeys(names) if not n.startswith("Tests")]
    return dict(status="fail" if failed else ("pass" if c.get("passed") else "unknown"), exact=True,
                passed=c.get("passed"), failed=failed, failing_names=names, excerpt=excerpt)


def _go(text: str):
    fails = re.findall(r"^\s*--- FAIL: (\S+)", text, re.M)
    pkg_fail = re.findall(r"^FAIL\s+\S+.*$", text, re.M)
    pkg_ok = re.findall(r"^ok\s+\S+.*$", text, re.M)
    if not (fails or pkg_fail or pkg_ok):
        return None
    passes = re.findall(r"^\s*--- PASS: ", text, re.M)
    failed = len(fails) or len(pkg_fail)
    return dict(status="fail" if failed else "pass", exact=True, passed=len(passes) or None, failed=failed,
                failing_names=fails, excerpt="\n".join((pkg_fail + pkg_ok)[:5]))


def _cargo(text: str):
    results = re.findall(r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed.*$", text, re.M)
    if not results:
        return None
    passed = sum(int(r[1]) for r in results)
    failed = sum(int(r[2]) for r in results)
    lines = re.findall(r"^test result: .*$", text, re.M)
    names = re.findall(r"^test (\S+) \.\.\. FAILED", text, re.M)
    return dict(status="fail" if failed else "pass", exact=True, passed=passed, failed=failed,
                failing_names=names, excerpt="\n".join(lines[:3]))


def _bun_node(text: str):
    # bun: " 4 pass\n 0 fail"   node --test: "ℹ pass 13\nℹ fail 0"
    p = re.search(r"^\s*(?:ℹ\s+pass\s+(\d+)|(\d+)\s+pass)\s*$", text, re.M)
    f = re.search(r"^\s*(?:ℹ\s+fail\s+(\d+)|(\d+)\s+fail)\s*$", text, re.M)
    if not (p and f):
        return None
    passed, failed = int(p.group(1) or p.group(2)), int(f.group(1) or f.group(2))
    names = re.findall(r"^\s*(?:\(fail\)|✖)\s+(.+?)\s*(?:\[[\d.]+m?s\]|\([\d.]+m?s\))?$", text, re.M)
    return dict(status="fail" if failed else "pass", exact=True, passed=passed, failed=failed,
                failing_names=names, excerpt=f"{p.group(0).strip()}\n{f.group(0).strip()}")


def _rtk(text: str):
    # Output-compressing shell hooks (rtk) rewrite runner output, e.g. "Pytest: 2 passed, 6 failed" + "1. [FAIL] name".
    m = re.search(r"^(?:Pytest|Jest|Vitest|Cargo test|Go test):\s+(.*\d+\s+(?:passed|failed).*)$", text, re.M | re.I)
    if not m:
        return None
    c = _counts(m.group(1))
    failed = c.get("failed", 0) + c.get("error", 0)
    names = re.findall(r"^\s*\d+\.\s+\[FAIL\]\s+(\S+)", text, re.M)
    return dict(status="fail" if failed else ("pass" if c.get("passed") else "unknown"), exact=True,
                passed=c.get("passed", 0), failed=failed, failing_names=names, excerpt=m.group(0).strip())


PARSERS = (_cargo, _go, _jest_vitest, _bun_node, _pytest, _rtk)


def parse_output(text: str, is_error: bool = False) -> dict:
    text = ANSI.sub("", text or "")
    for p in PARSERS:
        r = p(text)
        if r:
            names = r.get("failing_names") or re.findall(r"^(?:FAILED|ERROR)\s+(\S+)", text, re.M)
            r["failing_names"] = names[:5]
            return r
    m = re.search(r"^(?:Error: )?Exit code (\d+)", text, re.M)
    truncated = re.search(r"<persisted-output>|Output too large|lines truncated|\[truncated\]", text)
    if m and m.group(1) != "0" and is_error and not truncated:
        return dict(status="fail", exact=False, excerpt=m.group(0))
    return dict(status="unknown", exact=False, excerpt="")


def find_test_runs(events: list[Event]) -> list[TestRun]:
    results = {e.tool_use_id: e for e in events if e.kind == "tool_result"}
    runs = []
    for e in events:
        if e.kind != "tool_use" or e.tool_name != "Bash":
            continue
        cmd = (e.tool_input or {}).get("command", "")
        if not is_test_command(cmd):
            continue
        res = results.get(e.tool_use_id)
        parsed = parse_output(res.text, res.is_error) if res else dict(status="unknown", exact=False)
        runs.append(TestRun(event_line=e.line, result_line=res.line if res else None,
                            tool_use_id=e.tool_use_id or "", command=cmd.strip(), **parsed))
    return runs
