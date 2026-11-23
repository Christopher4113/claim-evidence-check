#!/usr/bin/env bash
# Run one real Claude Code task on a fresh copy of a demo repo and keep its session log.
# usage: scripts/gen_sessions.sh <name> <py_dates|ts_cart> <model> "<prompt>"
set -euo pipefail
name=$1 repo=$2 model=$3 prompt=$4
root=$(cd "$(dirname "$0")/.." && pwd)
work="$HOME/cec-runs/$name"
rm -rf "$work" && mkdir -p "$HOME/cec-runs"
rsync -a --exclude .pytest_cache --exclude .venv "$root/demo_repos/$repo/" "$work/"
cd "$work" && git init -q && git add -A && git commit -qm init
claude -p "$prompt" --model "$model" --allowedTools "Bash Edit Write Read Glob Grep" \
  --output-format json > "$root/scripts/out/$name.json" 2>&1 || true
proj="$HOME/.claude/projects/$(echo "$work" | sed 's#[/ _.]#-#g')"
latest=$(ls -t "$proj"/*.jsonl | head -1)
cp "$latest" "$root/sessions/raw_$name.jsonl"
echo "$name -> $latest"
