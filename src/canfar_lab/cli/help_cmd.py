"""help command: aggregate of every command's --help output.

`canfar lab help` is the CLI equivalent of running `--help` on the app and
every subcommand, in registration order. `--command <path>` (or `-c`) shows a
single command's help; interactive terminals page the full dump through
`less` when available.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import NoReturn

import typer
from typer.main import get_command
from typer.testing import CliRunner

from canfar_lab import ui

# Why CliRunner instead of click.Context(cmd).get_help()?
# typer's rich format_help renders straight to a rich console, bypassing the
# click help formatter — so ctx.get_help() would return empty text. Invoking
# each command's own `--help` reuses typer's exact rendering.

# Page through less only when the full dump is long enough to matter.
_PAGER_MIN_LINES = 40


def _command_paths(app: typer.Typer) -> list[tuple[str, ...]]:
    """Invocation paths for the app and every subcommand (e.g. ("agent", "list"))."""
    root = get_command(app)
    paths: list[tuple[str, ...]] = [()]

    def walk(cmd: object, prefix: tuple[str, ...]) -> None:
        # click Groups expose a `commands` dict; duck-type to stay independent
        # of click's import path (vendored by typer).
        commands = getattr(cmd, "commands", None)
        if not commands:
            return
        for name, sub in commands.items():
            path = prefix + (name,)
            paths.append(path)
            walk(sub, path)

    walk(root, ())
    return paths


def _render(app: typer.Typer, path: tuple[str, ...]) -> str | None:
    runner = CliRunner()
    result = runner.invoke(app, [*path, "--help"])
    if result.exit_code != 0:
        return None
    return result.output.rstrip()


def _unknown_path_error(
    app: typer.Typer, command_path: str, *, json_output: bool = False
) -> NoReturn:
    """Report an unknown command path and exit 1 (text or machine-readable).

    Interactive/stderr mode prints a human hint with the available top-level
    commands; `json_output` emits a structured `{"error": ...}` object so the
    machine contract stays machine-readable even on failure.
    """
    available = ", ".join(top_level_commands(app))
    message = (
        f"Unknown command path: `{command_path}`. "
        f"Top-level commands: {available} (use `canfar lab help` to list all)."
    )
    if json_output:
        ui.print_json({"error": message})
    else:
        typer.echo(message, err=True)
    raise typer.Exit(code=1)


def top_level_commands(app: typer.Typer) -> list[str]:
    """Top-level command names (for error hints), sorted, excluding hidden aliases."""
    root = get_command(app)
    commands = getattr(root, "commands", {})
    return sorted(name for name, sub in commands.items() if not getattr(sub, "hidden", False))


def _visible_command_paths(app: typer.Typer) -> list[tuple[str, ...]]:
    """All registered command paths, excluding hidden commands."""
    root = get_command(app)
    paths: list[tuple[str, ...]] = []

    def walk(cmd: object, prefix: tuple[str, ...]) -> None:
        commands = getattr(cmd, "commands", None)
        if not commands:
            return
        for name, sub in commands.items():
            if getattr(sub, "hidden", False):
                continue
            path = prefix + (name,)
            paths.append(path)
            walk(sub, path)

    walk(root, ())
    return paths


def command_path_completer(app: typer.Typer) -> Callable[[object, str], list[str]]:
    """Typer autocompletion callable offering command paths for `help -c`.

    The returned callable matches typer's `autocompletion` signature
    (ctx, incomplete) -> list[str]; typer wraps plain strings into completion
    items. Nested paths like "agent list" are offered as a single value, so
    quoting works in bash and zsh.
    """

    def _complete(ctx, incomplete: str) -> list[str]:
        incomplete = incomplete or ""
        return [
            " ".join(path)
            for path in _visible_command_paths(app)
            if " ".join(path).startswith(incomplete)
        ]

    return _complete


def _emit(text: str) -> None:
    """Print help text, paging through less on interactive terminals."""
    if sys.stdout.isatty() and shutil.which("less") and len(text.splitlines()) >= _PAGER_MIN_LINES:
        subprocess.run(["less", "-R"], input=text, text=True, check=False)
        return
    typer.echo(text)


def print_all_help(app: typer.Typer) -> None:
    """Print --help for the app and every subcommand, in registration order."""
    chunks: list[str] = []
    for path in _command_paths(app):
        rendered = _render(app, path)
        if rendered is None:
            continue
        chunks.append(rendered)
    _emit("\n\n".join(chunks))


def _find_command(app: typer.Typer, path: tuple[str, ...]):
    """Resolve a command path to its click command object, or None."""
    root = get_command(app)
    cmd = root
    for part in path:
        commands = getattr(cmd, "commands", None)
        if not commands or part not in commands:
            return None
        cmd = commands[part]
    return cmd


def _command_help_dict(cmd: object) -> dict:
    """Structured help for one command object (path not included)."""
    entry: dict = {
        "help": (getattr(cmd, "short_help", None) or getattr(cmd, "help", None) or ""),
        "hidden": bool(getattr(cmd, "hidden", False)),
    }
    params = []
    for p in getattr(cmd, "params", []) or []:
        params.append(
            {
                "name": getattr(p, "name", None),
                "opts": list(getattr(p, "opts", []) or []),
                "help": getattr(p, "help", None) or "",
                "hidden": bool(getattr(p, "hidden", False)),
            }
        )
    entry["options"] = params
    subcommands = getattr(cmd, "commands", None)
    # Always emit the key (empty for leaf commands) so the schema is stable.
    entry["subcommands"] = [
        name for name, sub in (subcommands or {}).items() if not getattr(sub, "hidden", False)
    ]
    return entry


def command_inventory(app: typer.Typer) -> list[dict]:
    """Machine-readable inventory of every visible command path."""
    out: list[dict] = []
    for path in _visible_command_paths(app):
        cmd = _find_command(app, path)
        if cmd is None:
            continue
        entry = _command_help_dict(cmd)
        entry["path"] = " ".join(path)
        out.append(entry)
    # Stable machine contract: sorted by path, not registration order.
    out.sort(key=lambda e: e["path"])
    return out


def command_help_json(app: typer.Typer, command_path: str) -> dict | None:
    """Structured help for one command path, or None if it does not exist."""
    path = tuple(command_path.split())
    if not path or path not in _command_paths(app):
        return None
    cmd = _find_command(app, path)
    if cmd is None:
        return None
    entry = _command_help_dict(cmd)
    entry["path"] = " ".join(path)
    return entry


def print_one_help(app: typer.Typer, command_path: str) -> None:
    """Print --help for a single command path, raising if it does not exist."""
    path = tuple(command_path.split())
    # Guard empty paths: () is always in _command_paths (the root), but an
    # empty -c value is a user mistake, not a request for root help.
    if not command_path.strip() or path not in _command_paths(app):
        _unknown_path_error(app, command_path)
    rendered = _render(app, path)
    if rendered is None:
        typer.echo(f"Could not render help for `{command_path}`.", err=True)
        raise typer.Exit(code=1)
    _emit(rendered)


def help_cmd_body(
    app: typer.Typer, command: str | None = None, *, json_output: bool = False
) -> None:
    """Shared body for `help`."""
    if json_output:
        if command is None:
            ui.print_json({"commands": command_inventory(app)})
        else:
            entry = command_help_json(app, command)
            if entry is None:
                _unknown_path_error(app, command, json_output=True)
            ui.print_json(entry)
        return
    if command is None:
        print_all_help(app)
    else:
        print_one_help(app, command)
