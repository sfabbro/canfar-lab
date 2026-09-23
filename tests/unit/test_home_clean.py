from __future__ import annotations

from pathlib import Path

import pytest

from canfar_lab.core.home_clean import cache_targets, plan_clean


def test_cache_targets_lists_runtime_cache_dirs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    mystery = home / ".cache" / "some-new-tool"
    mystery.mkdir(parents=True)
    (mystery / "blob").write_text("x", encoding="utf-8")
    pip = home / ".cache" / "pip"
    pip.mkdir()
    (home / ".pixi" / "cache").mkdir(parents=True)
    paths = {p.name for p in cache_targets(home)}
    assert "some-new-tool" in paths
    assert "pip" in paths
    assert "cache" in paths  # .pixi/cache


def test_cache_targets_includes_home_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    xdg = home / ".xdg-cache"
    xdg.mkdir(parents=True)
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))
    assert xdg in cache_targets(home)


def test_cache_targets_skips_scratch_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    scratch = tmp_path / "scratch"
    home.mkdir()
    xdg = scratch / ".cache-user"
    xdg.mkdir(parents=True)
    (xdg / "pip").mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))
    assert cache_targets(home) == []


def test_plan_clean_sizes_home_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = home / ".cache" / "uv"
    blob.mkdir(parents=True)
    (blob / "x").write_text("hello", encoding="utf-8")
    plan = plan_clean(home, home / "saves")
    assert plan["caches"]
    assert plan["cache_bytes"] >= 5
    assert any(row["path"].endswith(".cache/uv") for row in plan["caches"])
