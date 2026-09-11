# AGENTS.md — canfar-lab

In-session AstroAI lab CLI (`astroai`) and related tooling. CANFAR is the
platform; AstroAI is the product surface inside the session.

## Remotes (AstroAI fork workflow)

| Remote | Points at | Use |
|--------|-----------|-----|
| `origin` | `sfabbro/canfar-lab` | Push `wip/*` only |
| `upstream` | `astroai/canfar-lab` | Sync `main`; PR target |

`main` tracks `upstream/main`. Never force-push `astroai` `main`.

```bash
git fetch upstream && git rebase upstream/main
git checkout -b wip/<topic>
git push -u origin HEAD
gh pr create -R astroai/canfar-lab --head sfabbro:$(git branch --show-current)
```

## Environment

Pixi (`[tool.pixi]` in `pyproject.toml`). Prefer `pixi run` over system Python.

```bash
pixi install
```

## Verification

```bash
canfar-lab doctor
# or the repo's documented pixi / pytest tasks — see README and
# `.cursor/harness/config.json`
```

## In-session project template

The AGENTS template copied into user projects lives under
`src/astroai_lab/data/agent/project/AGENTS.md`. Edit that file when changing
what lab users see after `astroai agent setup`, not only this root file.

Workspace layout and `/arc` rules (`PYTHONNOUSERSITE`, no `$HOME/.local`
installs): parent workspace `AGENTS.md` (`~/src/AGENTS.md`).
