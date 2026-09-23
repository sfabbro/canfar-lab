"""OpenCode config semantic sanitize / verify."""

from __future__ import annotations

from pathlib import Path

import pytest

from canfar_lab.agent.fix import fix_agent_setup, repair_installed_agents
from canfar_lab.agent.inventory import verify_setup
from canfar_lab.agent.opencode_config import opencode_config_issues, sanitize_opencode_config
from canfar_lab.agent.registry import fix_registry_agent
from canfar_lab.utils.json_utils import read_jsonc


def test_sanitize_lsp_boolean_entries() -> None:
    data = {
        "lsp": {"pyright": True, "clangd": True, "bash": True},
        "mcp": {"x": {"type": "remote", "url": "https://example.com"}},
    }
    assert opencode_config_issues(data)
    cleaned, changes = sanitize_opencode_config(data)
    assert cleaned["lsp"] is True
    assert any("pyright" in c for c in changes)
    assert opencode_config_issues(cleaned) == []


def test_sanitize_lsp_false_becomes_disabled() -> None:
    cleaned, changes = sanitize_opencode_config({"lsp": {"pyright": False}})
    assert cleaned["lsp"] == {"pyright": {"disabled": True}}
    assert any("disabled" in c for c in changes)


def test_sanitize_preserves_valid_command_entries() -> None:
    entry = {"command": ["ty", "server"], "extensions": [".py"]}
    cleaned, changes = sanitize_opencode_config({"lsp": {"pyright": True, "ty": entry}})
    assert cleaned["lsp"] == {"ty": entry}
    assert changes
    assert "pyright" in "".join(changes)


def test_verify_reports_opencode_lsp_booleans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    cfg = home / ".config" / "opencode" / "opencode.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        '{\n  "lsp": {"pyright": true, "clangd": true, "bash": true},\n  "mcp": {}\n}\n',
        encoding="utf-8",
    )

    def _classify(binary: str, *, home=None):
        if binary == "opencode":
            return {
                "binary": binary,
                "path": "/tmp/opencode",
                "source": "managed",
                "managed": True,
                "home_install": False,
                "home_path": None,
            }
        return {
            "binary": binary,
            "path": None,
            "source": "missing",
            "managed": False,
            "home_install": False,
            "home_path": None,
        }

    monkeypatch.setattr("canfar_lab.agent.install.classify_binary", _classify)
    issues = verify_setup(home)
    assert any("lsp.pyright" in i for i in issues)
    assert any("lsp.clangd" in i for i in issues)


def test_verify_skips_opencode_lsp_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leftover opencode.json must not fail day-one verify without the binary."""
    home = tmp_path / "home"
    cfg = home / ".config" / "opencode" / "opencode.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        '{\n  "lsp": {"pyright": true},\n  "mcp": {}\n}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "canfar_lab.agent.install.classify_binary",
        lambda *a, **k: {
            "binary": "x",
            "path": None,
            "source": "missing",
            "managed": False,
            "home_install": False,
            "home_path": None,
        },
    )
    issues = verify_setup(home)
    assert not any("lsp." in i or "OpenCode" in i for i in issues)


def test_fix_agent_setup_sanitizes_opencode_lsp(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cfg = home / ".config" / "opencode" / "opencode.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "{\n"
        '  "lsp": {"pyright": true, "clangd": true},\n'
        '  "mcp": {"a": {"type": "remote", "url": "u"}}\n'
        "}\n",
        encoding="utf-8",
    )
    results = fix_agent_setup(home=home, dry_run=False)
    assert any(r.fixed and "Sanitized OpenCode" in r.detail for r in results)
    data = read_jsonc(cfg)
    assert data["lsp"] is True
    assert data["mcp"]["a"]["url"] == "u"
    assert opencode_config_issues(data) == []
    assert not any("lsp.pyright" in i for i in verify_setup(home))


def test_fix_registry_opencode_sanitizes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cfg = home / ".config" / "opencode" / "opencode.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"lsp": {"bash": true}, "mcp": {}}\n', encoding="utf-8")
    result = fix_registry_agent("opencode", home=home)
    assert result["ok"]
    assert any("sanitized OpenCode" in a for a in result["actions"])
    assert read_jsonc(cfg)["lsp"] is True


def test_repair_installed_includes_opencode_sanitize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CANFAR_LAB_BIN_DIR", str(bin_dir))
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")

    def _classify(binary: str, *, home=None):
        if binary == "opencode":
            return {
                "binary": binary,
                "path": str(bin_dir / "opencode"),
                "source": "managed",
                "managed": True,
                "home_install": False,
                "home_path": None,
            }
        return {
            "binary": binary,
            "path": None,
            "source": "missing",
            "managed": False,
            "home_install": False,
            "home_path": None,
        }

    monkeypatch.setattr("canfar_lab.agent.install.classify_binary", _classify)
    (bin_dir / "opencode").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    (bin_dir / "opencode").chmod(0o755)

    cfg = home / ".config" / "opencode" / "opencode.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"lsp": {"pyright": true}}\n', encoding="utf-8")

    repair = repair_installed_agents(home=home, dry_run=False)
    assert repair["ok"]
    assert read_jsonc(cfg)["lsp"] is True
