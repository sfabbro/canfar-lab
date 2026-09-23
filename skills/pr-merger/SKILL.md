---
name: pr-merger
description: >-
  Sync a repo with GitHub, evaluate open PRs/branches, merge winners, resolve
  conflicts, run local gates and CI, then clean up. Use for batch merge workflows
  on sfabbro repos (torchregress, torchsky, etc.).
disable-model-invocation: true
---

# PR / branch merger

Automates syncing a local Git repo with GitHub: evaluate PRs, merge into main, resolve conflicts, test, verify CI, cleanup.

## Prerequisites

- `git` and `gh` installed; `gh auth login` done
- Push permissions on the target repo

## Configuration

```bash
REPO_OWNER=<github-owner>
REPO_NAME=<github-repo>
MAIN_BRANCH=main
WORKDIR=/path/to/local/repo
```

## Workflow

### Phase 0: Cross-repo discovery

```bash
gh search prs --author <github-login> --state open -L 500 \
  --json repository,number,title,url,isDraft \
  --jq '.[] | "\(.repository.nameWithOwner) #\(.number): \(.title)"'
```

Dedupe overlapping PRs with `gh pr diff <n> --name-only`. Reject trivial lint-only or duplicate micro-PRs.

### Mandatory pre-push gate

Before any `git push`, run the repo **AGENTS.md** pre-push gate (`compileall`, `ruff`, format check if CI enforces it, tests). Do not push to discover CI failures locally catchable.

### Phase 1–5

1. Sync main: `git fetch origin && git checkout $MAIN_BRANCH && git pull`
2. List PRs: `gh pr list --state open --limit 100`
3. Evaluate each PR (title, diff, CI, mergeability, AGENTS.md policy)
4. Per PR: checkout → rebase → local gates → push → `gh pr merge`
5. Cleanup merged branches; verify `gh pr checks`

For Jules/agent batch triage, prefer **jules-pr-batch-triage** when many bot PRs are open.

## Common verifiers (sfabbro repos)

| Repo | Local gate |
|------|------------|
| torchsky, torchfits | `pixi run ci-local` |
| torchregress | `./scripts/ci_local.sh` |
| zscrape | `pixi run pytest` |

## Error handling

| Issue | Action |
|-------|--------|
| Merge conflict | Resolve, `git add`, `git rebase --continue` |
| Tests fail | Fix, commit, push, re-run |
| CI fails | Use **gh-fix-ci** skill |
