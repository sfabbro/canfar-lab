"""Unit tests for pure-logic functions across core and shell modules.

These functions need only Path fixtures and data structs — no external tools
(git, pixi, uv, canfar, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canfar_lab.core.arc_permissions import (
    AclGroupEntry,
    effective_perms,
    parse_getfacl_output,
)
from canfar_lab.core.project import (
    detect_project,
    list_saves,
    read_manifest,
    resolve_save_dir,
    save_rows,
)
from canfar_lab.core.vospace_status import _vault_groups, gms_name_from_uri
from canfar_lab.errors import LabError
from canfar_lab.models.manifest import ProjectKind
from canfar_lab.shell.session_env import (
    _path_under_roots,
    _session_cache_path,
    _session_runtime_path,
)
from tests.helpers import write_manifest


# ===============================================================
# gms_name_from_uri / _vault_groups tests
# ===============================================================
class TestGmsNameFromUri:
    def test_gms_prefix(self) -> None:
        uri = "ivo://cadc.nrc.ca/gms?mygroup"
        assert gms_name_from_uri(uri) == "mygroup"

    def test_other_prefix_with_query(self) -> None:
        uri = "http://example.com/groups?myteam"
        assert gms_name_from_uri(uri) == "myteam"

    def test_uri_with_multiple_question_marks(self) -> None:
        """split('?', 1) takes everything after first '?' — preserves later '?'."""
        assert gms_name_from_uri("http://example.com/path?a=b?c=d") == "a=b?c=d"
        assert gms_name_from_uri("ivo://cadc.nrc.ca/gms?group?extra") == "group?extra"
        # no query param delimiter, just literal text with '?'
        assert gms_name_from_uri("ivo://other.example.com/gms?grp1?grp2") == "grp1?grp2"

    def test_plain_name(self) -> None:
        assert gms_name_from_uri("mygroup") == "mygroup"

    def test_none_value(self) -> None:
        assert gms_name_from_uri(None) is None

    def test_none_string(self) -> None:
        assert gms_name_from_uri("NONE") is None

    def test_empty_string(self) -> None:
        assert gms_name_from_uri("") is None


class TestVaultGroups:
    def test_extracts_groups(self) -> None:
        props = {
            "groupread": "ivo://cadc.nrc.ca/gms?readers",
            "groupwrite": "ivo://cadc.nrc.ca/gms?writers",
        }
        read_group, write_group = _vault_groups(props)
        assert read_group == "readers"
        assert write_group == "writers"

    def test_missing_keys(self) -> None:
        read_group, write_group = _vault_groups({})
        assert read_group is None
        assert write_group is None

    def test_none_values(self) -> None:
        props = {"groupread": "NONE", "groupwrite": None}
        read_group, write_group = _vault_groups(props)
        assert read_group is None
        assert write_group is None

    def test_plain_names(self) -> None:
        props = {"groupread": "readers", "groupwrite": "writers"}
        read_group, write_group = _vault_groups(props)
        assert read_group == "readers"
        assert write_group == "writers"


# ===============================================================
# effective_perms / parse_getfacl_output tests
# ===============================================================
class TestEffectivePerms:
    def test_no_mask_returns_entry(self) -> None:
        assert effective_perms("rwx", None) == "rwx"
        assert effective_perms("r--", None) == "r--"

    def test_mask_ands_perms(self) -> None:
        assert effective_perms("rwx", "r-x") == "r-x"
        assert effective_perms("r-x", "rwx") == "r-x"
        assert effective_perms("rwx", "---") == "---"

    def test_mask_with_short_perms(self) -> None:
        # rw gets padded to rw-, mask r-x → r--
        assert effective_perms("rw", "r-x") == "r--"
        assert effective_perms("r", "rwx") == "r--"

    def test_zero_length_entry(self) -> None:
        """Empty entry gets ljust-padded to ---, so AND with any mask is ---."""
        assert effective_perms("", "r-x") == "---"
        assert effective_perms("", "rwx") == "---"
        assert effective_perms("", "---") == "---"


class TestParseGetfaclOutput:
    def test_basic(self) -> None:
        text = (
            "# file: /arc/projects/demo\n"
            "# owner: root\n"
            "user::rwx\n"
            "group::r-x\n"
            "mask::rwx\n"
            "group:cadc:r-x\n"
            "group:staff:rw-\n"
            "other::r--\n"
        )
        mask, groups = parse_getfacl_output(text)
        assert mask == "rwx"
        assert len(groups) == 2
        assert groups[0] == AclGroupEntry(name="cadc", perms="r-x")
        assert groups[1] == AclGroupEntry(name="staff", perms="rw-")

    def test_no_mask(self) -> None:
        text = "group:dev:rwx\n"
        mask, groups = parse_getfacl_output(text)
        assert mask is None
        assert groups[0].perms == "rwx"  # no mask applied

    def test_mask_restricts(self) -> None:
        text = "mask::r-x\ngroup:dev:rwx\n"
        _, groups = parse_getfacl_output(text)
        assert groups[0].perms == "r-x"

    def test_empty_input(self) -> None:
        mask, groups = parse_getfacl_output("")
        assert mask is None
        assert groups == []

    def test_blank_lines_and_comments(self) -> None:
        text = "# header\n\ngroup:alice:rw-\n\n"
        _, groups = parse_getfacl_output(text)
        assert len(groups) == 1
        assert groups[0].name == "alice"

    def test_group_without_name_skipped(self) -> None:
        text = "group::rwx\n"
        _, groups = parse_getfacl_output(text)
        assert groups == []

    def test_no_colon_in_body_skipped(self) -> None:
        text = "group:nocolon\n"
        _, groups = parse_getfacl_output(text)
        assert groups == []

    def test_multiple_groups(self) -> None:
        text = "\n".join(f"group:team{n}:rw-" for n in range(10))
        _, groups = parse_getfacl_output(text)
        assert len(groups) == 10
        assert groups[-1].name == "team9"


# ===============================================================
# detect_project / save_rows / list_saves tests
# ===============================================================
class TestDetectProject:
    def test_pixi(self, tmp_path: Path) -> None:
        (tmp_path / "pixi.toml").write_text("[project]\nname='p'\n")
        assert detect_project(tmp_path) == ProjectKind.PIXI

    def test_uv(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='p'\n")
        assert detect_project(tmp_path) == ProjectKind.UV

    def test_pixi_wins_over_uv(self, tmp_path: Path) -> None:
        (tmp_path / "pixi.toml").write_text("[project]\nname='p'\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='p'\n")
        assert detect_project(tmp_path) == ProjectKind.PIXI

    def test_empty(self, tmp_path: Path) -> None:
        assert detect_project(tmp_path) is None

    def test_directory_with_other_files(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("hi")
        (tmp_path / "data.csv").write_text("x,y\n")
        assert detect_project(tmp_path) is None


class TestListSaves:
    def test_empty_dir(self, tmp_path: Path) -> None:
        saves = tmp_path / "saves"
        saves.mkdir()
        assert list_saves(saves) == []

    def test_non_existent_dir(self, tmp_path: Path) -> None:
        assert list_saves(tmp_path / "nonexistent") == []

    def test_with_saves(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        write_manifest(root / "mylab", "mylab")
        write_manifest(root / "demo", "demo", ProjectKind.UV)

        results = list_saves(root)
        assert len(results) == 2
        paths = [p.name for p, _ in results]  # sorted
        assert paths == ["demo", "mylab"]

    def test_skips_entries_without_manifest(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        (root / "orphan").mkdir(parents=True)
        write_manifest(root / "valid", "valid")
        results = list_saves(root)
        assert len(results) == 1
        assert results[0][1].name == "valid"

    def test_skips_files_at_top_level(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        root.mkdir(parents=True)
        (root / "not-a-dir").write_text("junk")
        assert list_saves(root) == []

    def test_sorted_order(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        for name in ("zebra", "alpha", "mike"):
            write_manifest(root / name, name)
        results = list_saves(root)
        names = [m.name for _, m in results]
        assert names == ["alpha", "mike", "zebra"]


class TestSaveRows:
    def test_no_saves(self, tmp_path: Path) -> None:
        assert save_rows(tmp_path / "nonexistent") == []

    def test_converts_to_dicts(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        write_manifest(root / "mylab", "mylab")
        write_manifest(root / "demo", "demo", ProjectKind.UV, full=True)

        rows = save_rows(root)
        assert len(rows) == 2
        assert rows[0]["name"] == "demo"
        assert rows[0]["kind"] == "uv"
        assert rows[0]["full"] == "true"
        assert rows[1]["name"] == "mylab"
        assert rows[1]["kind"] == "pixi"
        assert rows[1]["full"] == "false"
        assert "path" in rows[0]
        assert "saved_at" in rows[0]


# ===============================================================
# read_manifest / resolve_save_dir tests
# ===============================================================
class TestReadManifest:
    def test_reads_valid_manifest(self, tmp_path: Path) -> None:
        write_manifest(tmp_path / "mylab", "mylab")
        manifest = read_manifest(tmp_path / "mylab" / "manifest.json")
        assert manifest.name == "mylab"
        assert manifest.kind == ProjectKind.PIXI
        assert manifest.user == "testuser"
        assert manifest.full is False

    def test_reads_full_manifest(self, tmp_path: Path) -> None:
        write_manifest(tmp_path / "demo", "demo", ProjectKind.UV, full=True)
        manifest = read_manifest(tmp_path / "demo" / "manifest.json")
        assert manifest.name == "demo"
        assert manifest.kind == ProjectKind.UV
        assert manifest.full is True

    def test_non_existent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_manifest(tmp_path / "nonexistent" / "manifest.json")

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json")
        with pytest.raises(ValueError):  # json.JSONDecodeError
            read_manifest(path)

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.json"
        path.write_text("")
        with pytest.raises(ValueError):  # json.JSONDecodeError
            read_manifest(path)

    def test_valid_json_wrong_schema_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "wrong.json"
        path.write_text('{"not": "a manifest"}')
        with pytest.raises(Exception):  # pydantic.ValidationError
            read_manifest(path)


class TestResolveSaveDir:
    def test_by_name(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        write_manifest(root / "mylab", "mylab")
        result = resolve_save_dir("mylab", root, from_path=None)
        assert result == root / "mylab"

    def test_by_from_path(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        custom = tmp_path / "custom-save"
        write_manifest(custom, "custom")
        result = resolve_save_dir("custom", root, from_path=custom)
        assert result == custom

    def test_from_path_ignores_name(self, tmp_path: Path) -> None:
        """When from_path is given, save_root/name is not consulted."""
        root = tmp_path / "saves"
        custom = tmp_path / "other-place"
        write_manifest(custom, "other")
        # Even though "mylab" exists under root, from_path takes priority
        result = resolve_save_dir("mylab", root, from_path=custom)
        assert result == custom

    def test_name_not_found_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        root.mkdir()
        with pytest.raises(LabError, match="Save not found"):
            resolve_save_dir("nonexistent", root, from_path=None)

    def test_from_path_missing_manifest_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "saves"
        missing = tmp_path / "no-manifest"
        missing.mkdir()
        with pytest.raises(LabError, match="Save not found"):
            resolve_save_dir("irrelevant", root, from_path=missing)

    def test_from_parent_uses_named_child(self, tmp_path: Path) -> None:
        parent = tmp_path / "env-saves"
        named = parent / "mylab"
        named.mkdir(parents=True)
        (named / "manifest.json").write_text("{}")
        result = resolve_save_dir("mylab", tmp_path / "saves", from_path=parent)
        assert result == named

    def test_empty_save_root_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()
        with pytest.raises(LabError, match="Save not found"):
            resolve_save_dir("anything", root, from_path=None)


# ===============================================================
# _path_under_roots tests
# ===============================================================
class TestPathUnderRoots:
    def test_under_single_root(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        child = root / "sub" / "file"
        child.parent.mkdir(parents=True)
        child.write_text("x")
        assert _path_under_roots(child, root) is True

    def test_not_under_root(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        other = tmp_path / "other" / "file"
        other.parent.mkdir(parents=True)
        other.write_text("x")
        assert _path_under_roots(other, root) is False

    def test_multiple_roots(self, tmp_path: Path) -> None:
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r1.mkdir()
        r2.mkdir()
        child = r2 / "child"
        child.write_text("x")
        assert _path_under_roots(child, r1, r2) is True

    def test_non_existent_root_skipped(self, tmp_path: Path) -> None:
        nonexistent = Path("/no/such/path")
        child = tmp_path / "child"
        child.write_text("x")
        # root doesn't exist — skipped, so child is not under any root
        assert _path_under_roots(child, nonexistent) is False

    def test_empty_roots(self, tmp_path: Path) -> None:
        child = tmp_path / "child"
        child.write_text("x")
        assert _path_under_roots(child) is False

    def test_path_equals_root(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        assert _path_under_roots(root, root) is True


# ===============================================================
# _session_cache_path tests
# ===============================================================
class TestSessionCachePath:
    @pytest.fixture(autouse=True)
    def _isolate_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "_pure_home"
        home.mkdir(exist_ok=True)
        monkeypatch.setenv("HOME", str(home))

    def test_env_under_work_without_scratch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        work = tmp_path / "work"
        work.mkdir()
        cache = work / ".cache-usr" / "pip"
        cache.mkdir(parents=True)
        monkeypatch.setenv("PIP_CACHE_DIR", str(cache))

        result = _session_cache_path(
            "PIP_CACHE_DIR",
            default=work / "default-cache",
            work=work,
            scratch=None,
        )
        assert result == cache  # kept because under work

    def test_system_path_redirected_without_scratch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.setenv("PIXI_CACHE_DIR", "/usr/local/share/pixi/cache")

        default = work / ".cache-usr" / "pixi"
        result = _session_cache_path(
            "PIXI_CACHE_DIR",
            default=default,
            work=work,
            scratch=None,
        )
        assert result == default  # redirected from system path

    def test_env_under_scratch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        work = tmp_path / "work"
        scratch = tmp_path / "scratch"
        work.mkdir()
        scratch.mkdir()
        cache = scratch / ".cache-usr" / "pip"
        cache.mkdir(parents=True)
        monkeypatch.setenv("PIP_CACHE_DIR", str(cache))

        result = _session_cache_path(
            "PIP_CACHE_DIR",
            default=work / "default-cache",
            work=work,
            scratch=scratch,
        )
        assert result == cache  # kept because under scratch

    def test_env_under_work_with_scratch_present(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        work = tmp_path / "work"
        scratch = tmp_path / "scratch"
        work.mkdir()
        scratch.mkdir()
        cache = work / ".cache-usr" / "pip"
        cache.mkdir(parents=True)
        monkeypatch.setenv("PIP_CACHE_DIR", str(cache))

        result = _session_cache_path(
            "PIP_CACHE_DIR",
            default=work / "default-cache",
            work=work,
            scratch=scratch,
        )
        assert result == cache  # kept because under work (scratch also checked but work wins)

    def test_var_not_set_returns_default(self, tmp_path: Path) -> None:
        work = tmp_path / "work"
        work.mkdir()
        default = work / ".cache-usr" / "pip"
        # env var intentionally absent (monkeypatch not set)

        result = _session_cache_path(
            "PIP_CACHE_DIR",
            default=default,
            work=work,
            scratch=None,
        )
        assert result == default

    def test_system_path_redirected_with_scratch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        work = tmp_path / "work"
        scratch = tmp_path / "scratch"
        work.mkdir()
        scratch.mkdir()
        monkeypatch.setenv("MAMBA_PKGS_DIRS", "/usr/local/share/micromamba/pkgs")

        default = work / ".cache-usr" / "conda" / "pkgs"
        result = _session_cache_path(
            "MAMBA_PKGS_DIRS",
            default=default,
            work=work,
            scratch=scratch,
        )
        assert result == default  # redirected from system path even with scratch

    def test_home_path_redirected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        work = tmp_path / "work"
        work.mkdir()
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("UV_CACHE_DIR", str(home / ".cache" / "uv"))
        default = work / ".cache-usr" / "uv"
        result = _session_cache_path(
            "UV_CACHE_DIR",
            default=default,
            work=work,
            scratch=None,
        )
        assert result == default

    def test_var_set_to_empty_string_uses_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.setenv("PIP_CACHE_DIR", "")
        default = work / "default-cache"

        result = _session_cache_path(
            "PIP_CACHE_DIR",
            default=default,
            work=work,
            scratch=None,
        )
        assert result == default


# ===============================================================
# _session_runtime_path tests
# ===============================================================
class TestSessionRuntimePath:
    def test_env_under_scratch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        runtime_dir = scratch / ".runtime-usr" / "uv" / "python"
        runtime_dir.mkdir(parents=True)
        monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(runtime_dir))
        monkeypatch.setenv("CANFAR_LAB_RUNTIME_ROOT", str(scratch / ".runtime-usr"))

        result = _session_runtime_path(
            "UV_PYTHON_INSTALL_DIR",
            default=scratch / "default-runtime",
            scratch=scratch,
        )
        assert result == runtime_dir

    def test_env_under_runtime_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        uv_tool = runtime / "uv" / "tools"
        uv_tool.mkdir(parents=True)
        monkeypatch.setenv("UV_TOOL_DIR", str(uv_tool))
        monkeypatch.setenv("CANFAR_LAB_RUNTIME_ROOT", str(runtime))

        result = _session_runtime_path(
            "UV_TOOL_DIR",
            default=runtime / "default-tools",
            scratch=scratch,
        )
        assert result == uv_tool

    def test_env_not_under_any_root_returns_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", "/usr/local/share/uv/python")
        monkeypatch.setenv("CANFAR_LAB_RUNTIME_ROOT", str(tmp_path / "runtime"))

        default = scratch / "default-runtime" / "uv" / "python"
        result = _session_runtime_path(
            "UV_PYTHON_INSTALL_DIR",
            default=default,
            scratch=scratch,
        )
        assert result == default

    def test_var_not_set_returns_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)

        default = scratch / "default-tools"
        result = _session_runtime_path(
            "UV_TOOL_DIR",
            default=default,
            scratch=scratch,
        )
        assert result == default

    def test_var_set_to_empty_string_uses_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        monkeypatch.setenv("UV_TOOL_DIR", "")

        default = scratch / "default-tools"
        result = _session_runtime_path(
            "UV_TOOL_DIR",
            default=default,
            scratch=scratch,
        )
        assert result == default

    def test_no_scratch_with_runtime_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        mamba = runtime / "micromamba"
        mamba.mkdir(parents=True)
        monkeypatch.setenv("MAMBA_ROOT_PREFIX", str(mamba))
        monkeypatch.setenv("CANFAR_LAB_RUNTIME_ROOT", str(runtime))

        result = _session_runtime_path(
            "MAMBA_ROOT_PREFIX",
            default=runtime / "default-mamba",
            scratch=None,
        )
        assert result == mamba

    def test_no_scratch_no_runtime_root_redirects(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MAMBA_ROOT_PREFIX", "/usr/local/share/micromamba")
        monkeypatch.delenv("CANFAR_LAB_RUNTIME_ROOT", raising=False)

        default = Path("/tmp/default-mamba")
        result = _session_runtime_path(
            "MAMBA_ROOT_PREFIX",
            default=default,
            scratch=None,
        )
        assert result == default
