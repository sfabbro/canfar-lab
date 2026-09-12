#!/usr/bin/env bash
# Sync ~/dsh review-bench sources into src/astroai_lab/data/review-bench/.
# Single source of truth remains ~/dsh; the pip package ships the copy.
# CI fails when the copy is stale (run this script, commit the result).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${DSH_SRC:-$HOME/dsh}"
DST="$ROOT/src/astroai_lab/data/review-bench"

[ -d "$SRC/presets/review-bench" ] || { echo "missing: $SRC/presets/review-bench" >&2; exit 1; }
[ -d "$SRC/skills/review-panel" ] || { echo "missing: $SRC/skills/review-panel" >&2; exit 1; }

mkdir -p "$DST/presets/review-bench" "$DST/skills" "$DST/bin" "$DST/project-template/.dsh"
cp "$SRC/presets/review-bench/agent.cordis.yml" "$DST/presets/review-bench/agent.cordis.yml"
cp "$SRC/presets/review-bench/preset.yml" "$DST/presets/review-bench/preset.yml"
rm -rf "$DST/skills/review-panel"
cp -r "$SRC/skills/review-panel" "$DST/skills/review-panel"
cp "$SRC/panel.sh" "$SRC/dsh-web.sh" "$SRC/validate.mjs" "$SRC/HOWTO.md" "$SRC/README.md" "$DST/"
cp "$SRC/panel.sh" "$SRC/dsh-web.sh" "$DST/bin/"

# Managed-install overrides (re-applied on every sync; do not edit by hand):
# 1. preset skill root -> ~/.astroai/lab/review-bench/skills (+ ~/dsh fallback)
python3 - "$DST/presets/review-bench/agent.cordis.yml" <<'PY'
import sys
p = sys.argv[1]
text = open(p).read()
old = "      - !!js process.env.HOME + '/dsh/skills'\n"
new = ("      - !!js (process.env.ASTROAI_LAB_DATA || process.env.HOME + '/.astroai/lab')"
       " + '/review-bench/skills'\n      - !!js process.env.HOME + '/dsh/skills'\n")
assert old in text, "upstream preset skill-root line changed — update this script"
open(p, "w").write(text.replace(old, new))
print("patched customSkillDirs -> managed bench + ~/dsh fallback")
PY

echo "ok: synced $SRC -> $DST"
if command -v node >/dev/null 2>&1; then
  node "$DST/validate.mjs" --root "$DST" || echo "(validate needs a dsh install: --node-modules <dir>)"
else
  echo "(node unavailable — skipped validate.mjs)"
fi
