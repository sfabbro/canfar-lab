#!/usr/bin/env bash
# Install git pre-push hook that runs the harness verify tier (ci-local).
set -euo pipefail

ROOT="${1:-.}"
ROOT="$(cd "$ROOT" && pwd)"
cd "$ROOT"
HOOK="$ROOT/.git/hooks/pre-push"
CONFIG="$ROOT/.cursor/harness/config.json"

if [[ ! -d "$ROOT/.git" ]]; then
  echo "Error: no .git in $ROOT"
  exit 1
fi

VERIFY_CMD=""
if [[ -f "$CONFIG" ]]; then
  VERIFY_CMD="$(python3 -c "
import json
with open('$CONFIG') as f:
    c = json.load(f)
cmds = c.get('verify') or []
print(' && '.join(cmds) if cmds else '')
")"
fi

if [[ -z "$VERIFY_CMD" ]]; then
  if command -v pixi >/dev/null 2>&1 && { [[ -f pixi.toml ]] || grep -q 'tool.pixi' pyproject.toml 2>/dev/null; }; then
    VERIFY_CMD="pixi run ci-local"
  elif [[ -x scripts/ci_test_only.sh ]]; then
    VERIFY_CMD="./scripts/ci_test_only.sh"
  elif [[ -x scripts/ci_local.sh ]]; then
    VERIFY_CMD="./scripts/ci_local.sh"
  else
    echo "Error: could not detect verify command; set verify in .cursor/harness/config.json"
    exit 1
  fi
fi

mkdir -p "$(dirname "$HOOK")"
cat >"$HOOK" <<EOF
#!/bin/bash
set -euo pipefail
export PATH="\$HOME/.pixi/bin:\$PATH"
echo "Running harness verify tier before push..."
cd "$ROOT"
$VERIFY_CMD || {
  echo "Verify failed. Push aborted (or use --no-verify)."
  exit 1
}
echo "Verify passed."
EOF
chmod +x "$HOOK"
echo "Installed pre-push hook at $HOOK"
echo "Runs: $VERIFY_CMD"
