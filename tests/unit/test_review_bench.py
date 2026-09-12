"""Tests for review-bench provisioning + dsh credential plumbing."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from astroai_lab.agent import review_bench as rb
from astroai_lab.agent.registry import get_registry_agent


@pytest.fixture(autouse=True)
def _clear_dsh_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (*rb.DSH_KEYS, "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)


def test_registry_includes_dsh_npm() -> None:
    dsh = get_registry_agent("dsh")
    assert dsh is not None
    assert dsh["install"]["method"] == "npm"
    assert "dsh" in dsh["install"]["source"]
    assert dsh["config"]["path"] == "~/.dsh/settings.yaml"


def test_validate_vendored_preset_clean() -> None:
    checks, failures = rb.validate_preset()
    assert failures == []
    assert any("persona lenses" in c for c in checks)
    assert any("managed bench" in c for c in checks)


def test_validate_rejects_missing_tree(tmp_path: Path) -> None:
    checks, failures = rb.validate_preset(tmp_path / "absent")
    assert failures
    assert checks == []


def test_discover_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "d-key")
    keys = rb.discover_dsh_keys(tmp_path)
    assert keys["GEMINI_API_KEY"] == "g-key"
    assert keys["DEEPSEEK_API_KEY"] == "d-key"


def test_discover_reads_opencode_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = tmp_path / ".local" / "share" / "opencode" / "auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text(json.dumps({"opencode-go": {"key": "zen-key"}}), encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
    keys = rb.discover_dsh_keys(tmp_path)
    assert keys["OPENCODE_API_KEY"] == "zen-key"


def test_ensure_settings_keeps_user_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_API_KEY", "zen-key")
    settings = tmp_path / ".dsh" / "settings.yaml"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        yaml.safe_dump(
            {"agent-default-model": {"provider": "google", "model": "gemini-2.5-flash"}}
        ),
        encoding="utf-8",
    )
    route = rb.ensure_dsh_settings(tmp_path, dry_run=False)
    assert route == "google"  # user pin kept
    doc = yaml.safe_load(settings.read_text(encoding="utf-8"))
    assert doc["agent-default-model"]["provider"] == "google"
    assert doc["llm-pi-ai"]["providers"]["opencode-go"] == {"apiKeyEnv": "OPENCODE_API_KEY"}


def test_ensure_settings_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "d-key")
    assert rb.ensure_dsh_settings(tmp_path, dry_run=True) == "deepseek-official"
    assert not (tmp_path / ".dsh" / "settings.yaml").exists()


def test_ensure_dotenv_preserves_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENCODE_API_KEY", "zen-key")
    dotenv = tmp_path / ".astroai" / "lab" / ".env"
    dotenv.parent.mkdir(parents=True)
    dotenv.write_text("OPENROUTER_API_KEY=sk-or\n", encoding="utf-8")
    rb.ensure_dsh_dotenv(tmp_path, dry_run=False)
    text = dotenv.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=sk-or" in text
    assert "OPENCODE_API_KEY=zen-key" in text
    assert oct(dotenv.stat().st_mode & 0o777) == "0o600"


def test_ensure_review_bench_installs_and_idempotent(tmp_path: Path) -> None:
    assert rb.ensure_review_bench(tmp_path, dry_run=True) is True
    assert not (tmp_path / ".astroai").exists()  # dry-run writes nothing
    assert rb.ensure_review_bench(tmp_path, dry_run=False) is True
    bench = tmp_path / ".astroai" / "lab" / "review-bench"
    assert (bench / "presets" / "review-bench" / "agent.cordis.yml").is_file()
    assert (bench / "skills" / "review-panel" / "SKILL.md").is_file()
    web = tmp_path / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    assert web.is_file()
    assert (tmp_path / ".dsh" / "profiles" / "headless" / "cordis.yml").is_file()
    # Second run without force: nothing new, no clobber.
    assert rb.ensure_review_bench(tmp_path, dry_run=False) is False
    # Differing user layer is kept without --force.
    web.write_text("custom: true\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="Refusing to overwrite"):
        assert rb.ensure_review_bench(tmp_path, dry_run=False) is False
    assert web.read_text(encoding="utf-8") == "custom: true\n"
    assert rb.ensure_review_bench(tmp_path, dry_run=False, force=True) is True


def test_no_keys_without_env(tmp_path: Path) -> None:
    assert rb.discover_dsh_keys(tmp_path) == {}
    assert rb.ensure_dsh_settings(tmp_path, dry_run=False) is None
    assert os.environ.get("OPENCODE_API_KEY") is None  # never leak into process env
