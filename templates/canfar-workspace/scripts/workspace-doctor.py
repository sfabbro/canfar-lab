#!/usr/bin/env python3
"""Read-only consistency checks for the agent workspace.

This deliberately uses only the standard library. It reports findings and never
changes repositories, agent configuration, or the registry.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "workspace.toml"
ALLOWED_CLASSES = {
    "owned_product",
    "platform",
    "personal",
    "paper",
    "third_party",
    "scratch",
}
ALLOWED_LIFECYCLES = {"active", "on_demand", "quarantine", "archived"}
ALLOWED_WORKFLOWS = {"pixi", "uv", "latex", "canfar", "generic", "none"}
CANONICAL_ROOTS = {"astroai", "opencadc", "sfabbro", "overleaf"}
KNOWN_ROOTS = CANONICAL_ROOTS | {"clones", "local", "worktrees", "archive"}
REQUIRED_REPOSITORY_FIELDS = {
    "path",
    "class",
    "lifecycle",
    "workflow",
    "remote_policy",
}
SKILL_LINKS = (
    Path.home() / ".codex/skills/repo-router",
    Path.home() / ".cursor/skills/repo-router",
    Path.home() / ".config/opencode/skills/repo-router",
    Path.home() / ".pi/agent/skills/repo-router",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None


def add(
    findings: list[Finding],
    severity: str,
    code: str,
    message: str,
    path: Path | str | None = None,
) -> None:
    findings.append(
        Finding(
            severity=severity,
            code=code,
            message=message,
            path=os.fspath(path) if path is not None else None,
        )
    )


def load_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError("registry root must be a TOML table")
    return data


def git_root(path: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return Path(output).resolve() if output else None


def is_dirty(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(path), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


def local_instruction(path: Path) -> Path | None:
    for candidate in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        instruction = path / candidate
        if instruction.is_file():
            return instruction
    return None


def validate_registry(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if data.get("version") != 1:
        add(findings, "error", "registry-version", "registry version must be 1")

    for key in ("workspace_root", "agent_home", "worktrees_root", "archive_root"):
        if not isinstance(data.get(key), str) or not data[key]:
            add(findings, "error", "registry-field", f"missing string field: {key}")

    repositories = data.get("repositories")
    if not isinstance(repositories, dict):
        add(findings, "error", "registry-repositories", "repositories must be a TOML table")
        return findings

    resolved_paths: dict[Path, str] = {}
    entries: dict[str, tuple[dict[str, Any], Path]] = {}

    for identity, entry in repositories.items():
        label = str(identity)
        if not isinstance(entry, dict):
            add(findings, "error", "repository-entry", "repository entry must be a table", label)
            continue

        missing = REQUIRED_REPOSITORY_FIELDS - entry.keys()
        if missing:
            add(
                findings,
                "error",
                "repository-fields",
                f"missing fields: {', '.join(sorted(missing))}",
                label,
            )
            continue

        path_value = entry["path"]
        if not isinstance(path_value, str) or not path_value:
            add(findings, "error", "repository-path", "path must be a non-empty string", label)
            continue
        path = Path(path_value)
        if path.is_absolute():
            add(findings, "error", "absolute-path", "repository paths must be relative", label)
            continue

        resolved = (ROOT / path).resolve()
        entries[label] = (entry, resolved)
        lifecycle = entry["lifecycle"]
        class_name = entry["class"]
        workflow = entry["workflow"]

        if class_name not in ALLOWED_CLASSES:
            add(findings, "error", "repository-class", f"unknown class: {class_name}", label)
        if lifecycle not in ALLOWED_LIFECYCLES:
            add(findings, "error", "repository-lifecycle", f"unknown lifecycle: {lifecycle}", label)
        if workflow not in ALLOWED_WORKFLOWS:
            add(findings, "error", "repository-workflow", f"unknown workflow: {workflow}", label)

        top_level = path.parts[0] if path.parts else ""
        if top_level not in KNOWN_ROOTS:
            add(
                findings,
                "error" if lifecycle == "active" else "warning",
                "stale-path",
                "path is outside the owner/lifecycle roots",
                label,
            )
        if lifecycle == "active" and top_level not in CANONICAL_ROOTS:
            add(
                findings,
                "error",
                "active-noncanonical",
                "active repositories must live under astroai, opencadc, sfabbro, or overleaf",
                label,
            )

        if not resolved.is_dir():
            add(findings, "error", "missing-path", "registered path does not exist", resolved)
            continue

        if lifecycle == "active":
            previous = resolved_paths.get(resolved)
            if previous is not None:
                add(
                    findings,
                    "error",
                    "duplicate-active-path",
                    f"same active path is registered as {previous}",
                    label,
                )
            else:
                resolved_paths[resolved] = label

        if git_root(resolved) is None:
            add(findings, "error", "not-git", "registered checkout is not a valid Git repository", resolved)
        elif lifecycle == "active" and class_name in {"owned_product", "platform", "personal"}:
            if local_instruction(resolved) is None:
                add(
                    findings,
                    "warning",
                    "missing-local-instructions",
                    "no repository-local AGENTS.md, CLAUDE.md, or GEMINI.md; workspace instructions are the fallback",
                    resolved,
                )

        harness_config = entry.get("harness_config")
        if harness_config is not None:
            if not isinstance(harness_config, str):
                add(findings, "error", "harness-path", "harness_config must be a string", label)
            else:
                config_path = (ROOT / harness_config).resolve()
                try:
                    with config_path.open(encoding="utf-8") as handle:
                        config = json.load(handle)
                except (OSError, json.JSONDecodeError) as exc:
                    add(findings, "error", "harness-config", f"cannot parse harness config: {exc}", config_path)
                else:
                    if not isinstance(config, dict):
                        add(findings, "error", "harness-config", "harness config must be a JSON object", config_path)

        duplicate_of = entry.get("duplicate_of")
        if duplicate_of is not None and duplicate_of not in repositories:
            add(
                findings,
                "error",
                "duplicate-target",
                f"duplicate_of references unknown repository: {duplicate_of}",
                label,
            )

        nested_under = entry.get("nested_under")
        if nested_under is not None:
            parent = entries.get(str(nested_under))
            if parent is None:
                add(
                    findings,
                    "error",
                    "nested-target",
                    f"nested_under references unknown repository: {nested_under}",
                    label,
                )
            elif not resolved.is_relative_to(parent[1]):
                add(
                    findings,
                    "error",
                    "nested-path",
                    "nested repository is not below nested_under",
                    label,
                )

        if lifecycle == "active" and is_dirty(resolved):
            add(findings, "info", "dirty-checkout", "tracked or untracked changes present; no changes made", resolved)

    agent_home = data.get("agent_home")
    if isinstance(agent_home, str):
        expected = (ROOT / agent_home).resolve()
        actual_link = Path.home() / ".agent-home"
        if not actual_link.is_symlink():
            add(findings, "error", "agent-home-link", "~/.agent-home is not a symlink", actual_link)
        elif actual_link.resolve() != expected:
            add(
                findings,
                "error",
                "agent-home-link",
                f"~/.agent-home resolves to {actual_link.resolve()}, expected {expected}",
                actual_link,
            )

    for link in SKILL_LINKS:
        if not link.is_dir():
            add(findings, "error", "skill-link", "repo-router skill link is missing or broken", link)

    return findings


def render(findings: list[Finding], as_json: bool) -> int:
    errors = sum(f.severity == "error" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    infos = sum(f.severity == "info" for f in findings)
    if as_json:
        print(
            json.dumps(
                {
                    "workspace": os.fspath(ROOT),
                    "registry": os.fspath(REGISTRY_PATH),
                    "summary": {"errors": errors, "warnings": warnings, "info": infos},
                    "findings": [asdict(f) for f in findings],
                },
                indent=2,
            )
        )
    else:
        if not findings:
            print("workspace doctor: OK")
        else:
            for finding in findings:
                location = f" [{finding.path}]" if finding.path else ""
                print(f"{finding.severity.upper():7} {finding.code}: {finding.message}{location}")
            print(f"workspace doctor: {errors} error(s), {warnings} warning(s), {infos} info")
    return 2 if errors and any(f.code.startswith("registry-") for f in findings) else (1 if errors or warnings else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        data = load_registry()
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        if args.as_json:
            print(json.dumps({"workspace": os.fspath(ROOT), "registry": os.fspath(REGISTRY_PATH), "error": str(exc)}))
        else:
            print(f"workspace doctor: registry error: {exc}", file=sys.stderr)
        return 2
    return render(validate_registry(data), args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())
