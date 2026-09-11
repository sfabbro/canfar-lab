"""`astroai panel` (alias `astroai review`): review-bench panels everywhere."""

from __future__ import annotations

import os
from typing import Annotated

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.errors import LabError

panel_app = typer.Typer(
    help="Run the review-bench panel (headless everywhere, web where reachable)."
)


@panel_app.command("run")
def panel_run(
    ctx: typer.Context,
    repo: Annotated[str | None, typer.Argument(help="Repo checkout under review.")] = None,
    claims: Annotated[str | None, typer.Argument(help="C1: ...; C2: ... (falsifiable claims).")] = (
        None
    ),
    slug: Annotated[str, typer.Argument(help="Panel slug.")] = "review",
    web: Annotated[bool, typer.Option("--web", help="Serve the web UI (laptop only).")] = False,
    port: Annotated[int, typer.Option("--port", help="Web UI port.")] = 3080,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print plan without executing.")] = (
        False
    ),
) -> None:
    """Run a headless review panel on REPO for CLAIMS (or --web where reachable)."""
    from astroai_lab import panel as _panel

    opts = merge_opts(ctx, dry_run=dry_run)
    if web:
        _panel_web(repo, port, opts.dry_run)
        return
    if not claims:
        ui.print_error('panel run needs CLAIMS, e.g. "C1: ...; C2: ..."')
        raise typer.Exit(1)
    try:
        result = _panel.run_panel(repo, claims, slug, dry_run=opts.dry_run)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.dry_run or opts.json:
        ui.print_json(result)
        return
    ui.print_ok(f"Panel {result['panel_id']} in {result['repo']} ({result['route']})")


@panel_app.command("status")
def panel_status_cmd(
    ctx: typer.Context,
    target: Annotated[str, typer.Argument(help="Panel dir.")] = "",
) -> None:
    """Print the verdict table from a finished panel report."""
    from astroai_lab import panel as _panel

    opts = merge_opts(ctx)
    if not target:
        ui.print_error("panel status needs a panel dir, e.g. panel/2026-09-11-smoke")
        raise typer.Exit(1)
    try:
        table = _panel.panel_status(target)
    except LabError as exc:
        ui.print_error(str(exc))
        raise typer.Exit(1) from exc
    if opts.json:
        ui.print_json({"panel": target, "verdicts": table})
    else:
        typer.echo(table)


@panel_app.command("web")
def panel_web(
    ctx: typer.Context,
    repo: Annotated[str | None, typer.Argument(help="Repo checkout to serve.")] = None,
    port: Annotated[int, typer.Option("--port", help="Web UI port.")] = 3080,
) -> None:
    """Serve the dsh web UI for REPO (laptop; warns on Skaha sessions)."""
    opts = merge_opts(ctx)
    _panel_web(repo, port, opts.dry_run)


def _on_skaha() -> bool:
    names = {key.upper() for key in os.environ}
    return "SKAHA_SESSIONID" in names or "SKAHA_HOSTNAME" in names


def _panel_web(repo: str | None, port: int, dry_run: bool) -> None:
    from astroai_lab import panel as _panel
    from astroai_lab.utils.subprocess import run

    repo_path = _panel.resolve_repo(repo)
    patch = repo_path / ".dsh" / "cordis.patch.yml"
    if not patch.is_file():
        _panel.scaffold_repo_dsh(repo_path)
    if _on_skaha():
        ui.print_warn(
            "Web UI is not reachable behind /proxy on a Skaha contributed "
            "session — use `astroai panel run` instead."
        )
        if dry_run:
            ui.print_json({"repo": str(repo_path), "web": False})
            return
        raise typer.Exit(2)
    cmd = ["npx", "-y", "@deepseek-ai/dsh", "--profile", "web"]
    if patch.is_file():
        cmd += ["--patch", str(patch)]
    cmd += ["--no-open", "--port", str(port)]
    if dry_run:
        ui.print_json({"repo": str(repo_path), "cmd": cmd})
        return
    run(cmd, cwd=repo_path)
