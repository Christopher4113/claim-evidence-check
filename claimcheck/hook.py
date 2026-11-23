"""Claude Code Stop hook: block a false "done" and hand the agent its own evidence.

settings.json:
  {"hooks": {"Stop": [{"hooks": [{"type": "command",
      "command": "uv run --project /path/to/claim-evidence-check python -m claimcheck.hook"}]}]}}

Reads the hook input on stdin ({"transcript_path", "stop_hook_active", "last_assistant_message"?...}),
runs the rules locally (--no-llm, nothing leaves the machine) on the current turn only, and on a
high-confidence claim-evidence-mismatch prints {"decision": "block", "reason": ...}. Otherwise allows the stop.
"""

import json
import sys

from .models import Event
from .rules import MISMATCH, check_events
from .session import parse_file


def decide(hook_input: dict) -> dict | None:
    if hook_input.get("stop_hook_active"):
        return None  # already steered once this stop; don't loop
    events = parse_file(hook_input["transcript_path"])
    last = hook_input.get("last_assistant_message")
    texts = [e for e in events if e.kind == "assistant_text"]
    if last and (not texts or texts[-1].text.strip() != last.strip()):
        # final message not flushed to the transcript yet
        events.append(Event(line=(events[-1].line + 1) if events else 1, kind="assistant_text", text=last))
    # Only judge claims made since the person's last message.
    start = max((i for i, e in enumerate(events) if e.kind == "user"), default=0)
    rep = check_events(events, use_llm=False)
    turn_line = events[start].line if events else 0
    for f in rep.findings:
        claim = next(e for e in f.evidence if e.role == "claim")
        if f.rule_id == MISMATCH and f.confidence == "high" and claim.line >= turn_line:
            run = next(r for r in rep.runs if r.tool_use_id == next(e.tool_use_id for e in f.evidence if e.role == "test_call"))
            names = ", ".join(run.failing_names) or run.excerpt
            from .rules import _fail_phrase, _short_cmd
            return {"decision": "block",
                    "reason": f"Your last {_short_cmd(run.command)} run (line {run.result_line or run.event_line}) shows "
                              f"{_fail_phrase(run)}: {names}. Don't report success. Fix it, or tell the user what still fails."}
    return None


def main():
    out = decide(json.load(sys.stdin))
    if out:
        print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
