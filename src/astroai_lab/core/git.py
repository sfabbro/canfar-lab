from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path

from astroai_lab.errors import LabError
from astroai_lab.utils.subprocess import run_capture


@dataclass
class GitStatus:
    in_repo: bool
    branch: str | None
    remote: str | None
    uncommitted: bool
    ahead: int = 0


def git_status(cwd: Path | None = None) -> GitStatus:
    root = cwd or Path.cwd()
    try:
        run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)
    except LabError:
        return GitStatus(in_repo=False, branch=None, remote=None, uncommitted=False)

    branch = run_capture(["git", "branch", "--show-current"], cwd=root) or None
    try:
        remote = run_capture(["git", "remote", "get-url", "origin"], cwd=root)
    except LabError:
        remote = None

    uncommitted = False
    try:
        run_capture(["git", "rev-parse", "--verify", "HEAD"], cwd=root)
        run_capture(["git", "diff-index", "--quiet", "HEAD", "--"], cwd=root)
    except LabError:
        uncommitted = True

    return GitStatus(
        in_repo=True,
        branch=branch,
        remote=remote,
        uncommitted=uncommitted,
    )


def git_head_sha(cwd: Path, *, short: bool = True) -> str:
    """Return HEAD SHA (short by default). Empty string if unavailable."""
    args = ["git", "rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    try:
        return run_capture(args, cwd=cwd).strip()
    except LabError:
        return ""


def _looks_like_sha(value: str) -> bool:
    if len(value) < 7 or len(value) > 40:
        return False
    return all(c in "0123456789abcdef" for c in value.lower())


def git_default_branch(cwd: Path) -> str:
    """Resolve origin's default branch, falling back to main then master."""
    try:
        ref = run_capture(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=cwd,
        ).strip()
        if ref.startswith("refs/remotes/origin/"):
            return ref.removeprefix("refs/remotes/origin/")
    except LabError:
        pass
    for name in ("main", "master"):
        try:
            run_capture(["git", "rev-parse", "--verify", f"origin/{name}"], cwd=cwd)
            return name
        except LabError:
            continue
    return "main"


def git_sync_from_origin(
    cwd: Path,
    *,
    ref: str | None = None,
    force: bool = False,
) -> str:
    """Fetch ``origin`` and fast-forward (or check out ``ref``). Return short HEAD SHA.

    ``ref`` may be a branch name or a commit SHA. Refuses a dirty tree unless
    ``force`` (then hard-reset to the target tip).
    """
    from astroai_lab.utils.subprocess import run

    status = git_status(cwd)
    if not status.in_repo:
        raise LabError(f"Not a git repo: {cwd}", hint="Remove it or pass a fresh --to path.")
    if status.uncommitted and not force:
        raise LabError(
            f"Dirty working tree: {cwd}",
            hint="Commit/stash, or pass --force to hard-reset to origin.",
        )
    run(["git", "fetch", "--prune", "origin"], cwd=cwd, quiet=True)

    if ref and _looks_like_sha(ref):
        cmd = ["git", "checkout", "--detach", ref]
        if force:
            cmd = ["git", "checkout", "-f", "--detach", ref]
        run(cmd, cwd=cwd, quiet=True)
        return git_head_sha(cwd)

    if ref:
        branch = ref.removeprefix("origin/")
        target = ref if ref.startswith("origin/") else f"origin/{ref}"
    else:
        branch = git_default_branch(cwd)
        target = f"origin/{branch}"

    run_capture(["git", "rev-parse", "--verify", target], cwd=cwd)
    if force:
        run(["git", "checkout", "-f", "-B", branch, target], cwd=cwd, quiet=True)
        run(["git", "reset", "--hard", target], cwd=cwd, quiet=True)
    else:
        run(["git", "checkout", branch], cwd=cwd, quiet=True)
        run(["git", "merge", "--ff-only", target], cwd=cwd, quiet=True)
    return git_head_sha(cwd)


def git_ensure_upstream(cwd: Path, parent: str) -> bool:
    """Point ``upstream`` at ``parent`` (owner/name). Return True if added/changed."""
    from astroai_lab.utils.subprocess import run

    url = f"https://github.com/{parent}.git"
    try:
        current = run_capture(["git", "remote", "get-url", "upstream"], cwd=cwd)
    except LabError:
        run(["git", "remote", "add", "upstream", url], cwd=cwd, quiet=True)
        return True
    if parent not in current.replace(":", "/"):
        run(["git", "remote", "set-url", "upstream", url], cwd=cwd, quiet=True)
        return True
    return False


def git_init_and_commit(target: Path, message: str = "Initial commit") -> None:
    from astroai_lab.utils.subprocess import run

    if not (target / ".git").exists():
        run(["git", "init", "-q"], cwd=target)
    run(["git", "add", "-A"], cwd=target)
    with contextlib.suppress(LabError):
        run(["git", "commit", "-m", message, "--quiet"], cwd=target)
