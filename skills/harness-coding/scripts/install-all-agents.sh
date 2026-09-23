#!/usr/bin/env bash
# Deprecated: use ~/.agent-home/scripts/install.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
while [[ "$REPO_ROOT" != "/" && ! -f "$REPO_ROOT/scripts/install.sh" ]]; do
  REPO_ROOT="$(dirname "$REPO_ROOT")"
done
if [[ -f "$REPO_ROOT/scripts/install.sh" ]]; then
  exec bash "$REPO_ROOT/scripts/install.sh" "$@"
fi
if [[ -x "$HOME/.agent-home/scripts/install.sh" ]]; then
  exec bash "$HOME/.agent-home/scripts/install.sh" "$@"
fi
echo "agent-home not found; clone sfabbro/agent-home" >&2
exit 1
