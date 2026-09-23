from __future__ import annotations

from pathlib import Path

import pytest

from canfar_lab.core.disk_usage import DiskUsage, disk_usage, quota_used_pct, used_pct
from canfar_lab.core.session_resources import collect_resources


def test_quota_used_pct_statvfs(tmp_path: Path) -> None:
    pct = quota_used_pct(tmp_path)
    assert pct is not None
    assert 0 <= pct <= 100


def test_disk_usage_missing() -> None:
    assert disk_usage(Path("/no/such/path-astroai")) is None


def test_disk_usage_prefers_ceph_xattrs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()

    def fake_getxattr(path: str | bytes, name: str | bytes) -> bytes:
        key = name.decode() if isinstance(name, bytes) else name
        if key == "ceph.quota.max_bytes":
            return b"1000"
        if key == "ceph.dir.rbytes":
            return b"250"
        raise OSError("missing")

    # macOS has no os.getxattr — raise=False installs the attribute for the test.
    monkeypatch.setattr("os.getxattr", fake_getxattr, raising=False)
    info = disk_usage(home)
    assert info is not None
    assert info.source == "ceph-xattr"
    assert info.pct == 25
    assert info.used_bytes == 250
    assert info.total_bytes == 1000


def test_collect_resources_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SCRATCH", str(scratch))
    snap = collect_resources()
    data = snap.to_dict()
    assert "mem_pct" in data
    assert "cpu_pct" in data
    assert "gpu" in data
    assert isinstance(data["gpu"], list)
    assert data["home"] is not None
    assert data["home"]["source"] in ("statvfs", "ceph-xattr")


def test_disk_usage_to_dict() -> None:
    d = DiskUsage("/x", 1, 2, 1, 50, "statvfs").to_dict()
    assert d["pct"] == 50


def test_used_pct_rounds_half_up() -> None:
    assert used_pct(0, 1000) == 0
    assert used_pct(250, 1000) == 25
    assert used_pct(931, 1000) == 93
    assert used_pct(937, 1000) == 94
    assert used_pct(1000, 1000) == 100
    assert used_pct(1, 0) == 0


def test_ceph_usage_does_not_inherit_arc_parent_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    from canfar_lab.core.disk_usage import _ceph_dir_usage

    def fake_getxattr(path: str | bytes, name: str | bytes) -> bytes:
        key = name.decode() if isinstance(name, bytes) else name
        p = str(path)
        if p.rstrip("/") == "/arc/home" and key == "ceph.quota.max_bytes":
            return b"999999"
        if p.rstrip("/") == "/arc/home" and key == "ceph.dir.rbytes":
            return b"900000"
        raise OSError("missing")

    monkeypatch.setattr("os.getxattr", fake_getxattr, raising=False)
    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    info = _ceph_dir_usage(Path("/arc/home/alice"))
    assert info is None


def test_disk_usage_skips_statvfs_on_arc_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("canfar_lab.core.disk_usage._arc_home_tree", lambda _p: True)
    assert disk_usage(home) is None
