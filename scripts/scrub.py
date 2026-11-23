"""Scrub a Claude Code session before committing it. Line numbers are preserved.

- user/assistant lines are kept; home path -> ~, username -> user, emails and tokens redacted
- every other line (api-request, attachment, system prompts...) becomes {"type": ..., "scrubbed": true}
- noisy per-line metadata (cwd, requestId, signatures...) is dropped

usage: python scripts/scrub.py raw.jsonl out.jsonl
"""

import json
import os
import re
import sys

HOME = os.path.expanduser("~")
USER = os.path.basename(HOME)
KEEP_KEYS = {"type", "message", "timestamp", "uuid", "parentUuid", "isSidechain", "isMeta", "sessionId", "toolUseResult"}
SECRETS = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9]{16,}|21st_[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def clean(s: str) -> str:
    s = s.replace(HOME, "~").replace(f"-Users-{USER}-", "-Users-user-")
    s = re.sub(rf"\b{re.escape(USER)}\b", "user", s)
    s = SECRETS.sub("<redacted>", s)
    return EMAIL.sub("<email>", s)


def scrub_line(raw: str) -> str:
    try:
        d = json.loads(raw)
    except Exception:
        return raw.strip()
    if not isinstance(d, dict):
        return "{}"
    if d.get("type") not in ("user", "assistant"):
        return json.dumps({"type": d.get("type"), "scrubbed": True})
    d = {k: v for k, v in d.items() if k in KEEP_KEYS}
    for b in (d.get("message") or {}).get("content") or []:
        if isinstance(b, dict) and b.get("type") == "thinking":
            b.pop("signature", None)
    return clean(json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    with open(src) as f, open(dst, "w") as o:
        for ln in f:
            o.write(scrub_line(ln) + "\n")
