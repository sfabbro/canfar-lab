from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from canfar_lab.utils.timing import PhaseTimer, call_with_timeout


def test_call_with_timeout_returns_value() -> None:
    assert call_with_timeout(lambda: 7, 1.0, default=0) == 7


def test_call_with_timeout_expires() -> None:
    gate = threading.Event()

    def _block() -> str:
        gate.wait(timeout=5)
        return "late"

    assert call_with_timeout(_block, 0.05, default="skip") == "skip"
    gate.set()


def test_call_with_timeout_does_not_block_process_exit() -> None:
    """Non-daemon executor workers were joined at interpreter shutdown."""
    src = Path(__file__).resolve().parents[2] / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    code = (
        "from canfar_lab.utils.timing import call_with_timeout\n"
        "import time\n"
        "call_with_timeout(lambda: time.sleep(30), 0.15, None)\n"
    )
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        timeout=3,
        check=True,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0
    assert elapsed < 2.0, elapsed


def test_call_with_timeout_propagates_errors() -> None:
    def _boom() -> int:
        raise RuntimeError("nope")

    try:
        call_with_timeout(_boom, 1.0, default=0)
    except RuntimeError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_phase_timer_emits_names() -> None:
    seen: list[str] = []

    def _cb(name: str, dt: float, total: float) -> None:
        seen.append(name)
        assert dt >= 0
        assert total >= dt

    timer = PhaseTimer(_cb)
    with timer.phase("one"):
        time.sleep(0.01)
    with timer.phase("two"):
        pass
    assert seen == ["one", "two"]
