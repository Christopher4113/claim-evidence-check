"""Copy a real session and replace ONLY the text of its final assistant message.

usage: python scripts/make_synthetic.py raw.jsonl out.jsonl "new final message"
"""

import json
import sys

src, dst, text = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(src).read().splitlines()
for i in range(len(lines) - 1, -1, -1):
    try:
        d = json.loads(lines[i])
    except Exception:
        continue
    blocks = (d.get("message") or {}).get("content")
    if d.get("type") == "assistant" and isinstance(blocks, list) and any(b.get("type") == "text" for b in blocks):
        for b in blocks:
            if b.get("type") == "text":
                b["text"] = text
        lines[i] = json.dumps(d, ensure_ascii=False)
        break
open(dst, "w").write("\n".join(lines) + "\n")
print(f"{dst}: replaced final message at line {i + 1}")
