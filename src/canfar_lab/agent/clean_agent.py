"""Clean agent setup state, stale locks, failed markers, and invalid configs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from canfar_lab.agent.setup_state import (
    failed_path,
    lock_path,
    log_path,
)


@dataclass(frozen=True)
class CleanResult:
    target: str
    status: str  # removed, skipped, repaired
    detail: str = ""


def clean_agent_state(
    *,
    home: Path | None = None,
    stale_locks: bool = True,
    failed_marker: bool = True,
    empty_configs: bool = True,
    logs: bool = False,
    dry_run: bool = False,
) -> list[CleanResult]:
    """Clean stale agent setup state, lock files, and broken config files."""
    home = home or Path.home()
    results: list[CleanResult] = []

    # 1. Clean stale locks
    lpath = lock_path(home)
    if lpath.is_file() and stale_locks:
        if dry_run:
            results.append(CleanResult("lock", "would_remove", str(lpath)))
        else:
            try:
                lpath.unlink(missing_ok=True)
                results.append(CleanResult("lock", "removed", str(lpath)))
            except OSError as exc:
                results.append(CleanResult("lock", "error", str(exc)))

    # 2. Clean failed markers
    fpath = failed_path(home)
    if fpath.is_file() and failed_marker:
        if dry_run:
            results.append(CleanResult("failed_marker", "would_remove", str(fpath)))
        else:
            try:
                fpath.unlink(missing_ok=True)
                results.append(CleanResult("failed_marker", "removed", str(fpath)))
            except OSError as exc:
                results.append(CleanResult("failed_marker", "error", str(exc)))

    # 3. Clean logs if requested
    lgpath = log_path(home)
    if lgpath.is_file() and logs:
        if dry_run:
            results.append(CleanResult("log", "would_remove", str(lgpath)))
        else:
            try:
                lgpath.unlink(missing_ok=True)
                results.append(CleanResult("log", "removed", str(lgpath)))
            except OSError as exc:
                results.append(CleanResult("log", "error", str(exc)))

    # 4. Clean empty/corrupted configs
    config_paths = [
        home / ".cursor" / "mcp.json",
        home / ".config" / "opencode" / "opencode.json",
        home / ".config" / "kilo" / "kilo.jsonc",
        home / ".claude.json",
        home / ".codex" / "config.toml",
    ]
    if empty_configs:
        for cfg in config_paths:
            if cfg.is_file():
                content = cfg.read_text(encoding="utf-8", errors="replace").strip()
                if not content or content == "{}" or content == "[]":
                    if dry_run:
                        results.append(
                            CleanResult(cfg.name, "would_remove", f"Empty config at {cfg}")
                        )
                    else:
                        try:
                            cfg.unlink()
                            results.append(
                                CleanResult(cfg.name, "removed", f"Removed empty config at {cfg}")
                            )
                        except OSError as exc:
                            results.append(CleanResult(cfg.name, "error", str(exc)))

    return results
