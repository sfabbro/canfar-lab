from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from canfar_lab.core.arc_permissions import (
    GETFACL_TIMEOUT_SEC,
    GMS_TIMEOUT_SEC,
    AclGroupEntry,
    GmsGroups,
    effective_perms,
    list_gms_groups,
    parse_getfacl_output,
    project_access,
    project_gms_member,
    read_acl_groups,
)


def test_effective_perms_applies_mask() -> None:
    assert effective_perms("rwx", "r-x") == "r-x"
    assert effective_perms("rw-", "r--") == "r--"


def test_parse_getfacl_output() -> None:
    text = """
# file: /arc/projects/foo
group:collab-a:rwx
group:collab-b:r-x
mask::r-x
default:group:collab-a:rwx
""".strip()
    mask, groups = parse_getfacl_output(text)
    assert mask == "r-x"
    assert groups == [
        AclGroupEntry(name="collab-a", perms="r-x"),
        AclGroupEntry(name="collab-b", perms="r-x"),
    ]


def test_project_gms_member_matches_name_or_acl() -> None:
    gms = GmsGroups(groups=["MyGroup", "other"], source="test")
    assert project_gms_member("mygroup", [], gms) is True
    assert (
        project_gms_member(
            "foo",
            [AclGroupEntry(name="other", perms="r-x")],
            gms,
        )
        is True
    )
    assert project_gms_member("foo", [], gms) is False
    assert project_gms_member("foo", [], None) is None


def test_read_acl_groups_uses_getfacl(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    with (
        patch("canfar_lab.core.arc_permissions.shutil.which", return_value="getfacl"),
        patch(
            "canfar_lab.core.arc_permissions.run_capture",
            return_value="group:team:rwx\nmask::rwx",
        ) as mock_run,
    ):
        groups = read_acl_groups(proj)
    assert groups == [AclGroupEntry(name="team", perms="rwx")]
    assert mock_run.call_args.kwargs.get("timeout") == GETFACL_TIMEOUT_SEC


def test_list_gms_groups_times_out_the_cli() -> None:
    with (
        patch("canfar_lab.core.arc_permissions.shutil.which", return_value="cadc-groups"),
        patch("canfar_lab.core.arc_permissions.cadc_cli_auth_args", return_value=["--cert", "x"]),
        patch("canfar_lab.core.arc_permissions.run_capture", return_value="team-a\n") as mock_run,
    ):
        gms = list_gms_groups()
    assert gms is not None
    assert gms.groups == ["team-a"]
    assert mock_run.call_args.kwargs.get("timeout") == GMS_TIMEOUT_SEC


def test_project_access(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    with patch("canfar_lab.core.arc_permissions.os.access", side_effect=[True, False]):
        assert project_access(proj) == "rw"
    with patch("canfar_lab.core.arc_permissions.os.access", side_effect=[False, True]):
        assert project_access(proj) == "ro"


def test_list_gms_groups_no_tool() -> None:
    with patch("canfar_lab.core.arc_permissions.shutil.which", return_value=None):
        assert list_gms_groups() is None
