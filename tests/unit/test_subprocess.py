from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run, run_capture, run_cmd


def test_run_cmd_not_found() -> None:
    with pytest.raises(LabError, match="not found"):
        run_cmd(["definitely-not-a-real-command-xyz"])


def test_run_cmd_called_process_error() -> None:
    with patch("canfar_lab.utils.subprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["false"], stderr="boom")
        with pytest.raises(LabError, match="Command failed"):
            run_cmd(["false"])


def test_run_and_run_capture() -> None:
    with patch("canfar_lab.utils.subprocess.run_cmd") as mock_cmd:
        mock_cmd.return_value = subprocess.CompletedProcess(["echo"], 0, stdout="hi\n")
        assert run_capture(["echo"]) == "hi"
        run(["echo"])
        assert mock_cmd.call_count == 2
