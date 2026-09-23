from __future__ import annotations

from pathlib import Path

from canfar_lab.core.cadc_auth import (
    cadc_cert_path,
    cadc_cli_auth_args,
    has_cadc_netrc,
)


def test_cadc_cert_path_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cadc_cert_path() is None


def test_cadc_cert_path_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cert = tmp_path / ".ssl" / "cadcproxy.pem"
    cert.parent.mkdir(parents=True)
    cert.write_text("dummy", encoding="utf-8")
    assert cadc_cert_path() == cert


def test_has_cadc_netrc(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert has_cadc_netrc() is False
    (tmp_path / ".netrc").write_text("machine example", encoding="utf-8")
    assert has_cadc_netrc() is True


def test_cadc_cli_auth_args_prefers_cert(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cert = tmp_path / ".ssl" / "cadcproxy.pem"
    cert.parent.mkdir(parents=True)
    cert.write_text("dummy", encoding="utf-8")
    (tmp_path / ".netrc").write_text("machine example", encoding="utf-8")
    assert cadc_cli_auth_args() == ["--cert", str(cert)]


def test_cadc_cli_auth_args_netrc_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".netrc").write_text("machine example", encoding="utf-8")
    assert cadc_cli_auth_args() == ["-n"]


def test_cadc_cli_auth_args_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cadc_cli_auth_args() is None
