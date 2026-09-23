from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from canfar_lab.core.arc_permissions import GmsGroups
from canfar_lab.core.cadc_auth import cadc_cert_path, has_cadc_netrc
from canfar_lab.core.disk_usage import naturalsize, used_pct
from canfar_lab.core.storage import QuotaLine

logger = logging.getLogger(__name__)

VAULT_SCHEME = "vault"
CADC_GMS_PREFIX = "ivo://cadc.nrc.ca/gms?"


@dataclass
class VaultNodeStatus:
    name: str
    uri: str
    used_bytes: int | None
    quota_bytes: int | None
    read_group: str | None
    write_group: str | None
    gms_member: bool | None
    error: str | None = None

    @property
    def found(self) -> bool:
        return self.error is None

    def quota_line(self, *, current: bool = False) -> QuotaLine | None:
        if self.quota_bytes is None or self.quota_bytes <= 0:
            return None
        used = self.used_bytes or 0
        free = max(self.quota_bytes - used, 0)
        return QuotaLine(
            label=f"{self.name} (vault)",
            path=self.uri,
            used=naturalsize(used),
            total=naturalsize(self.quota_bytes),
            free=naturalsize(free),
            pct=used_pct(used, self.quota_bytes),
            current=current,
            source="vospace",
        )


@dataclass
class VaultStatus:
    nodes: list[VaultNodeStatus] = field(default_factory=list)
    source: str = "vos.Client"
    auth: str | None = None


def gms_name_from_uri(value: str | None) -> str | None:
    if not value or value == "NONE":
        return None
    if value.startswith(CADC_GMS_PREFIX):
        return value[len(CADC_GMS_PREFIX) :]
    if "?" in value:
        return value.split("?", 1)[1]
    return value


def _vos_client():
    from vos import vos  # type: ignore

    cert = cadc_cert_path()
    if cert is not None:
        return vos.Client(vospace_certfile=str(cert)), "cert"
    if has_cadc_netrc():
        return vos.Client(), "netrc"
    return vos.Client(), "anonymous"


def _int_prop(props: dict, key: str) -> int | None:
    raw = props.get(key)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _vault_groups(props: dict) -> tuple[str | None, str | None]:
    read_group = gms_name_from_uri(props.get("groupread"))
    write_group = gms_name_from_uri(props.get("groupwrite"))
    return read_group, write_group


def _vault_gms_member(
    read_group: str | None,
    write_group: str | None,
    gms: GmsGroups | None,
) -> bool | None:
    if gms is None:
        return None
    names = {g.casefold() for g in gms.groups}
    return any(group and group.casefold() in names for group in (read_group, write_group))


def _node_used_bytes(client, uri: str, props: dict) -> int:
    used = _int_prop(props, "length")
    if used is not None:
        return used
    try:
        size = client.size(uri)
    except Exception:  # noqa: BLE001 — vos.Client.size() can raise arbitrary transport errors
        logger.debug("vault size lookup failed for %s", uri, exc_info=True)
        return 0
    try:
        return int(size)
    except (TypeError, ValueError):
        return 0


def vault_node_status(
    name: str,
    *,
    client,
    gms: GmsGroups | None,
) -> VaultNodeStatus:
    uri = f"{VAULT_SCHEME}:/{name}"
    try:
        node = client.get_node(uri)
    except Exception as exc:  # noqa: BLE001 — vos.Client.get_node() transport; NotFound handled below
        err_name = type(exc).__name__
        if err_name in {"NotFoundException", "NodeNotFound"}:
            return VaultNodeStatus(
                name=name,
                uri=uri,
                used_bytes=None,
                quota_bytes=None,
                read_group=None,
                write_group=None,
                gms_member=None,
                error="not_found",
            )
        return VaultNodeStatus(
            name=name,
            uri=uri,
            used_bytes=None,
            quota_bytes=None,
            read_group=None,
            write_group=None,
            gms_member=None,
            error=str(exc),
        )

    read_group, write_group = _vault_groups(node.props)
    return VaultNodeStatus(
        name=name,
        uri=uri,
        used_bytes=_node_used_bytes(client, uri, node.props),
        quota_bytes=_int_prop(node.props, "quota"),
        read_group=read_group,
        write_group=write_group,
        gms_member=_vault_gms_member(read_group, write_group, gms),
    )


def _discover_vault_names(client, gms: GmsGroups | None) -> list[str]:
    if gms is None or not gms.groups:
        return []
    gms_names = {g.casefold() for g in gms.groups}
    discovered: list[str] = []
    try:
        root = client.get_node(f"{VAULT_SCHEME}:/", limit=500)
    except Exception:  # noqa: BLE001 — vos.Client.get_node("/") listing; no VOSpace available is not fatal
        logger.debug("vault root listing failed", exc_info=True)
        return []
    for child in getattr(root, "nodes", []) or []:
        read_group, write_group = _vault_groups(child.props)
        matched = any(
            group and group.casefold() in gms_names
            for group in (read_group, write_group, child.name)
        )
        if matched:
            discovered.append(child.name)
    return discovered


def candidate_vault_names(
    *,
    arc_names: list[str],
    gms: GmsGroups | None,
    client,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(raw: str | None) -> None:
        if not raw:
            return
        key = raw.casefold()
        if key in seen:
            return
        seen.add(key)
        names.append(raw)

    for arc_name in arc_names:
        add(arc_name)
    add(os.environ.get("USER", "").strip() or None)
    for name in _discover_vault_names(client, gms):
        add(name)
    return names


def vault_statuses(
    *,
    arc_names: list[str],
    gms: GmsGroups | None,
) -> VaultStatus | None:
    try:
        from vos import vos  # noqa: F401  # type: ignore
    except ImportError:
        return None

    try:
        client, auth = _vos_client()
    except Exception:  # noqa: BLE001 — vos.Client() auth init; status shows "unavailable" gracefully
        logger.debug("vos client init failed", exc_info=True)
        return None

    names = candidate_vault_names(arc_names=arc_names, gms=gms, client=client)
    if not names:
        return VaultStatus(nodes=[], auth=auth)

    nodes: list[VaultNodeStatus] = []
    for name in names:
        status = vault_node_status(name, client=client, gms=gms)
        if status.found or status.error != "not_found":
            nodes.append(status)
    nodes.sort(key=lambda row: row.name.lower())
    return VaultStatus(nodes=nodes, auth=auth)


def vault_by_name(status: VaultStatus | None) -> dict[str, VaultNodeStatus]:
    if status is None:
        return {}
    return {node.name.casefold(): node for node in status.nodes if node.found}


def vault_node_dict(node: VaultNodeStatus) -> dict:
    quota = node.quota_line()
    return {
        "name": node.name,
        "uri": node.uri,
        "used_bytes": node.used_bytes,
        "quota_bytes": node.quota_bytes,
        "read_group": node.read_group,
        "write_group": node.write_group,
        "gms_member": node.gms_member,
        "error": node.error,
        "quota": quota.__dict__ if quota else None,
    }


def vault_status_dict(status: VaultStatus | None) -> dict | None:
    if status is None:
        return None
    return {
        "service": VAULT_SCHEME,
        "source": status.source,
        "auth": status.auth,
        "nodes": [vault_node_dict(node) for node in status.nodes],
    }
