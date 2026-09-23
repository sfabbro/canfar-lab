from __future__ import annotations

from pathlib import Path

from canfar_lab import ui


def _combined(capsys) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def test_env_list_table_empty(capsys) -> None:
    ui.env_list_table([])
    assert "No saved environments" in _combined(capsys)


def test_env_list_table_with_rows(capsys) -> None:
    ui.env_list_table([{"name": "mylab", "kind": "pixi", "saved_at": "t", "path": "/save/mylab"}])
    assert "mylab" in _combined(capsys)


def test_status_human(capsys) -> None:
    from canfar_lab.core.storage import ArcProjectInfo, QuotaLine

    quotas = [
        QuotaLine(
            label="home",
            path="/home",
            used="1G",
            total="10G",
            free="9G",
            pct=90,
        ),
        QuotaLine(
            label="othergroup",
            path="/arc/projects/othergroup",
            used="1G",
            total="100G",
            free="99G",
            pct=1,
        ),
    ]
    active = ArcProjectInfo(
        name="mygroup",
        path=Path("/arc/projects/mygroup"),
        quota=QuotaLine(
            label="mygroup",
            path="/arc/projects/mygroup",
            used="2G",
            total="100G",
            free="98G",
            pct=2,
            current=True,
        ),
        is_cwd=True,
    )
    other = ArcProjectInfo(
        name="othergroup",
        path=Path("/arc/projects/othergroup"),
        quota=quotas[1],
        is_cwd=False,
    )
    ui.status_human(quotas, [(".cache", "1M", "caches")], active, [active, other], ["proc1"])
    combined = _combined(capsys)
    assert "status" in combined.lower()
    assert "mygroup" in combined
    assert "free" in combined.lower()
    assert "Team projects" not in combined
    assert "othergroup" not in combined
    assert "canfar lab clean" in combined

    ui.status_human(
        quotas, [(".cache", "1M", "caches")], active, [active, other], ["proc1"], full=True
    )
    full = _combined(capsys)
    assert "Team projects" in full
    assert "othergroup" in full


def test_print_helpers(capsys) -> None:
    ui.print_error("bad\n  hint `cmd`")
    ui.print_ok("good `cmd`")
    ui.print_hint("hint `cmd`")
    ui.print_info("info `cmd`")
    ui.print_warn("warn `cmd`")
    ui.print_json({"a": 1})
    combined = _combined(capsys)
    assert "bad" in combined
    assert "cmd" in combined
    assert '"a"' in combined


def test_progress_task_quiet() -> None:
    with ui.progress_task("test", quiet=True):
        pass


def test_format_text() -> None:
    assert "[bold #ffaf00]mycmd[/bold #ffaf00]" in ui._format_text("`mycmd`")
    assert ui._format_text("  git status") == "  git status"
    # `agent list` rows collide with CLI names (kilo/goose/cline) — keep plain.
    row = "  kilo         ✓      ✓      home    7.4.11"
    assert "[bold" not in ui._format_text(row)
    assert ui._format_text("  kilo auth") == "  kilo auth"
