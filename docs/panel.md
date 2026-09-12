# AstroAI Panel (`astroai panel` / `astroai review`)

![AstroAI](../src/astroai_lab/data/brand/astroai-logo.png)

Headless-first port of the `~/dsh` review bench (8-persona **AstroAI Panel**
preset + `review-panel` skill): freeze → blind-parallel → audit, writing
`panel/<date>-<slug>/{00-brief.md,01-findings.json,02-report.md}`.

## One install, one command

```bash
uv tool install --force git+https://github.com/astroai/canfar-lab.git@main
astroai agent setup --recommended   # recommended agents + dsh / review-bench
astroai panel doctor                # route, keys, pin sanity
astroai panel run /scratch/src/zensus "C1: 90% intervals cover 90% on 2024 split; C2: bias slope |.|<0.01" smoke
```

`astroai review` is the same command. `--dry-run` prints the resolved repo,
panel id, credential route, and task prompt without executing.

## Catalog CLI

| Command | Behavior |
|---------|----------|
| `astroai panel doctor` | dsh presence, active route, keys, pin vs `support.yaml` |
| `astroai panel models` | role → preset / catalog pins for the active router |
| `astroai panel routers` | supported routers + key presence |
| `astroai agent routers` | same router catalog |
| `astroai agent list --supported` | filter to recommended agents |
| `astroai agent setup --recommended` | install+setup recommended set (+ panel/dsh) |

Supported routers and role pins live in
[`src/astroai_lab/data/agent/support.yaml`](../src/astroai_lab/data/agent/support.yaml).

## Surfaces

- Terminal everywhere (ghostty-web, webterm, vscode/notebook terminals, plain
  CLI): `astroai panel run` — headless dsh one-shot. If OpenCode Go rejects
  headless (`MissingSessionID`), the run auto-falls back to the next available
  provider (DeepSeek official preferred).
- Laptop browser: `astroai panel web /scratch/src/torchregress --port 3080`.
  On Skaha contributed sessions the web UI is not proxyable behind `/proxy`
  — the command warns and exits 2; use `panel run`.
- Marimo notebooks (no shell): `from astroai_lab.panel import run_panel`
  — `run_panel(repo, claims, slug)` calls the same logic via subprocess.

## Other commands

- `astroai panel status panel/<date>-<slug>` — verdict table from `02-report.md`.
- `astroai agent env --with-dsh` — key presence (never values) + active route.
- `astroai init mylab --with-dsh` — scaffold `.dsh/cordis.patch.yml` + README.

## Credentials

Shared dotenv `~/.astroai/lab/.env` (0600) + `agent-env.sh`: preference order
from `support.yaml` (OpenCode Go → DeepSeek → Gemini → OpenAI → Anthropic),
from env → shared `.env` → opencode/Codex auth files.
`~/.dsh/settings.yaml` gains the provider route + default model but a
user-pinned `agent-default-model.provider` is never overwritten (except
headless fallback). No key → `LabError` pointing at `opencode auth login`.

## Compatibility

- Existing `npx -y @deepseek-ai/dsh --profile … --patch .dsh/cordis.patch.yml`
  invocations keep working; `~/dsh` stays the dev source and remains usable
  via shim when byte-identical to the vendored copy.
- `data/review-bench/` is a build-time copy: `scripts/sync-review-bench.sh`
  refreshes it from `~/dsh`, re-applies AstroAI Panel branding + skill-root
  overrides, and runs `validate.mjs`; CI fails when out of sync.
