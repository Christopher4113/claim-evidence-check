"""Claude Code session JSONL -> ordered list[Event].

Written against real files in ~/.claude/projects/<dir>/<id>.jsonl (Claude Code 2.1.x):
- only `type` in {"user", "assistant"} lines carry the conversation; everything else
  (attachment, api-request-blob, file-history-*, cost-state, ...) is skipped.
  `api-request-blob` lines repeat tool_use/tool_result blocks and must not be counted.
- each assistant content block is its own line (text / thinking / tool_use).
- user lines hold either the prompt (string or text blocks) or tool_result blocks.
- `isMeta` user lines are injected skill/command text, not the person typing.
- `isSidechain` lines belong to subagents; ignored here.
"""

import json
import logging
from pathlib import Path

from .models import Event

log = logging.getLogger(__name__)


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def parse_lines(lines) -> list[Event]:
    events: list[Event] = []
    for n, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
            if not isinstance(d, dict) or d.get("type") not in ("user", "assistant") or d.get("isSidechain"):
                continue
            ts = d.get("timestamp")
            content = (d.get("message") or {}).get("content")
            if d["type"] == "user":
                if isinstance(content, str):
                    if not d.get("isMeta"):
                        events.append(Event(line=n, kind="user", text=content, timestamp=ts))
                    continue
                for b in content or []:
                    if b.get("type") == "tool_result":
                        events.append(Event(
                            line=n, kind="tool_result", text=_result_text(b.get("content")),
                            tool_use_id=b.get("tool_use_id"), is_error=bool(b.get("is_error")), timestamp=ts))
                    elif b.get("type") == "text" and not d.get("isMeta"):
                        events.append(Event(line=n, kind="user", text=b.get("text", ""), timestamp=ts))
            else:
                for b in content or []:
                    if b.get("type") == "text" and b.get("text", "").strip():
                        events.append(Event(line=n, kind="assistant_text", text=b["text"], timestamp=ts))
                    elif b.get("type") == "tool_use":
                        events.append(Event(
                            line=n, kind="tool_use", tool_name=b.get("name"), tool_input=b.get("input") or {},
                            tool_use_id=b.get("id"), timestamp=ts))
        except Exception as e:  # never crash on an unknown line
            log.warning("skipping line %d: %s", n, e)
    return events


def parse_file(path: str | Path) -> list[Event]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse_lines(f)
