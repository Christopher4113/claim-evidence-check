from pathlib import Path

import pytest

from claimcheck.rules import MISMATCH, NO_EVIDENCE, STALE, check_file
from claimcheck.testruns import is_test_command, parse_output

FX = Path(__file__).parent / "fixtures"

OUTPUTS = {
    "pytest": ("FAILED tests/t.py::test_a - assert 1 == 2\n1 failed, 5 passed in 0.31s",
               "......\n6 passed in 0.20s"),
    "jest": ("FAIL src/sum.test.js\n  ● sum › adds\nTests:       2 failed, 10 passed, 12 total\nTime: 1s",
             "PASS src/sum.test.js\nTests:       12 passed, 12 total"),
    "vitest": (" FAIL  src/date.test.ts > parse > handles DST\n Test Files  1 failed | 2 passed (3)\n      Tests  1 failed | 9 passed (10)",
               " ✓ src/date.test.ts (10)\n Test Files  3 passed (3)\n      Tests  10 passed (10)"),
    "go": ("--- FAIL: TestParse (0.00s)\nFAIL\nFAIL\texample.com/dates\t0.01s",
           "ok  \texample.com/dates\t0.01s"),
    "cargo": ("test parse::tz ... FAILED\ntest result: FAILED. 1 passed; 2 failed; 0 ignored",
              "test result: ok. 3 passed; 0 failed; 0 ignored"),
    "bun": (" 3 pass\n 1 fail\n 9 expect() calls", " 4 pass\n 0 fail"),
}


@pytest.mark.parametrize("tool", OUTPUTS)
def test_parsers_fail_and_pass(tool):
    fail, ok = OUTPUTS[tool]
    f = parse_output(fail, is_error=True)
    assert f["status"] == "fail" and f["exact"] and f["failed"] >= 1 and f["excerpt"]
    p = parse_output(ok)
    assert p["status"] == "pass" and p["exact"] and p["failed"] == 0


def test_failing_names_and_excerpt_are_real_lines():
    r = parse_output(OUTPUTS["pytest"][0], True)
    assert r["failing_names"] == ["tests/t.py::test_a"]
    assert r["excerpt"] == "1 failed, 5 passed in 0.31s"


def test_truncated_output_is_unknown():
    out = "Exit code 1\n<persisted-output>\nOutput too large (88KB).\nPreview (first 2KB):\n....F...."
    assert parse_output(out, True)["status"] == "unknown"
    assert parse_output("collecting ... \n....", False)["status"] == "unknown"


def test_exit_code_only_is_fail_not_exact():
    r = parse_output("Exit code 2\nImportError: no module named foo", True)
    assert r["status"] == "fail" and not r["exact"]


def test_test_command_detection():
    for c in ["pytest -q", "uv run pytest tests/", "python -m pytest", "cd app && npm test -- --run",
              "npx vitest run", "pnpm run test:unit", "go test ./...", "cargo test", "make test",
              "CI=1 yarn test", "timeout 60 npx jest", "uv run --offline pytest -q", "ls; (uv run pytest -q 2>&1 || true)"]:
        assert is_test_command(c), c
    for c in ["pip install pytest", "grep pytest README.md", "cat package.json", "echo go test"]:
        assert not is_test_command(c), c


def rules(name):
    return check_file(FX / name, use_llm=False).findings


def test_mismatch_high_confidence():
    (f,) = rules("mismatch.jsonl")
    assert f.rule_id == MISMATCH and f.severity == "medium" and f.confidence == "high" and f.notifies
    assert "2 failed" in f.message and "uv run pytest -q" in f.message
    roles = {e.role: e for e in f.evidence}
    assert roles["test_result"].text == "2 failed, 6 passed in 0.12s"
    assert roles["test_call"].tool_use_id == "t1"


def test_honest_fail_is_not_flagged():
    assert rules("honest_fail.jsonl") == []


def test_links_latest_run_not_older_pass():
    (f,) = rules("latest_run.jsonl")
    assert f.rule_id == MISMATCH
    assert next(e for e in f.evidence if e.role == "test_call").tool_use_id == "t2"


def test_hedged_claim_is_medium_confidence():
    (f,) = rules("hedged.jsonl")
    assert f.rule_id == MISMATCH and f.confidence == "medium" and not f.notifies


def test_edit_after_passing_run_is_stale():
    (f,) = rules("stale.jsonl")
    assert f.rule_id == STALE and f.severity == "low"


def test_claim_without_any_test_run():
    assert [f.rule_id for f in rules("no_tests.jsonl")] == [NO_EVIDENCE]


def test_malformed_line_is_skipped():
    rep = check_file(FX / "malformed.jsonl", use_llm=False)
    assert [f.rule_id for f in rep.findings] == [MISMATCH]


def test_mid_turn_narration_is_not_a_claim():
    assert rules("midturn.jsonl") == []


def test_rtk_compressed_pytest_output():
    r = parse_output("Pytest: 2 passed, 6 failed\n\nFailures:\n1. [FAIL] test_leap_century\n     tests/x.py:11", True)
    assert r["status"] == "fail" and r["failed"] == 6 and r["failing_names"] == ["test_leap_century"]


def test_scoped_claim_with_unrelated_failures_is_not_flagged():
    from claimcheck.link import Link
    from claimcheck.models import Claim, TestRun
    from claimcheck.rules import mismatch
    run = TestRun(event_line=1, result_line=2, tool_use_id="t", command="pytest", status="fail", exact=True,
                  passed=4, failed=4, failing_names=["test_business_days_excludes_end", "test_parse_iso_offset"])
    ok = Claim(line=5, text="Leap-year tests now pass.", kind="tests_pass", scope="leap-year")
    bad = Claim(line=5, text="Parse tests now pass.", kind="tests_pass", scope="parse")
    assert mismatch(Link(claim=ok, run=run)) is None
    assert mismatch(Link(claim=bad, run=run)) is not None


def test_message_reporting_failures_is_not_a_claim():
    from claimcheck.claims import find_claims
    from claimcheck.session import parse_lines
    import json
    msg = {"type": "assistant", "message": {"content": [{"type": "text", "text":
           "Fixed bulk and coupon; both pass. npm test: 5 failed, 3 passed.\n| fixed coupon | 0 | -3 |"}]}}
    assert find_claims(parse_lines([json.dumps(msg)]), use_llm=False) == []


def test_stop_hook_blocks_high_confidence_mismatch_and_allows_others():
    from claimcheck.hook import decide
    out = decide({"transcript_path": str(FX / "mismatch.jsonl"), "stop_hook_active": False})
    assert out["decision"] == "block"
    assert "2 failed" in out["reason"] and "tests/test_dates.py::test_tz" in out["reason"]
    assert decide({"transcript_path": str(FX / "hedged.jsonl"), "stop_hook_active": False}) is None
    assert decide({"transcript_path": str(FX / "mismatch.jsonl"), "stop_hook_active": True}) is None
