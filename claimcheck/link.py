"""Link each claim to the test run it rests on, and note edits made after that run."""

import re

from pydantic import BaseModel

from .models import Claim, Event, TestRun

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Bash that writes files: redirection (not 2>&1 / >/dev/null), sed -i, tee, heredoc to file, mv/cp/rm, patch.
BASH_WRITE = re.compile(r"(?<![0-9&])>>?\s*(?!&|/dev/null)\S|\bsed\s+-i|\btee\b|\bpatch\b|\bgit (?:apply|checkout|restore)\b|"
                        r"^\s*(?:mv|cp|rm)\s|&&\s*(?:mv|cp|rm)\s|\bperl\s+-pi")


class Link(BaseModel):
    claim: Claim
    run: TestRun | None
    edits_after: list[Event] = []


def is_edit(e: Event) -> bool:
    if e.kind != "tool_use":
        return False
    if e.tool_name in EDIT_TOOLS:
        return True
    return e.tool_name == "Bash" and bool(BASH_WRITE.search((e.tool_input or {}).get("command", "")))


def _scope_match(scope: str, cmd: str) -> bool:
    words = [w for w in re.split(r"[\s/:.,]+", scope.lower()) if len(w) > 3 and w not in ("tests", "test", "suite", "the")]
    return any(w in cmd.lower() for w in words)


def link(claim: Claim, runs: list[TestRun], events: list[Event]) -> Link:
    before = [r for r in runs if r.event_line < claim.line]
    run = None
    if claim.scope:
        scoped = [r for r in before if _scope_match(claim.scope, r.command)]
        run = scoped[-1] if scoped else None
    if run is None and before:
        run = before[-1]
    edits = []
    if run:
        edits = [e for e in events if run.event_line < e.line < claim.line and is_edit(e)]
    return Link(claim=claim, run=run, edits_after=edits)
