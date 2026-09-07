"""CanfarOps session-catalog helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from astroai_workload.canfar_ops import CanfarOps


def test_list_headless_sessions_uses_own_catalog_not_view_all() -> None:
    """view=all strips id/name; hard-cap requires the caller\'s own catalog."""
    ops = CanfarOps.__new__(CanfarOps)
    sess = MagicMock()
    sess.fetch.return_value = [
        {"id": "a", "name": "ray-as-c1-1", "status": "Running"},
        {"id": "b", "name": "other", "status": "Running"},
    ]
    ops._fresh_session = MagicMock(return_value=sess)
    rows = ops.list_headless_sessions(name_prefix="ray-as-")
    assert [r["id"] for r in rows] == ["a"]
    assert sess.fetch.call_args.kwargs == {"kind": "headless"}


def test_list_sessions_uses_own_catalog() -> None:
    ops = CanfarOps.__new__(CanfarOps)
    sess = MagicMock()
    sess.fetch.return_value = [{"id": "m", "name": "raymgr", "status": "Running"}]
    ops._fresh_session = MagicMock(return_value=sess)
    assert ops.list_sessions()[0]["id"] == "m"
    assert sess.fetch.call_args.kwargs == {}
