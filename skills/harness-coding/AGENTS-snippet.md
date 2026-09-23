# Coding harness (always on)

Use a **coding harness** for implementation: plan → execute → verify → improve. Repo state lives in `.cursor/harness/` (playbook + config + trajectories).

## Verify tiers (read `.cursor/harness/config.json`)

| Tier | Key | When |
|------|-----|------|
| Fast | `verify_fast` | Small edit done (`preflight-push`) |
| Pre-push | `verify` | Before push / PR fix (`ci-local` or `scripts/ci_test_only.sh`) |
| Full | `verify_full` | Human opt-in only — never auto-run |

Pixi repos: `pixi run preflight-push`, `pixi run ci-local`. UV repos: `./scripts/preflight_push.sh`, `./scripts/ci_test_only.sh`.

Never auto-run `torchregress-harness` or full benchmark suites in the agent loop.

## Skills

- `harness-coding` — default implementation loop
- `harness-reflect` — update playbook from trajectories (manual)
- `harness-improve` — bounded harness edits (manual)

Bootstrap a repo: `bash ~/.cursor/skills/harness-coding/scripts/init-harness.sh`
