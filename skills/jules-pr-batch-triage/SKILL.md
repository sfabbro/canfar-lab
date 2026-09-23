---
name: jules-pr-batch-triage
description: >-
  Lists open GitHub PRs (often from bots such as Google Jules), reads and scores
  each change, groups them by overlap and risk, merges or integrates the
  worthwhile ones, resolves conflicts, runs local tests (e.g. torchregress
  ./scripts/ci_local.sh) and watches GitHub CI, then commits and pushes. Use
  when the user wants to batch-triage many agent PRs, clear a Jules backlog, or
  automate merge + verify for bot-opened PRs.
---

# Jules / agent PR batch triage

## When to use

- Many open PRs from coding agents (e.g. **Jules**, Copilot, Codex) on one repo.
- Goal: **read → evaluate → group → apply winners → fix conflicts → test → CI → push**.

## Prerequisites

1. **`gh` authenticated** with repo scope: `gh auth status` (fix with `gh auth login`).
2. **Default branch up to date**: `git fetch origin && git checkout <default> && git pull`.
3. Know the repo’s **test entrypoint** (e.g. `pixi run pytest`, `uv run pytest`, `npm test`) from `AGENTS.md`, `README`, or CI config.

## Phase 0 — Scope and safety

- Confirm **target repo**: `gh repo view --json nameWithOwner -q .nameWithOwner`.
- Prefer a **dry run**: list and classify PRs before any merge or destructive git operations.
- If the user must approve each merge, **stop after the evaluation report** and wait for explicit PR numbers or a merge list.
- **Cross-repo:** when the user has PRs in many repositories, start from `gh search prs --author <login> --state open -L 500` so nothing is missed.
- **Upstream / fork:** if the user wants **no** changes on upstream (work stays on a fork only), **do not** close or merge upstream PRs unless they explicitly ask — skip that repo in apply phases.

### Phase 0b — Branch deletion is **after** merge (non-negotiable)

The intended order is always: **discover → evaluate → merge (or reject with reason) → test → push → then delete remote heads**. **Do not skip to branch deletion.**

- **Allowed without extra proof:** delete remote tracking branches that are **`--merged`** into the default branch (their commits are already on `main`).
- **Forbidden unless the user explicitly waives merge** for each PR/branch: bulk `git push origin --delete` on refs that are **`--no-merged`** into `default`. That drops unique commits and often leaves GitHub PRs **closed without merge** (`mergedAt: null`).
- **Before deleting any head** tied to a PR, verify at least one of:
  - `gh pr view N --json mergedAt` is non-null (**MERGED**), or
  - After `git fetch origin pull/N/head:recover/pr-N`, `git merge-base --is-ancestor recover/pr-N origin/<default>` is true (work already landed another way).
- **Recovery** when the remote branch is gone but the PR still exists: `git fetch origin pull/<N>/head:recover/pr-<N>` (GitHub keeps `refs/pull/N/head` for many closed PRs). Then merge or cherry-pick onto `default`, test, push, and **close/update the PR** with a pointer to the integrating commit.

## Phase 1 — Discover open PRs and remote branches

**`gh pr list` defaults to `--limit 30` (alias `-L 30`).** Omitting the limit silently hides most open PRs. Always pass an explicit limit or use the paginated API below.

After `git fetch origin --prune`, list **all** remote heads (not only PR-linked ones):

```bash
git fetch origin --prune
git branch -r | rg -v 'origin/HEAD|origin/main'
```

Stale agent branches often exist without an open PR (closed PRs whose heads were not deleted). Cross-check each remote head against open PRs and `git merge-base --is-ancestor <branch> origin/main` before deletion.

### Option A — `gh pr list` with a high limit

Set `--limit` to at least the number of open PRs (safe ceiling: `100000`). `gh` requests additional API pages until the limit is reached or PRs are exhausted.

```bash
gh pr list --state open --limit 100000 \
  --json number,title,author,headRefName,baseRefName,createdAt,labels,url,isDraft \
  --jq '.[] | {number, title, login: .author.login, head: .headRefName, base: .baseRefName, draft: .isDraft, url}'
```

Optional **author filter** still applies the same limit to matching PRs only:

```bash
gh pr list --state open --author "<bot-login>" --limit 100000 --json number,title,url
```

### Option B — Guaranteed full list (`gh api` + `--paginate`)

Use when you want every open PR regardless of count (no artificial ceiling on the `pr list` path). REST field names differ slightly from `gh pr list --json`.

```bash
repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api --paginate "repos/${repo}/pulls?state=open&per_page=100" \
  | jq -s 'add | .[] | {number, title, login: .user.login, head: .head.ref, base: .base.ref, draft: .draft, url: .html_url}'
```

If `jq` is unavailable, save the raw `gh api --paginate ...` output and parse in Python; each page is a JSON array.

**Sanity check:** compare the line or record count to the open-PR count shown in the GitHub UI for the repo.

**Jules / bot heuristics** (use what matches the repo):

- Filter by author: e.g. `--author app/jules` or the org’s Jules app user (discover via one `gh pr view <n> --json author`).
- Or filter in `jq` on `.author.login` or label e.g. `jules`, `automated`.
- Skip **draft** PRs unless the user wants them.

## Phase 1b — Gather CI failures (before merging)

Do not assume green CI on `main` or on agent PRs. Collect failures **before** integration so you fix infra blockers in the same push as code merges.

```bash
# Recent runs (failures first)
gh run list --limit 50 --json databaseId,status,conclusion,headBranch,event,workflowName,createdAt,url \
  --jq '.[] | select(.conclusion == "failure") | {branch: .headBranch, workflow: .workflowName, url}'

# Main branch health
gh run list --branch main --limit 10 --json conclusion,status,url,createdAt

# Per-PR checks (when PRs are open)
for N in <pr-numbers>; do echo "=== PR #$N ==="; gh pr checks $N 2>/dev/null || true; done
```

**Inspect failed logs** (replace `<id>` with `databaseId`):

```bash
gh run view <id> --log-failed 2>&1 | tail -100
```

### torchz CI failure patterns

| Symptom | Likely cause | Fix on integration branch |
|---------|--------------|---------------------------|
| `torchsky` CMake: `CUDA::nvrtc` / `libnvrtc` | GitHub runner lacks CUDA toolkit for native extension build | Use `Jimver/cuda-toolkit@v0.2.35` with `cuda: "12.4.1"` on `ubuntu-22.04`; set `CUDA_HOME: ${{ steps.cuda-toolkit.outputs.CUDA_PATH }}` on `pixi install`. **Do not** use apt `nvidia-cuda-toolkit` alone — Ubuntu ships CUDA 12.0, but PyTorch requires ≥12.1. |
| `torchregress` / private git dep resolution | Missing `PAT_FOR_PRIVATE_REPOS` or stale lockfile | Ensure workflow `git config url.insteadOf` step; do not hand-edit `pixi.lock` for unrelated PRs |
| `test_discover_dataset_configs` / empty `data/` dict | `data/` is gitignored; CI has no benchmark YAMLs | Skip in test when `data/` missing; do not stage data for CI |
| All PR branches red, same log | **Infra**, not PR code | Land CI fix on `main` first, then close agent PRs whose *only* delta is the same CI hack |

If **main** and **all open PRs** fail with the same infra error, prioritize a single CI fix commit; agent PRs that only duplicate that fix should be **closed as superseded**, not merged individually.

## Phase 2 — Read each PR

For each candidate number `N`:

```bash
gh pr view N --json title,body,author,files,commits,mergeable,mergeStateStatus
gh pr diff N
# Optional: files only for grouping
gh pr diff N --name-only
```

Capture: **intent**, **surface area** (files), **mergeability**, and whether it **touches risky zones** (migrations, security, public API, lockfiles).

## Phase 3 — Evaluate (scoring rubric)

Assign each PR a short verdict. Use this **default rubric**; tighten for production repos.

| Signal | Action |
|--------|--------|
| Clear purpose, small diff, tests/docs aligned | **Merge candidate** |
| Duplicate or superseded by another open PR | **Close or defer**; link the winner |
| Breaks API without migration, or huge unrelated refactor | **Reject** or request split |
| Generated noise (format-only churn, accidental secrets) | **Reject** |
| **Trivial lint only** (unused imports, one-off formatting) that pre-commit/ruff should catch | **Reject**; run **one** repo-wide `ruff check --fix` / format pass (or ask maintainer to) instead of merging N agent PRs |
| Micro-perf without benchmarks where AGENTS requires evidence | **Reject** or **defer** until benchmark note exists |
| **torchz scanner noise** (MD5 integrity, `random` augmentation, per-file test stubs, `iter_rows` in ETL, sync CLI I/O, "function too long") | **Reject** — see **AGENTS.md §7** |
| Touches same files as another candidate | **Group** (merge order matters) |

### Grouping duplicate agent PRs (common Jules pattern)

Cluster open PRs by **file overlap** and **theme** (e.g. four Palette PRs all touching `photoz_browser.py` empty states):

1. `gh pr diff N --name-only` for each open PR; cluster with `comm -12` (see [reference.md](reference.md)).
2. Pick **one winner** per cluster: prefer the PR with **tests**, the **smallest diff**, or the **most actionable** UX copy.
3. **Cherry-pick behavior onto `main` locally** (Strategy B) rather than merging five near-duplicate PRs on GitHub.
4. Close losers with: `Integrated on main in <sha>. Superseded by grouped batch (PRs #A, #B, …).`
5. Apply **hint-text / copy** improvements from a second PR in the same cluster when they do not conflict (merge copy from the best-written branch).

**torchz Palette empty-state cluster:** `build_nz_figure` empty state + `tests/test_photoz_browser_reporting.py` from one PR; actionable annotation strings from another; close #148–#151 together after one integration commit.

**torchz Bolt perf cluster:** prefer vectorized `multinomial` / `bincount` paths in `nz/` over per-row Python loops; one integration commit per module (`sompz_style.py`, `diagnostics.py`, …).

Produce a **one-page summary** for the user:

- **Merge now** (ordered list of PR numbers)
- **Merge after rebase / conflict pass**
- **Close or ignore** (reason each)

## Phase 4 — Group before applying

- **Dependency**: if PR B depends on A, order **A then B** (or merge A first).
- **File overlap**: use `gh pr diff N --name-only` to cluster PRs touching the same paths; merge **smallest / foundational** PRs first to reduce conflict surface.
- **Base branch**: ensure every PR targets the same default branch; if not, note **retarget** or **cherry-pick** separately.

## Phase 5 — Apply worthwhile PRs

Pick **one** primary strategy (do not mix blindly).

**Batch lint / hygiene (preferred over many PRs):** when several open PRs only remove unused imports or reformat, **do not merge them one by one**. Instead, on a clean default branch run the repo’s documented `ruff` / `black` (or `pre-commit run --all-files`), verify tests, and land **one** commit or PR. **Close** the trivial agent PRs as superseded with a short comment.

**Close without merge:** when policy says not to land work on upstream (e.g. fork-only workflow), skip merge strategies for that target; leave PRs open or let the user handle them — do not assume they must be closed.

### Strategy A — Merge on GitHub (cleanest when checks are trusted)

For each approved `N` in order, **delete the PR head branch on merge** (same-repo PRs) using `--delete-branch`:

```bash
gh pr merge N --merge --delete-branch   # or --squash / --rebase per team policy
```

If `gh` refuses (branch protection, fork PR, or permissions), note it and delete manually in Phase 10 after the PR shows **merged**.

If **merge conflicts**: checkout the PR branch locally, merge/rebase default branch, resolve, push, then merge:

```bash
gh pr checkout N
git fetch origin
git merge origin/$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
# resolve conflicts → test → commit → push
```

### Strategy B — Integration branch locally (one push, one CI run)

```bash
git checkout origin/<default>
git checkout -b integrate/jules-batch-<date>
for N in <ordered list>; do
  git fetch origin pull/$N/head:pr-$N
  git merge pr-$N -m "Merge PR #$N"
done
# resolve conflicts between PRs → run tests → push → open PR or fast-forward default per policy
```

## Phase 6 — Resolve merge conflicts

Follow project **fix-merge-conflicts** discipline:

1. `git status` and conflict markers; resolve **minimally**.
2. **Regenerate lockfiles** with the package manager; do not hand-edit unless unavoidable.
3. Run **lint/tests** before staging.

## Phase 7 — Local verification (mandatory before push)

**Goal:** stop burning GitHub Actions on **syntax**, **stale imports** (**F401**), **undefined names** (**F821**), and **format drift**. **Do not `git push`** until local gates pass.

1. Read **`AGENTS.md`** for the repo and run its **Mandatory pre-push gate** section in full (blocking for agents).
2. **Cheap baseline** every Python repo should run if `AGENTS.md` is silent (adapt paths):
   - `python -m compileall -q <package_dirs> tests`
   - `ruff check` on the **same paths CI uses** (read `.github/workflows/*` when unsure)
   - `ruff format --check` or `black --check` **only when CI enforces them** (otherwise you add noise and failed pushes)
   - `pytest` — narrow paths only for tiny edits; widen when unsure
3. **Repo shortcuts** (use when defined — they bundle the above):
   - **torchsky / zscrape / cfhtcast:** `pixi run preflight-push` then tests (`pixi run pytest`, `pixi run test`, etc.).
   - **torchregress:** `./scripts/ci_local.sh` for full Actions parity; see `AGENTS.md` for a **minimal** fast path when appropriate.

Install **pre-commit + pre-push** when the repo documents it (`uvx pre-commit install --hook-type pre-push`) so `git push` cannot skip parity checks by accident.

**Batching:** one green **integration branch** + **one push** beats N pushes that each trigger CI.

## Phase 8 — CI

After push:

```bash
gh pr checks   # if on a PR branch
gh run list --branch "$(git branch --show-current)" --limit 5
gh run watch --exit-status
```

On failure: `gh run view <id> --log-failed`, fix, commit, push, repeat. Treat **non-GitHub** checks as out of scope (report URL only).

## Phase 9 — Commit and push

- **One logical commit per conflict-resolution or post-merge fix** with a message like `fix: resolve conflicts after merging Jules PRs #12 #15`.
- Push: `git push -u origin HEAD`.
- If policy requires **signed commits** or **PR-only** workflow, follow that instead of pushing directly to default.

## Phase 10 — Delete merged head branches

After merges are **complete** and default (or target) branch is updated on the remote, **remove the head branches** for PRs you merged so the repo does not keep dozens of stale agent branches.

**Do not use this phase to “clean” `--no-merged` branches** without a prior merge or an explicit written discard decision per PR (see Phase 0b).

### Remote branches (required for this workflow)

1. **If you used `gh pr merge --delete-branch`:** GitHub removes the head branch when the merge succeeds (same-repo heads). Verify leftovers with `git fetch origin --prune` and `git branch -r`.
2. **If branches remain** (merged without `--delete-branch`, admin merge, or integration flow): for each merged PR `N`, read `state`, `headRefName`, `headRepository`, and `headRepositoryOwner` via `gh pr view N --json state,headRefName,headRepository,headRepositoryOwner`. When `state` is `MERGED`, delete `refs/heads/<headRefName>` on the head repo with:

`gh api -X DELETE "repos/<owner>/<repo>/git/refs/heads/<branch>"`

Skip when `<branch>` is the **default** branch or matches a **protected** pattern. **Fork PRs:** `<owner>/<repo>` is the **fork** (confirm before deleting). For a full loop over many PR numbers, use [reference.md](reference.md).

3. **Batch sanity check:** list remote branches matching your agent prefix (if any) and confirm each PR is merged before deleting:

```bash
git fetch origin --prune
git branch -r | rg 'origin/(jules|agent|dependabot)'   # adjust pattern; verify each is fully merged
```

### Local clones (optional cleanup)

- Drop stale remote-tracking refs: `git fetch origin --prune`.
- Remove local branches created for PR work (e.g. `gh pr checkout`): `git branch -d <branch>` after merge, or prune locals that track deleted remotes (see [reference.md](reference.md)).

### Strategy B note

If you land one integration PR and **close** the original Jules PRs without merging them in GitHub’s sense, those PR head branches may still exist on `origin` until you delete them explicitly (same `gh api DELETE` / `git push origin --delete` as above), using the **head branch names** you recorded before closing.

## Guardrails

- Never **force-push** shared branches without explicit user approval.
- Never merge PRs that add **secrets** or disable security checks without explicit approval.
- Do not use `--no-verify` to bypass hooks unless the user explicitly allows it.
- If **more than ~5** PRs overlap heavily, stop and propose **serial merge** or **split batches** after the first integration PR is green.
- **Branch deletion:** never delete the **default** branch, **release** branches, or anything under branch protection; if `gh` or the API refuses, report and skip rather than forcing.
- **Never bulk-delete `--no-merged` remote branches** as a hygiene shortcut; that is not equivalent to merging PRs and violates the workflow above.

## Output checklist

Report back with:

1. **Inventory:** open PR count, remote branch count, CI failure summary (main + PR branches).
2. PRs **merged** or **integrated** (numbers + URLs + integrating commit SHA).
3. PRs **skipped** (reason).
4. **Conflicts** resolved (files touched).
5. **Tests / CI** result (local + post-push `gh run watch` when applicable).
6. Branch names and **push** confirmation.
7. **Branches deleted** (remote + local), or **skipped** with reason (protected, fork, permission).

## Additional detail

For longer examples and a copy-paste batch template, see [reference.md](reference.md).
