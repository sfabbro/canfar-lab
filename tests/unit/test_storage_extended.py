from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from canfar_lab.core.storage import (
    ArcProjectInfo,
    QuotaLine,
    arc_project_statuses,
    collect_status_quotas,
    cwd_arc_project,
    df_line,
    dir_size,
    home_breakdown,
    top_cpu_processes,
)
from canfar_lab.errors import LabError


def test_df_line(tmp_path: Path) -> None:
    line = df_line(tmp_path, "test")
    assert isinstance(line, QuotaLine)
    assert line.label == "test"
    assert line.source == "statvfs"


def test_df_line_missing() -> None:
    assert df_line(Path("/no/such/dir"), "x") is None


def test_dir_size_file(tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_text("12345")
    assert dir_size(f) == 5
    assert dir_size(tmp_path / "missing") == 0


def test_dir_size_does_not_walk(tmp_path: Path, monkeypatch) -> None:
    d = tmp_path / "d"
    d.mkdir()
    (d / "a").write_text("hello")

    def _boom(self, *args, **kwargs):
        raise AssertionError("rglob must not be used on Ceph home trees")

    monkeypatch.setattr(Path, "rglob", _boom)
    assert dir_size(d) >= 5


def test_dir_size_prefers_ceph_rbytes(tmp_path: Path, monkeypatch) -> None:
    d = tmp_path / "d"
    d.mkdir()

    def fake_getxattr(path: str | bytes, name: str | bytes) -> bytes:
        key = name.decode() if isinstance(name, bytes) else name
        if key == "ceph.dir.rbytes":
            return b"999"
        raise OSError("missing")

    monkeypatch.setattr("os.getxattr", fake_getxattr, raising=False)
    with patch("canfar_lab.core.storage._du_bytes") as du:
        assert dir_size(d) == 999
        du.assert_not_called()


def test_dir_bytes_does_not_retry_du_after_timeout(tmp_path: Path) -> None:
    from canfar_lab.core.storage import dir_bytes

    d = tmp_path / "d"
    d.mkdir()
    calls: list[list[str]] = []

    def _du(cmd: list[str], **kwargs: object) -> str:
        calls.append(cmd)
        raise LabError("Command timed out after 2.0s: du -sb")

    with patch("canfar_lab.utils.subprocess.run_capture", side_effect=_du):
        assert dir_bytes(d, timeout_sec=2.0) is None
    assert calls == [["du", "-sb", str(d)]]


def test_home_breakdown(tmp_path: Path) -> None:
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "data").write_text("x" * 50)
    rows = home_breakdown(tmp_path)
    assert any(r[0] == ".cache" for r in rows)


def test_top_cpu_processes() -> None:
    with patch("canfar_lab.utils.subprocess.run_capture", return_value="USER PID\nproc1\nproc2"):
        procs = top_cpu_processes(limit=1)
    assert len(procs) == 1


def test_top_cpu_processes_on_error() -> None:
    with patch("canfar_lab.utils.subprocess.run_capture", side_effect=LabError("fail")):
        assert top_cpu_processes() == []


def test_arc_project_statuses_marks_cwd() -> None:
    foo = Path("/arc/projects/foo")
    bar = Path("/arc/projects/bar")
    q = QuotaLine(label="foo", path=str(foo), used="1G", total="10G", free="9G", pct=10)
    with (
        patch("canfar_lab.core.storage.find_arc_project_root", return_value=foo),
        patch("canfar_lab.core.storage.list_arc_projects", return_value=[bar, foo]),
        patch("canfar_lab.core.storage.df_line", return_value=q) as mock_df,
        patch("canfar_lab.core.storage.read_acl_groups", return_value=[]),
        patch("canfar_lab.core.storage.project_access", return_value="rw"),
        patch("canfar_lab.core.storage.list_gms_groups", return_value=None),
    ):
        active, rows, gms, vault = arc_project_statuses(gms=False, vault=False)
    assert gms is None
    assert vault is None
    assert active is not None
    assert active.name == "foo"
    assert active.is_cwd is True
    assert active.access == "rw"
    assert rows[0].name == "foo"
    mock_df.assert_any_call(foo, "foo", current=True)
    mock_df.assert_any_call(bar, "bar", current=False)


def test_collect_status_quotas_includes_home_and_scratch(tmp_path: Path) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    q = QuotaLine(label="x", path="p", used="1", total="2", free="1", pct=50)
    with (
        patch("canfar_lab.core.storage.df_line", return_value=q),
        patch("canfar_lab.core.storage.arc_project_statuses", return_value=(None, [], None, None)),
    ):
        rows = collect_status_quotas(home=home, scratch=scratch)
    assert len(rows) == 2


def test_collect_status_quotas_reuses_projects(tmp_path: Path) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    scratch.mkdir()
    proj_q = QuotaLine(
        label="team", path="p", used="1", total="2", free="1", pct=50, source="statvfs"
    )
    proj = ArcProjectInfo(name="team", path=tmp_path / "team", quota=proj_q, is_cwd=False)
    with (
        patch("canfar_lab.core.storage.df_line", return_value=proj_q),
        patch("canfar_lab.core.storage.arc_project_statuses") as mock_arc,
    ):
        rows = collect_status_quotas(home=home, scratch=scratch, projects=[proj])
    mock_arc.assert_not_called()
    assert any(r.label == "team" for r in rows)


def test_cwd_arc_project_skips_listing() -> None:
    foo = Path("/arc/projects/foo")
    q = QuotaLine(label="foo", path=str(foo), used="1G", total="10G", free="9G", pct=10)
    with (
        patch("canfar_lab.core.storage.find_arc_project_root", return_value=foo),
        patch("canfar_lab.core.storage.list_arc_projects") as mock_list,
        patch("canfar_lab.core.storage.df_line", return_value=q),
        patch("canfar_lab.core.storage.read_acl_groups", return_value=[]),
        patch("canfar_lab.core.storage.project_access", return_value="rw"),
    ):
        info = cwd_arc_project()
    mock_list.assert_not_called()
    assert info is not None
    assert info.name == "foo"
    assert info.is_cwd is True
