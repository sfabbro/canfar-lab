from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from canfar_lab.core.kernel import list_kernels, register_kernel, unregister_kernel
from canfar_lab.errors import LabError


def _pixi_with_env(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pixi.toml").write_text('[project]\nname="p"\n')
    py = path / ".pixi" / "envs" / "default" / "bin"
    py.mkdir(parents=True)
    (py / "python").write_text("#!/bin/sh")


def test_register_kernel(tmp_path: Path) -> None:
    project = tmp_path / "mylab"
    _pixi_with_env(project)
    with (
        patch("canfar_lab.core.kernel.shutil.which", return_value="/usr/bin/jupyter"),
        patch("canfar_lab.core.kernel.run") as mock_run,
    ):
        name = register_kernel(project, name="mylab")
    assert name == "mylab"
    mock_run.assert_called_once()


def test_register_kernel_no_jupyter() -> None:
    with (
        patch("canfar_lab.core.kernel.shutil.which", return_value=None),
        pytest.raises(LabError, match="jupyter not found"),
    ):
        register_kernel(Path("/tmp"))


def test_register_kernel_no_env(tmp_path: Path) -> None:
    project = tmp_path / "mylab"
    project.mkdir()
    (project / "pixi.toml").write_text('[project]\nname="p"\n')
    with (
        patch("canfar_lab.core.kernel.shutil.which", return_value="/usr/bin/jupyter"),
        pytest.raises(LabError, match="not installed"),
    ):
        register_kernel(project)


def test_list_kernels() -> None:
    payload = json.dumps({"kernelspecs": {"mylab": {"resource_dir": "/k/mylab"}}})
    with (
        patch("canfar_lab.core.kernel.shutil.which", return_value="/usr/bin/jupyter"),
        patch("canfar_lab.core.kernel.run_capture", return_value=payload),
    ):
        rows = list_kernels()
    assert rows[0]["name"] == "mylab"


def test_list_kernels_no_jupyter() -> None:
    with patch("canfar_lab.core.kernel.shutil.which", return_value=None):
        assert list_kernels() == []


def test_unregister_kernel() -> None:
    with (
        patch("canfar_lab.core.kernel.shutil.which", return_value="/usr/bin/jupyter"),
        patch("canfar_lab.core.kernel.run") as mock_run,
    ):
        unregister_kernel("mylab")
    mock_run.assert_called_once()
