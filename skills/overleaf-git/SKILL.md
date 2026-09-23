---
name: overleaf-git
description: >-
  Sync and edit Overleaf projects via Git (pull, commit, push) and the Overleaf
  MCP. Use when working under ~/src/overleaf, fixing Overleaf sync, pushing
  LaTeX changes, or when the user mentions Overleaf git, project IDs, or olp_ tokens.
---

# Overleaf Git

Overleaf has no public write API. **Git is the integration.** Local clones live under `/Users/fabbros/src/overleaf/<name>/`.

## Credentials (do not commit)

| File | Purpose |
|------|---------|
| `~/.config/overleaf-mcp/git-token` | Account Git token (`olp_…`), mode 600 |
| `~/.config/overleaf-mcp/projects.json` | Multi-project IDs + tokens for MCP |
| `~/.config/overleaf-mcp/git-credentials` | `git credential-store` for `git.overleaf.com` |

Remote shape: `https://git@git.overleaf.com/<PROJECT_ID>`.

Never put `olp_` tokens in the repo, chat logs, or `mcp.json`. Point MCP at `OVERLEAF_PROJECTS_CONFIG`.

## Daily workflow (preferred: local clone)

```bash
cd /Users/fabbros/src/overleaf/<project>
git pull --rebase origin master   # or main — check: git branch -a
# edit .tex / .bib
latexmk -pdf -interaction=nonstopmode -file-line-error main.tex   # if appropriate
git add -p
git commit -m "Describe the paper change, not the tooling."
git push origin HEAD
```

Conflict with Overleaf web edits: pull first; resolve `.tex` conflicts carefully (keep both intended sentences); rebuild; push.

## MCP

Cursor MCP server `overleaf` uses `@mjyoo2/overleaf-mcp` with:

```bash
export OVERLEAF_PROJECTS_CONFIG="$HOME/.config/overleaf-mcp/projects.json"
```

Tools (names may vary): list/read/write files, section extract, sync. Prefer **local git** for multi-file refactors already checked out; use MCP when the agent is not in the clone or needs section-level Overleaf ops.

Project keys in `projects.json`: `astrosure`, `cfhtiq`, `changpaper`, `cure`, `msa`.

## New project

1. Overleaf → Menu → Git → copy project ID from URL / git URL.
2. `git clone https://git@git.overleaf.com/<PROJECT_ID> /Users/fabbros/src/overleaf/<name>`
3. Add entry to `~/.config/overleaf-mcp/projects.json` (same account token).
4. Confirm: `git -C … pull` and `git push` dry-run.

## Failure modes

| Error | Fix |
|-------|-----|
| `403` / auth fail | Regenerate token in Overleaf Account → Git integration; update `git-token` + `projects.json` + `git-credentials` |
| Non-fast-forward | `git pull --rebase`; resolve; push |
| Empty commit rejected | No changes; check Overleaf already has the edit |
| Plan without Git | Need premium/institution Git; cannot MCP-write |

## Safety

- Do not force-push to Overleaf unless the user explicitly asks.
- Do not rewrite history on shared paper branches.
- Treat the Git token like a password; rotate if it leaked into a tracked file.
