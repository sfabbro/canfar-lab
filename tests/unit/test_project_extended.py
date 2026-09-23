from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from canfar_lab.core.project import (
    detect_project,
    format_dir_size,
    install_project,
    read_manifest,
    require_project,
    resolve_save_dir,
    restore_env,
    save_env,
    tar_zst,
    warm_cache,
    write_manifest,
)
from canfar_lab.errors import LabError
from canfar_lab.models.manifest import EnvManifest, ProjectKind


def _pixi(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname = "p"\n')
    (path / "pixi.lock").write_text("lock")


def _uv(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text('[project]\nname = "p"\n')
    (path / "uv.lock").write_text("lock")


def test_require_project_raises(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="No pixi or uv"):
        require_project(tmp_path)


def test_resolve_save_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="Save not found"):
        resolve_save_dir("missing", tmp_path, None)


def test_format_dir_size(tmp_path: Path) -> None:
    assert format_dir_size(tmp_path / "nope") == "0 B"
    d = tmp_path / "data"
    d.mkdir()
    (d / "f").write_text("hello")
    assert "B" in format_dir_size(d)


def test_write_and_read_manifest(tmp_path: Path) -> None:
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="20260101T000000Z",
        saved_from="/x",
        user="u",
    )
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    loaded = read_manifest(path)
    assert loaded.name == "t"


def test_save_env_uv_project(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _uv(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    assert (save_dir / "pyproject.toml").is_file()
    assert (save_dir / "manifest.json").is_file()


def test_save_env_full_requires_env_dir(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    with pytest.raises(LabError, match="No .pixi"):
        save_env("proj", tmp_path / "save", project, full=True)


def test_save_env_full_packs(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    env_dir = project / ".pixi"
    env_dir.mkdir()
    (env_dir / "dummy").write_text("x")

    mock_tar = MagicMock()
    mock_tar.stdout = MagicMock()
    mock_tar.returncode = 0
    mock_tar.communicate.return_value = (b"", b"")

    mock_zstd = MagicMock()
    mock_zstd.returncode = 0
    mock_zstd.communicate.return_value = (b"", b"")

    def popen(cmd: list[str], **_kwargs: object) -> MagicMock:
        return mock_tar if cmd[0] == "tar" else mock_zstd

    with patch("canfar_lab.core.project.subprocess.Popen", side_effect=popen):
        save_env("proj", tmp_path / "save", project, full=True)
    assert (tmp_path / "save" / "env.tar.zst").exists()
    assert read_manifest(tmp_path / "save" / "manifest.json").full is True


def test_restore_env_installs_when_not_full(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    dest = tmp_path / "restored"
    with patch("canfar_lab.core.project.install_project") as install:
        restore_env(save_dir, dest)
    install.assert_called_once_with(dest)


def test_restore_env_full_unpacks(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project, full=False)
    manifest = read_manifest(save_dir / "manifest.json")
    manifest.full = True
    write_manifest(save_dir / "manifest.json", manifest)
    (save_dir / "env.tar.zst").write_bytes(b"fake")

    mock_zstd = MagicMock()
    mock_zstd.stdout = MagicMock()
    mock_zstd.returncode = 0
    with (
        patch("canfar_lab.core.project.subprocess.Popen", return_value=mock_zstd),
        patch("canfar_lab.core.project.subprocess.run") as mock_run,
    ):
        restore_env(save_dir, tmp_path / "dest")
    mock_run.assert_called_once()


def test_install_project_pixi(tmp_path: Path) -> None:
    _pixi(tmp_path)
    with patch("canfar_lab.core.project.run") as mock_run:
        install_project(tmp_path)
    mock_run.assert_called_with(["pixi", "install"], cwd=tmp_path, quiet=False)


def test_install_project_uv_bootstrap(tmp_path: Path) -> None:
    _uv(tmp_path)
    with (
        patch("canfar_lab.core.project._run_uv_sync", return_value=False),
        patch("canfar_lab.core.project.run") as mock_run,
    ):
        install_project(tmp_path, bootstrap_lock=True)
    assert mock_run.call_count >= 2


def test_install_project_bootstrap_skips_second_when_first_ok(tmp_path: Path) -> None:
    _pixi(tmp_path)
    with (
        patch("canfar_lab.core.project._run_pixi_install", return_value=True) as first,
        patch("canfar_lab.core.project.run") as mock_run,
    ):
        install_project(tmp_path, bootstrap_lock=True)
    first.assert_called_once()
    mock_run.assert_not_called()


def test_warm_cache_pixi(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    _pixi(save_dir)
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    write_manifest(save_dir / "manifest.json", manifest)
    with patch("canfar_lab.core.project.run") as mock_run:
        warm_cache(save_dir)
    mock_run.assert_called_once()


def test_warm_cache_uv(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    _uv(save_dir)
    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.UV,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    write_manifest(save_dir / "manifest.json", manifest)
    with patch("canfar_lab.core.project.run") as mock_run:
        warm_cache(save_dir)
    mock_run.assert_called_once()


def test_init_project_mocked(tmp_path: Path) -> None:
    from canfar_lab.core.project import init_project

    target = tmp_path / "new"
    with patch("canfar_lab.core.project.run") as mock_run:
        kind = init_project(target, use_uv=True)
    assert kind == ProjectKind.UV
    mock_run.assert_called_once()


def test_save_kind_switch_drops_previous_kind(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("p", save_dir, project)
    (project / "pixi.toml").unlink()
    (project / "pixi.lock").unlink()
    _uv(project)
    save_env("p", save_dir, project)
    assert not (save_dir / "pixi.toml").exists()
    assert not (save_dir / "pixi.lock").exists()
    assert (save_dir / "pyproject.toml").is_file()
    dest = tmp_path / "out"
    with patch("canfar_lab.core.project.install_project"):
        restore_env(save_dir, dest)
    assert detect_project(dest) == ProjectKind.UV
    assert not (dest / "pixi.toml").exists()


def test_save_full_failure_leaves_previous(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    (project / ".pixi").mkdir()
    (project / ".pixi" / "x").write_text("x")
    with (
        patch(
            "canfar_lab.core.project.tar_zst",
            side_effect=LabError("Failed to compress environment pack"),
        ),
        pytest.raises(LabError, match="compress"),
    ):
        save_env("proj", save_dir, project, full=True)
    assert (save_dir / "pixi.toml").is_file()
    assert read_manifest(save_dir / "manifest.json").full is False
    assert not (save_dir / "env.tar.zst").exists()


def test_tar_zst_raises_on_zstd_failure(tmp_path: Path) -> None:
    src = tmp_path / "env"
    src.mkdir()
    (src / "f").write_text("x")
    mock_tar = MagicMock()
    mock_tar.stdout = MagicMock()
    mock_tar.returncode = 0
    mock_tar.communicate.return_value = (b"", b"")
    mock_zstd = MagicMock()
    mock_zstd.returncode = 1
    mock_zstd.communicate.return_value = (b"", b"fail")

    def popen(cmd: list[str], **_kwargs: object) -> MagicMock:
        return mock_tar if cmd[0] == "tar" else mock_zstd

    with (
        patch("canfar_lab.core.project.subprocess.Popen", side_effect=popen),
        pytest.raises(LabError, match="compress"),
    ):
        tar_zst(src, tmp_path / "out.tar.zst", arcname="env")


def test_restore_unpack_tar_failure_is_lab_error(tmp_path: Path) -> None:
    import subprocess as sp

    project = tmp_path / "proj"
    _pixi(project)
    save_dir = tmp_path / "save"
    save_env("proj", save_dir, project)
    manifest = read_manifest(save_dir / "manifest.json")
    manifest.full = True
    write_manifest(save_dir / "manifest.json", manifest)
    (save_dir / "env.tar.zst").write_bytes(b"fake")

    mock_zstd = MagicMock()
    mock_zstd.stdout = MagicMock()
    mock_zstd.returncode = 0
    mock_zstd.communicate.return_value = (b"", b"")
    with (
        patch("canfar_lab.core.project.subprocess.Popen", return_value=mock_zstd),
        patch(
            "canfar_lab.core.project.subprocess.run",
            side_effect=sp.CalledProcessError(2, ["tar", "-xf", "-"]),
        ),
        pytest.raises(LabError, match="unpack"),
    ):
        restore_env(save_dir, tmp_path / "dest")


def test_save_refuses_high_quota(tmp_path: Path) -> None:
    from canfar_lab.core.disk_usage import DiskUsage

    project = tmp_path / "proj"
    _pixi(project)
    fake = DiskUsage(
        path=str(tmp_path),
        used_bytes=99,
        total_bytes=100,
        free_bytes=200 * 1024 * 1024,
        pct=99,
        source="ceph-xattr",
    )
    with (
        patch("canfar_lab.core.disk_usage.disk_usage", return_value=fake),
        pytest.raises(LabError, match="Quota"),
    ):
        save_env("proj", tmp_path / "save", project)


def test_save_refuses_low_free_space(tmp_path: Path) -> None:
    from canfar_lab.core.disk_usage import DiskUsage

    project = tmp_path / "proj"
    _pixi(project)
    fake = DiskUsage(
        path=str(tmp_path),
        used_bytes=50,
        total_bytes=100,
        free_bytes=10 * 1024 * 1024,
        pct=50,
        source="statvfs",
    )
    with (
        patch("canfar_lab.core.disk_usage.disk_usage", return_value=fake),
        pytest.raises(LabError, match="Low disk space"),
    ):
        save_env("proj", tmp_path / "save", project)


def test_save_allows_statvfs_high_pct_with_free_space(tmp_path: Path) -> None:
    from canfar_lab.core.disk_usage import DiskUsage

    project = tmp_path / "proj"
    _pixi(project)
    fake = DiskUsage(
        path=str(tmp_path),
        used_bytes=99,
        total_bytes=100,
        free_bytes=200 * 1024 * 1024,
        pct=99,
        source="statvfs",
    )
    with patch("canfar_lab.core.disk_usage.disk_usage", return_value=fake):
        save_env("proj", tmp_path / "save", project)
    assert (tmp_path / "save" / "pixi.toml").is_file()


def test_resolve_save_dir_hint_is_save_not_env_save(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="canfar lab save missing") as exc:
        resolve_save_dir("missing", tmp_path, None)
    assert "env save" not in str(exc.value)
