from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from canfar_lab.core.cadc_auth import cadc_cli_auth_args
from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run_capture

GETFACL_TIMEOUT_SEC = 3.0
GMS_TIMEOUT_SEC = 5.0


@dataclass(frozen=True)
class AclGroupEntry:
    name: str
    perms: str


@dataclass
class GmsGroups:
    groups: list[str]
    source: str


def effective_perms(entry: str, mask: str | None) -> str:
    """AND group permissions with optional ACL mask (rwx)."""
    if not mask:
        return entry
    out: list[str] = []
    for char, mask_char in zip(entry.ljust(3, "-"), mask.ljust(3, "-")):
        out.append(char if char != "-" and mask_char != "-" else "-")
    return "".join(out)


def parse_getfacl_output(text: str) -> tuple[str | None, list[AclGroupEntry]]:
    mask: str | None = None
    pending: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("mask::"):
            mask = line.split("::", 1)[1]
            continue
        if not line.startswith("group:"):
            continue
        body = line.removeprefix("group:")
        if ":" not in body:
            continue
        name, perms = body.split(":", 1)
        if not name:
            continue
        pending.append((name, perms))
    groups = [
        AclGroupEntry(name=name, perms=effective_perms(perms, mask)) for name, perms in pending
    ]
    return mask, groups


def read_acl_groups(path: Path) -> list[AclGroupEntry]:
    if not path.is_dir() or shutil.which("getfacl") is None:
        return []
    try:
        out = run_capture(["getfacl", "-p", str(path)], timeout=GETFACL_TIMEOUT_SEC)
    except LabError:
        return []
    _, groups = parse_getfacl_output(out)
    return groups


def project_access(path: Path) -> str:
    if not path.is_dir():
        return "none"
    if os.access(path, os.W_OK):
        return "rw"
    if os.access(path, os.R_OK):
        return "ro"
    if os.access(path, os.X_OK):
        return "x"
    return "none"


def list_gms_groups() -> GmsGroups | None:
    if shutil.which("cadc-groups") is None:
        return None
    auth = cadc_cli_auth_args()
    if auth is None:
        return None
    cmd = ["cadc-groups", "list", "-q", *auth]
    try:
        out = run_capture(cmd, timeout=GMS_TIMEOUT_SEC)
    except LabError:
        return None
    groups = [line.strip() for line in out.splitlines() if line.strip()]
    return GmsGroups(groups=sorted(groups, key=str.lower), source=" ".join(cmd))


def project_gms_member(
    project_name: str,
    acl_groups: list[AclGroupEntry],
    gms: GmsGroups | None,
) -> bool | None:
    if gms is None:
        return None
    names = {project_name.casefold()}
    names.update(g.name.casefold() for g in acl_groups)
    gms_names = {g.casefold() for g in gms.groups}
    return bool(names & gms_names)
