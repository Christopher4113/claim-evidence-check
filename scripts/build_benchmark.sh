#!/usr/bin/env bash
# Run both modes on the labelled and held-out sets and write sessions/benchmark.json for the UI.
set -euo pipefail
cd "$(dirname "$0")/.."
for d in sessions sessions/heldout; do
  uv run python cli.py --all "$d" --no-llm --json > "$d/.nollm.json"
  uv run python cli.py --all "$d" --json > "$d/.llm.json"
done
uv run python - <<'PY'
import json
b = {k: json.load(open(f"sessions/.{f}.json")) for k, f in (("no-llm", "nollm"), ("llm", "llm"))}
b["heldout"] = {k: json.load(open(f"sessions/heldout/.{f}.json")) for k, f in (("no-llm", "nollm"), ("llm", "llm"))}
b["stacktrace"] = json.load(open("sessions/stacktrace_comparison.json"))
json.dump(b, open("sessions/benchmark.json", "w"), indent=2)
print("wrote sessions/benchmark.json")
PY
