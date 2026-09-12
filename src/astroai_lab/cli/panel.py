"""`astroai panel` (alias `astroai review`): AstroAI Panel."""

from __future__ import annotations

import os
import shutil
from typing import Annotated, Any

import typer

from astroai_lab import ui
from astroai_lab.cli.context import merge_opts
from astroai_lab.errors import LabError

panel_app = typer.Typer(
    help=(
        "AstroAI Panel — chaired eight-persona review "
        "(headless everywhere, web where reachable).\n\n"
        "  run / status / web     execute and inspect panels\n"
        "  doctor / models / routers   catalog + credential health"
    ),
)


@panel_app.callback(invoke_without_command=True)
def panel_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    opts = merge_opts(ctx)
    from astroai_lab.agent.support import brand_logo_path

    logo = brand_logo_path()
    if opts.json:
        ui.print_json(
            {
                "product": "AstroAI Panel",
                "help": "astroai panel --help",
                "try": ["run", "web", "doctor", "models", "routers"],
                "logo": str(logo) if logo else None,
            }
        )
        return
    ui.print_hint("AstroAI Panel — chaired eight-persona review.")
    if logo:
        ui.print_hint(f"  Logo: {logo}")
    ui.print_hint('  astroai panel run <repo> "C1: …" [slug]')
    ui.print_hint("  astroai panel web <repo> --port 3080")
    ui.print_hint("  astroai panel doctor | models | routers")


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
    """Run a headless AstroAI Panel on REPO for CLAIMS (or --web where reachable)."""
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
    note = result.get("fallback_note")
    if note:
        ui.print_warn(str(note))
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


@panel_app.command("doctor")
def panel_doctor(ctx: typer.Context) -> None:
    """dsh version, active route/keys, pin sanity vs support catalog."""
    from astroai_lab.agent import review_bench as _rb
    from astroai_lab.agent.support import brand_logo_path, load_support, routers_status

    opts = merge_opts(ctx)
    catalog = load_support()
    keys = _rb.discover_dsh_keys()
    route = _rb.ensure_dsh_settings(dry_run=True)
    pins = _rb.extract_preset_role_models()
    expected = _rb.panel_role_pins(route or "opencode-go")
    unknown: list[str] = []
    if route:
        router = catalog.router_by_id(route)
        allowed = set(router.panel_models) if router else set()
        for role, model in pins.items():
            if allowed and model not in allowed:
                unknown.append(f"{role}:{model}")
    dsh_bin = shutil.which("dsh")
    payload: dict[str, Any] = {
        "product": "AstroAI Panel",
        "logo": str(brand_logo_path()) if brand_logo_path() else None,
        "dsh_on_path": bool(dsh_bin),
        "dsh_bin": dsh_bin,
        "dsh_version_pin": _rb.DSH_VERSION,
        "active_route": route,
        "keys_present": sorted(keys),
        "routers": routers_status(keys_present=keys),
        "preset_pins": pins,
        "catalog_pins_for_route": expected,
        "unknown_preset_ids": unknown,
        "headless_tip": (
            "Prefer deepseek-official for headless; OpenCode Go may need a "
            "session header (panel run auto-falls back)."
        ),
    }
    if opts.json:
        ui.print_json(payload)
        return
    ui.print_hint("AstroAI Panel doctor")
    if payload["logo"]:
        ui.print_hint(f"  Logo: {payload['logo']}")
    ui.print_hint(f"  dsh: {'on PATH' if dsh_bin else 'not on PATH'} (pin {_rb.DSH_VERSION})")
    ui.print_hint(f"  Active route: {route or '(none)'}")
    ui.print_hint(f"  Keys present: {', '.join(sorted(keys)) or '(none)'}")
    if unknown:
        ui.print_warn(f"  Preset models not in catalog for {route}: {', '.join(unknown)}")
    else:
        ui.print_ok("  Preset pins look consistent with the active router catalog")
    ui.print_hint(f"  Tip: {payload['headless_tip']}")
    ui.print_hint("  More: astroai panel models | routers")


@panel_app.command("models")
def panel_models(ctx: typer.Context) -> None:
    """Role → pinned model for the active router; flag unknown IDs."""
    from astroai_lab.agent import review_bench as _rb
    from astroai_lab.agent.support import load_support

    opts = merge_opts(ctx)
    catalog = load_support()
    keys = _rb.discover_dsh_keys()
    route = _rb.ensure_dsh_settings(dry_run=True) or "opencode-go"
    pins = _rb.extract_preset_role_models()
    catalog_pins = _rb.panel_role_pins(route)
    router = catalog.router_by_id(route)
    allowed = set(router.panel_models) if router else set()
    rows: list[dict[str, Any]] = []
    for role in catalog.panel_roles:
        preset = pins.get(role)
        want = catalog_pins.get(role)
        rows.append(
            {
                "role": role,
                "preset": preset,
                "catalog": want,
                "unknown": bool(preset and allowed and preset not in allowed),
            }
        )
    payload = {
        "route": route,
        "key_present": any(catalog.key_to_route().get(k, (None, None))[0] == route for k in keys),
        "panel_default": router.panel_default if router else None,
        "roles": rows,
    }
    if opts.json:
        ui.print_json(payload)
        return
    ui.print_hint(f"AstroAI Panel models (router: {route})")
    ui.print_hint("  Role                 Preset                         Catalog")
    ui.print_hint("  ───────────────────  ─────────────────────────────  ────────────────")
    for row in rows:
        flag = " !" if row["unknown"] else ""
        ui.print_hint(
            f"  {row['role']:<19}  {(row['preset'] or '-'):<29}  {(row['catalog'] or '-')}{flag}"
        )
    if any(r["unknown"] for r in rows):
        ui.print_warn("  ! = preset id not listed for this router in support.yaml")


@panel_app.command("routers")
def panel_routers(ctx: typer.Context) -> None:
    """Supported routers from support.yaml + which keys are present."""
    from astroai_lab.agent import review_bench as _rb
    from astroai_lab.agent.support import routers_status

    opts = merge_opts(ctx)
    keys = _rb.discover_dsh_keys()
    rows = routers_status(keys_present=keys)
    if opts.json:
        ui.print_json({"routers": rows})
        return
    ui.print_hint("AstroAI Panel routers (preference order)")
    ui.print_hint("  Id                  Key                   Present  Default")
    ui.print_hint("  ──────────────────  ────────────────────  ───────  ────────────")
    for row in rows:
        present = "✓" if row["key_present"] else "-"
        ui.print_hint(f"  {row['id']:<18}  {row['key']:<20}  {present:<7}  {row['panel_default']}")
        if row.get("notes"):
            ui.print_hint(f"    {row['notes']}")


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
