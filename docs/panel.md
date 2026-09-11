# Review panels (`astroai panel` / `astroai review`)

Headless-first port of the `~/dsh` review bench (8-persona `review-bench`
preset + `review-panel` skill): freeze → blind-parallel → audit, writing
`panel/<date>-<slug>/{00-brief.md,01-findings.json,02-report.md}`.

## One install, one command

```bash
uv pip install git+https://github.com/astroai/canfar-lab.git@main  # or upgrade-cadc-tools.sh --upgrade astroai-lab
astroai agent setup            # provisions ~/.astroai/lab/review-bench + ~/.dsh web layer + keys
astroai panel run /scratch/src/zensus "C1: 90% intervals cover 90% on 2024 split; C2: bias slope |.|<0.01" smoke
```

`astroai review` is the same command. `--dry-run` prints the resolved repo,
panel id, credential route, and task prompt without executing.

## Surfaces

- Terminal everywhere (ghostty-web, webterm, vscode/notebook terminals, plain
  CLI): `astroai panel run` — headless dsh one-shot.
- Laptop browser: `astroai panel web /scratch/src/torchregress --port 3080`.
  On Skaha contributed sessions the web UI is not proxyable behind `/proxy`
  (see `dsh-client-connection/lib/client.js:resolveBase`) — the command warns
  and exits 2; use `panel run`.
- Marimo notebooks (no shell): `from astroai_lab.panel import run_panel`
  — `run_panel(repo, claims, slug)` calls the same logic via subprocess.

## Other commands

- `astroai panel status panel/<date>-<slug>` — verdict table from `02-report.md`.
- `astroai agent env --with-dsh` — key presence (never values) + active route.
- `astroai init mylab --with-dsh` — scaffold `.dsh/cordis.patch.yml` + README.

## Credentials

Shared dotenv `~/.astroai/lab/.env` (0600) + `agent-env.sh`, same plumbing as
OpenRouter: `OPENCODE_API_KEY` (opencode Zen, no DeepSeek key needed) →
`GEMINI_API_KEY` → `DEEPSEEK_API_KEY` → `OPENAI_API_KEY` →
`ANTHROPIC_API_KEY`, from env → shared `.env` → opencode/Codex auth files.
`~/.dsh/settings.yaml` gains the provider route + default model but a
user-pinned `agent-default-model.provider` is never overwritten. No key →
`LabError` pointing at `opencode auth login`.

## Compatibility

- Existing `npx -y @deepseek-ai/dsh --profile … --patch .dsh/cordis.patch.yml`
  invocations keep working; `~/dsh` stays the dev source and remains usable
  via shim when byte-identical to the vendored copy.
- `data/review-bench/` is a build-time copy: `scripts/sync-review-bench.sh`
  refreshes it from `~/dsh` and runs `validate.mjs` (50 checks); CI fails
  when out of sync.
