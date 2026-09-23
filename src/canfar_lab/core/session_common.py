from __future__ import annotations

import os
import pwd
import shutil
from pathlib import Path

PLATFORM_SRC = Path("/srcdir")
SCRATCH_WORK_NAME = "src"


def user_tag() -> str:
    """Match shell ``${USER:-$(id -un)}`` for cache/runtime directory names."""
    for key in ("USER", "LOGNAME"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        return str(os.getuid())


def _dev(path: Path) -> int | None:
    try:
        return path.stat().st_dev
    except OSError:
        return None


def overlay_work_dir(
    hinted: Path | None,
    scratch: Path | None,
    *,
    srcdir: Path = PLATFORM_SRC,
    root: Path = Path("/"),
) -> Path | None:
    """Return ``scratch/src`` when ``/srcdir`` would be wiped on container restart.

    CANFAR OOM-kills recreate the container overlay (``/srcdir``) but remount
    ``/scratch``. Bind-mounted ``/srcdir`` (tests, some session types) and an
    explicit ``SRCDIR``/``WORK`` other than ``/srcdir`` are left alone. Disable with
    ``CANFAR_LAB_WORK_ON_SCRATCH=0``.
    """
    flag = os.environ.get("CANFAR_LAB_WORK_ON_SCRATCH", "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return None
    if scratch is None or not scratch.is_dir() or not os.access(scratch, os.W_OK):
        return None
    scratch_dev = _dev(scratch)
    root_dev = _dev(root)
    if scratch_dev is None or root_dev is None or scratch_dev == root_dev:
        return None
    if hinted is not None and hinted != srcdir:
        return None
    src_dev = _dev(srcdir) if srcdir.is_dir() else root_dev
    if src_dev != root_dev:
        return None
    work = scratch / SCRATCH_WORK_NAME
    work.mkdir(parents=True, exist_ok=True)
    if srcdir.is_dir():
        _seed_work_from_srcdir(srcdir, work)
    return work


def _seed_work_from_srcdir(srcdir: Path, work: Path) -> None:
    """Copy overlay ``/srcdir`` into ``scratch/src`` once, before an OOM wipe."""
    try:
        if srcdir.resolve() == work.resolve():
            return
        if any(work.iterdir()):
            return
        entries = list(srcdir.iterdir())
        if not entries:
            return
    except OSError:
        return
    for src in entries:
        dest = work / src.name
        if dest.exists():
            continue
        try:
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest, follow_symlinks=False)
        except OSError:
            continue


def ensure_writable_dir(path: Path) -> bool:
    """mkdir -p ``path`` and return whether it is writable. Never raises."""
    try:
        path = path.expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return bool(os.access(path, os.W_OK))
    except OSError:
        return False


def scratch_cache_root(work: Path, scratch: Path | None) -> Path:
    user = user_tag()
    if scratch is not None:
        return scratch / f".cache-{user}"
    return work / f".cache-{user}"


def find_arc_project_root(start: Path | None = None) -> Path | None:
    """Team project dir: `PROJECT` env var wins, else walk up to /arc/projects."""
    project = os.environ.get("PROJECT", "").strip()
    if project:
        path = Path(project).expanduser()
        if path.is_dir():
            return path
    path = (start or Path.cwd()).resolve()
    if not Path("/arc/projects").is_dir():
        return None
    while path != path.parent:
        if path.parent == Path("/arc/projects"):
            return path
        path = path.parent
    return None
