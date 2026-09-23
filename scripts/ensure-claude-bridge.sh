#!/usr/bin/env bash
# Ensure Claude Code loads repo AGENTS.md via CLAUDE.md (@import).
# Claude Code reads CLAUDE.md, not AGENTS.md — Anthropic documents @AGENTS.md.
# Usage: ensure-claude-bridge.sh [repo-root ...]
# Default: all git roots under ~/src/{astroai,sfabbro} that have AGENTS.md.
set -euo pipefail

BRIDGE=$'@AGENTS.md\n'

ensure_one() {
  local root="$1"
  local agents="$root/AGENTS.md"
  local claude="$root/CLAUDE.md"
  [[ -f "$agents" ]] || return 0

  if [[ ! -e "$claude" ]]; then
    printf '%s\n' "$BRIDGE" >"$claude"
    echo "created $claude"
    return 0
  fi
  if [[ -L "$claude" ]]; then
    echo "skip $claude (symlink — leave as-is)"
    return 0
  fi
  if head -n 5 "$claude" | grep -qE '^@AGENTS\.md[[:space:]]*$'; then
    echo "ok $claude (already imports AGENTS.md)"
    return 0
  fi
  # Prepend import; keep existing Claude-specific content
  local tmp
  tmp="$(mktemp)"
  {
    printf '%s\n' "$BRIDGE"
    cat "$claude"
  } >"$tmp"
  mv "$tmp" "$claude"
  echo "prepended @AGENTS.md -> $claude"
}

if [[ $# -gt 0 ]]; then
  for r in "$@"; do ensure_one "$(cd "$r" && pwd)"; done
  exit 0
fi

SRC="${SRC:-$HOME/src}"
for org in astroai sfabbro; do
  base="$SRC/$org"
  [[ -d "$base" ]] || continue
  for dir in "$base"/*/; do
    [[ -d "${dir}.git" ]] || continue
    ensure_one "${dir%/}"
  done
done
