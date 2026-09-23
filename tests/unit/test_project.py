from __future__ import annotations

from pathlib import Path

from canfar_lab.core.project import bootstrap_lock, detect_project
from canfar_lab.models.manifest import EnvManifest, ProjectKind


def test_detect_project_pixi(tmp_path: Path) -> None:
    (tmp_path / "pixi.toml").write_text('[project]\nname = "x"\n')
    assert detect_project(tmp_path) == ProjectKind.PIXI


def test_detect_project_uv(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert detect_project(tmp_path) == ProjectKind.UV


def test_bootstrap_lock_skips_existing(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pixi.toml").write_text('[project]\nname = "p"\n')
    (project / "pixi.lock").write_text("existing")
    (save_dir / "pixi.lock").write_text("saved")

    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    (save_dir / "manifest.json").write_text(manifest.model_dump_json())

    assert bootstrap_lock(save_dir, project) is False
    assert (project / "pixi.lock").read_text() == "existing"


def test_bootstrap_lock_copies_when_missing(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pixi.toml").write_text('[project]\nname = "p"\n')
    (save_dir / "pixi.lock").write_text("saved-lock")

    manifest = EnvManifest(
        name="t",
        kind=ProjectKind.PIXI,
        saved_at="t",
        saved_from="/x",
        user="u",
    )
    (save_dir / "manifest.json").write_text(manifest.model_dump_json())

    assert bootstrap_lock(save_dir, project) is True
    assert (project / "pixi.lock").read_text() == "saved-lock"
