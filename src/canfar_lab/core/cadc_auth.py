from __future__ import annotations

from pathlib import Path


def cadc_cert_path() -> Path | None:
    cert = Path.home() / ".ssl" / "cadcproxy.pem"
    return cert if cert.is_file() else None


def has_cadc_netrc() -> bool:
    return (Path.home() / ".netrc").is_file()


def cadc_cli_auth_args() -> list[str] | None:
    cert = cadc_cert_path()
    if cert is not None:
        return ["--cert", str(cert)]
    if has_cadc_netrc():
        return ["-n"]
    return None
