#!/usr/bin/env bash
# ponytail: one-shot bootstrap; upgrade path = copy template from harness-coding skill
set -euo pipefail

ROOT="${1:-.}"
HARNESS="$ROOT/.cursor/harness"
SKILL="${HOME}/.cursor/skills/harness-coding"
TEMPLATE="$SKILL/templates"

mkdir -p "$HARNESS"/{trajectories,failures,proposals,archive,state}

if [[ ! -f "$HARNESS/playbook.md" ]]; then
  cat >"$HARNESS/playbook.md" <<'EOF'
# Harness Playbook

## Bullets

- id: verify-tiers
  desc: verify_fast during edits; verify (ci-local) before push; verify_full only when human opts in.

- id: file-memory
  desc: Put durable notes in .cursor/harness/ — not long chat scrollback.

- id: minimal-diff
  desc: Smallest correct change; match existing repo style and tools.
EOF
fi

if [[ -f "$TEMPLATE/playbook-verify-tiers.md" ]] && ! grep -q '^- id: verify-tiers' "$HARNESS/playbook.md" 2>/dev/null; then
  cat "$TEMPLATE/playbook-verify-tiers.md" >>"$HARNESS/playbook.md"
fi

if [[ ! -f "$HARNESS/config.json" ]]; then
  if [[ -f "$TEMPLATE/config.json" ]]; then
    cp "$TEMPLATE/config.json" "$HARNESS/config.json"
  else
    cat >"$HARNESS/config.json" <<'EOF'
{
  "verify_fast": ["pixi run preflight-push"],
  "verify": ["pixi run ci-local"],
  "verify_full": [],
  "reflect_min_turns": 5,
  "reflect_min_minutes": 45
}
EOF
  fi
fi

if [[ ! -f "$HARNESS/.gitignore" ]]; then
  cat >"$HARNESS/.gitignore" <<'EOF'
trajectories/
failures/
state/
proposals/rejected.md
EOF
fi

if [[ ! -f "$ROOT/.cursor/hooks.json" ]]; then
  mkdir -p "$ROOT/.cursor/hooks"
  cat >"$ROOT/.cursor/hooks.json" <<'EOF'
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": ".cursor/hooks/harness-session-start.sh"
      }
    ]
  }
}
EOF
  cp "$SKILL/hooks/harness-session-start.sh" "$ROOT/.cursor/hooks/"
  chmod +x "$ROOT/.cursor/hooks/"*.sh
fi

echo "Harness ready at $HARNESS"
