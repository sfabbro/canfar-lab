"""Shared test helpers for astroai tests.

Add fixtures and utility functions here that need to be reused across
multiple test modules.  Prefer this module over conftest.py for plain
helper functions — conftest.py is for pytest fixture auto-discovery.
"""

from __future__ import annotations

from pathlib import Path

from canfar_lab.models.manifest import EnvManifest, ProjectKind


def write_manifest(
    save_dir: Path,
    name: str,
    kind: ProjectKind = ProjectKind.PIXI,
    full: bool = False,
) -> None:
    """Create a minimal save fixture — a directory with a manifest.json.

    Used by tests that exercise list_saves, save_rows, restore_env, etc.
    without needing a real pixi/uv project.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    manifest = EnvManifest(
        name=name,
        kind=kind,
        saved_at="20250101T000000Z",
        saved_from="/scratch/src/" + name,
        user="testuser",
        full=full,
    )
    (save_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
