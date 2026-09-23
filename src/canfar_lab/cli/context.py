from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlobalOpts:
    json: bool = False
    yes: bool = False
    dry_run: bool = False
    quiet: bool = False


def get_opts(ctx) -> GlobalOpts:
    return ctx.obj if isinstance(ctx.obj, GlobalOpts) else GlobalOpts()


def merge_opts(
    ctx,
    *,
    json_output: bool = False,
    yes: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
) -> GlobalOpts:
    """Combine root callback flags with subcommand-local copies."""
    base = get_opts(ctx)
    return GlobalOpts(
        json=base.json or json_output,
        yes=base.yes or yes,
        dry_run=base.dry_run or dry_run,
        quiet=base.quiet or quiet,
    )
