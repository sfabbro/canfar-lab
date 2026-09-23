# Jules PR batch triage — reference

## Listing every open PR (avoid the default cap)

- **`gh pr list` without `-L` / `--limit` only returns 30 PRs.** Always set `--limit` ≥ your open-PR count (e.g. `--limit 100000`) or use Option B.
- **Author-filtered lists** are also capped by the same default if you forget `-L`.

### Full list via `gh pr list`

```bash
gh pr list --state open --limit 100000 \
  --json number,title,author,headRefName,baseRefName,createdAt,labels,url,isDraft
```

### Full list via REST pagination (no limit parameter)

```bash
repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api --paginate "repos/${repo}/pulls?state=open&per_page=100" | jq -s 'add'
```

## Discover Jules bot login

Use a **high limit** so every author appears (not the default 30):

```bash
gh pr list --state open --limit 100000 --json number,author \
  --jq '.[] | "\(.number)\t\(.author.login)"' | sort -u
```

## File overlap between two PRs

```bash
comm -12 <(gh pr diff 12 --name-only | sort) <(gh pr diff 15 --name-only | sort)
```

## Cluster all open PRs by touched paths

```bash
for N in $(gh pr list --state open --limit 100000 --json number -q '.[].number'); do
  echo "#$N"
  gh pr diff "$N" --name-only | sort
  echo "---"
done
```

## CI failure harvest

```bash
gh run list --limit 50 --json databaseId,conclusion,headBranch,workflowName,url \
  --jq '.[] | select(.conclusion == "failure") | [.databaseId, .headBranch, .workflowName] | @tsv'
gh run view <databaseId> --log-failed 2>&1 | tail -80
```

## Mergeability snapshot

```bash
gh pr view 12 --json mergeable,mergeStateStatus,baseRefName,headRefName
```

- `mergeable`: `CONFLICTING` → expect local merge/rebase.
- `UNKNOWN` → retry after a short wait or fetch.

## Evaluation report template

Copy and fill:

```markdown
## Agent PR triage — <repo> — <date>

### Merge now (ordered)
1. #N — <one-line why>
2. ...

### Merge after fix / rebase
- #N — <blocker>

### Close / ignore
- #N — <reason>

### Groups (same files)
- Group A: #2, #7 — touch `src/foo/`

### Commands executed
- ...
```

## Policy knobs (ask user if unclear)

- Merge style: **merge commit** vs **squash** vs **rebase**.
- Target branch: always **default** vs **release/x**.
- Close bot PRs automatically vs leave open.

## Delete head branches after a merged batch

**Preferred:** merge with delete in one step:

```bash
gh pr merge N --squash --delete-branch   # or --merge / --rebase
```

**Cleanup any stragglers** (merged PR numbers in `MERGED_PRS`):

```bash
MERGED_PRS="12 15 18"
default="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)"
for n in $MERGED_PRS; do
  line="$(gh pr view "$n" --json state,headRefName,headRepository,headRepositoryOwner \
    --jq -r 'select(.state=="MERGED") | "\(.headRepositoryOwner.login)/\(.headRepository.name)\t\(.headRefName)"')"
  [ -z "$line" ] && continue
  repo_part="${line%%	*}"
  branch="${line#*	}"
  owner="${repo_part%%/*}"
  repo="${repo_part#*/}"
  [ "$branch" = "$default" ] && continue
  gh api -X DELETE "repos/${owner}/${repo}/git/refs/heads/${branch}" || true
done
```

Adjust the `default` skip if you use a different protection rule. Inspect failures (`|| true` avoids aborting the loop); remove `|| true` if you want a hard stop on errors.

**Local cleanup after remote deletes:**

```bash
git fetch origin --prune
git switch "$default"
```

Then remove local PR branches with `git branch -d <name>` (or `git branch -D` only if you are sure they are obsolete).

## CI parity (torchregress)

From repo root (matches `.github/workflows/ci.yml` test + benchmark jobs, plus lint):

```bash
./scripts/ci_local.sh
```

## Related Cursor skills

- **gh-fix-ci**: deep dive on failing GitHub Actions logs.
- **fix-merge-conflicts**: conflict resolution guardrails.
- **loop-on-ci**: watch runs until green.
