"""Live session resource snapshot (CPU / RAM / GPU / scratch)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from canfar_lab.core.disk_usage import disk_usage
from canfar_lab.core.paths import resolve_paths


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_pct: float | None
    load_1m: float | None
    mem_used_bytes: int | None
    mem_total_bytes: int | None
    mem_pct: float | None
    scratch: dict[str, Any] | None
    home: dict[str, Any] | None
    gpu: list[dict[str, Any]]
    cgroup_mem_pct: float | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


def _meminfo() -> tuple[int | None, int | None]:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None, None
    total = avail = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                avail = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        return None, None
    if total is None:
        return None, None
    used = total - avail if avail is not None else None
    return used, total


def _loadavg() -> float | None:
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return None


def _cpu_pct_from_load(load: float | None) -> float | None:
    if load is None:
        return None
    cpus = os.cpu_count() or 1
    return round(min(100.0, (load / cpus) * 100.0), 1)


def _cgroup_mem_pct() -> float | None:
    """Kubernetes/cgroup v2 memory pressure when present."""
    for current_p, max_p in (
        (Path("/sys/fs/cgroup/memory.current"), Path("/sys/fs/cgroup/memory.max")),
        (
            Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
            Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        ),
    ):
        if not (current_p.is_file() and max_p.is_file()):
            continue
        try:
            cur = int(current_p.read_text().strip())
            raw_max = max_p.read_text().strip()
            if raw_max in ("max", ""):
                return None
            lim = int(raw_max)
            if lim <= 0 or lim >= (1 << 62):
                return None
            return round((cur / lim) * 100.0, 1)
        except (OSError, ValueError):
            continue
    return None


def _gpu_stats() -> list[dict[str, Any]]:
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in out.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            rows.append(
                {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "util_pct": float(parts[2]),
                    "mem_used_mib": float(parts[3]),
                    "mem_total_mib": float(parts[4]),
                }
            )
        except ValueError:
            continue
    return rows


def collect_resources() -> ResourceSnapshot:
    paths = resolve_paths()
    mem_used, mem_total = _meminfo()
    mem_pct = None
    if mem_used is not None and mem_total:
        mem_pct = round((mem_used / mem_total) * 100.0, 1)
    load = _loadavg()
    notes: list[str] = []
    scratch_info = None
    if paths.scratch_dir is not None:
        du = disk_usage(paths.scratch_dir)
        if du is not None:
            scratch_info = du.to_dict()
            if du.source == "statvfs":
                notes.append("scratch usage from filesystem (session-private volume)")
    home_du = disk_usage(paths.home)
    home_info = home_du.to_dict() if home_du else None
    if home_du and home_du.source == "ceph-xattr":
        notes.append(
            "home quota from Ceph xattrs (ceph.dir.rbytes can lag a few seconds after writes)"
        )
    elif home_du and home_du.source == "statvfs":
        notes.append("home usage from statvfs/df — may not match Ceph directory quota on /arc")
    return ResourceSnapshot(
        cpu_pct=_cpu_pct_from_load(load),
        load_1m=load,
        mem_used_bytes=mem_used,
        mem_total_bytes=mem_total,
        mem_pct=mem_pct,
        scratch=scratch_info,
        home=home_info,
        gpu=_gpu_stats(),
        cgroup_mem_pct=_cgroup_mem_pct(),
        notes=tuple(notes),
    )
