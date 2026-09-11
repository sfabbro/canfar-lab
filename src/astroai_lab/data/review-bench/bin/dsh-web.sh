#!/usr/bin/env bash
# dsh web for any repo here — including from inside a CANFAR session.
#
#   ~/dsh/dsh-web.sh [<repo-dir>] [-- <web-app flags>]
#
# Adds --patch <repo>/.dsh/cordis.patch.yml when the repo has one (the review
# bench itself comes from the installed web-profile layer, so it is always
# on). Extra flags after `--` reach the web app, e.g.:
#
#   ~/dsh/dsh-web.sh /scratch/src/torchz -- --port 8080
#
# CANFAR note: a contributed session forwards only its own app port to your
# browser — a `dsh web` on any other port is not reachable from outside. The
# wrapper still boots (with --no-open on loopback), but for terminal-only
# sessions prefer the terminal panel runner (HOWTO.md §10):
#
#   ~/dsh/panel.sh /scratch/src/torchregress "C1: ...; C2: ..." my-slug
set -euo pipefail

repo="$PWD"
if [ $# -ge 1 ] && [ -d "${1}" ]; then repo="$1"; shift; fi
if [ $# -ge 1 ] && [ "${1}" = "--" ]; then shift; fi

patch=()
if [ -f "$repo/.dsh/cordis.patch.yml" ]; then
  patch=(--patch "$repo/.dsh/cordis.patch.yml")
fi

if [ -n "${skaha_sessionid:-}" ]; then
  echo "CANFAR session detected ($skaha_hostname): no local browser here;" \
    "serving with --no-open on loopback." >&2
  echo "The UI is only reachable if this session forwards the port to your browser" \
    "(most contributed sessions forward just their own app port — then use" \
    "~/dsh/panel.sh instead, HOWTO.md §10)." >&2
  # NOTE: dsh refuses --host 0.0.0.0 (remote-code-execution guard), so bind
  # loopback (the default) and let the session's own port proxy do the reaching.
  # shellcheck disable=SC2086
  exec npx -y @deepseek-ai/dsh --profile web ${patch[@]+"${patch[@]}"} \
    --no-open --port "${DSH_WEB_PORT:-3080}" "$@"
fi
