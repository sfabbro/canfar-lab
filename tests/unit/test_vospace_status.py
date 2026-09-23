from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from canfar_lab.core.arc_permissions import GmsGroups
from canfar_lab.core.vospace_status import (
    VaultNodeStatus,
    VaultStatus,
    candidate_vault_names,
    gms_name_from_uri,
    vault_by_name,
    vault_node_status,
    vault_status_dict,
    vault_statuses,
)


def test_gms_name_from_uri() -> None:
    assert gms_name_from_uri("ivo://cadc.nrc.ca/gms?bcg-read") == "bcg-read"
    assert gms_name_from_uri("NONE") is None
    assert gms_name_from_uri(None) is None


def test_vault_node_status_parses_quota_and_groups() -> None:
    node = MagicMock()
    node.props = {
        "quota": "1073741824",
        "length": "1048576",
        "groupread": "ivo://cadc.nrc.ca/gms?team-ro",
        "groupwrite": "ivo://cadc.nrc.ca/gms?team-rw",
    }
    client = MagicMock()
    client.get_node.return_value = node
    gms = GmsGroups(groups=["team-ro"], source="test")

    status = vault_node_status("myteam", client=client, gms=gms)

    assert status.found
    assert status.quota_bytes == 1073741824
    assert status.used_bytes == 1048576
    assert status.read_group == "team-ro"
    assert status.write_group == "team-rw"
    assert status.gms_member is True


def test_vault_node_status_not_found() -> None:
    class NotFoundException(Exception):
        pass

    client = MagicMock()
    client.get_node.side_effect = NotFoundException("missing")
    status = vault_node_status("missing", client=client, gms=None)
    assert status.error == "not_found"


def test_vault_statuses_missing_vos(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "vos" or name.startswith("vos."):
            raise ImportError("no vos")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert vault_statuses(arc_names=[], gms=None) is None


def test_vault_statuses_with_mock_client() -> None:
    import sys

    sys.modules["vos"] = MagicMock()
    node = MagicMock()
    node.props = {
        "quota": "2048",
        "groupread": "ivo://cadc.nrc.ca/gms?team-ro",
        "groupwrite": "NONE",
    }
    client = MagicMock()
    client.get_node.return_value = node
    client.size.return_value = 512
    gms = GmsGroups(groups=["team-ro"], source="test")

    with (
        patch.dict(sys.modules, {"vos": MagicMock()}),
        patch(
            "canfar_lab.core.vospace_status._vos_client",
            return_value=(client, "anonymous"),
        ),
        patch(
            "canfar_lab.core.vospace_status.candidate_vault_names",
            return_value=["team"],
        ),
    ):
        status = vault_statuses(arc_names=["team"], gms=gms)

    assert status is not None
    assert status.auth == "anonymous"
    assert len(status.nodes) == 1
    assert status.nodes[0].read_group == "team-ro"
    assert status.nodes[0].quota_bytes == 2048


def test_vault_statuses_empty_candidates() -> None:
    client = MagicMock()
    with (
        patch.dict(sys.modules, {"vos": MagicMock()}),
        patch(
            "canfar_lab.core.vospace_status._vos_client",
            return_value=(client, "netrc"),
        ),
        patch(
            "canfar_lab.core.vospace_status.candidate_vault_names",
            return_value=[],
        ),
    ):
        status = vault_statuses(arc_names=[], gms=None)

    assert status is not None
    assert status.nodes == []
    assert status.auth == "netrc"


def test_candidate_vault_names_deduplicates(monkeypatch) -> None:
    monkeypatch.setenv("USER", "alice")
    client = MagicMock()
    with patch(
        "canfar_lab.core.vospace_status._discover_vault_names",
        return_value=["Team", "extra"],
    ):
        names = candidate_vault_names(
            arc_names=["team"],
            gms=GmsGroups(groups=["team-ro"], source="test"),
            client=client,
        )
    assert names == ["team", "alice", "extra"]


def test_vault_status_dict_and_by_name() -> None:
    node = VaultNodeStatus(
        name="home",
        uri="vault:/home",
        used_bytes=100,
        quota_bytes=1000,
        read_group="ro",
        write_group=None,
        gms_member=True,
    )
    vault = VaultStatus(nodes=[node], auth="cert")
    data = vault_status_dict(vault)
    assert data is not None
    assert data["service"] == "vault"
    assert data["auth"] == "cert"
    assert data["nodes"][0]["read_group"] == "ro"
    assert vault_by_name(vault)["home"] is node
    assert vault_status_dict(None) is None
    assert vault_by_name(None) == {}


def test_vault_quota_line() -> None:
    node = VaultNodeStatus(
        name="home",
        uri="vault:/home",
        used_bytes=100,
        quota_bytes=1000,
        read_group=None,
        write_group=None,
        gms_member=None,
    )
    line = node.quota_line(current=True)
    assert line is not None
    assert line.label == "home (vault)"
    assert line.current is True
    assert line.pct == 10
    assert line.source == "vospace"


def test_discover_vault_names() -> None:
    from canfar_lab.core.vospace_status import _discover_vault_names

    child1 = MagicMock()
    child1.name = "proj1"
    child1.props = {
        "groupread": "ivo://cadc.nrc.ca/gms?team-ro",
        "groupwrite": "NONE",
    }

    child2 = MagicMock()
    child2.name = "proj2"
    child2.props = {
        "groupread": "NONE",
        "groupwrite": "ivo://cadc.nrc.ca/gms?other-team",
    }

    root = MagicMock()
    root.nodes = [child1, child2]

    client = MagicMock()
    client.get_node.return_value = root

    gms = GmsGroups(groups=["team-ro"], source="test")
    names = _discover_vault_names(client, gms)
    assert names == ["proj1"]
