"""OpenCode config semantic checks and repairs.

OpenCode's schema allows top-level ``lsp`` / ``formatter`` to be a boolean, but
per-server / per-formatter entries must be objects — not bare ``true``/``false``.
Lab historically shipped ``"pyright": true`` in the bundled opencode.json, which
OpenCode rejects as:

  Expected { readonly "disabled": true, ... } | object, got true lsp.pyright
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _normalize_named_map(
    section: str,
    value: Any,
) -> tuple[Any, list[str]]:
    """Coerce a boolean-or-object map section (``lsp`` / ``formatter``).

    Returns ``(new_value, change_messages)``. Booleans at the top level are kept.
    Bare ``true`` entries are dropped (built-ins stay enabled via object/true
    form). Bare ``false`` becomes ``{"disabled": true}``.
    """
    if isinstance(value, bool) or value is None:
        return value, []
    if not isinstance(value, dict):
        return True, [f"{section}: non-object {type(value).__name__} → true"]

    changes: list[str] = []
    out: dict[str, Any] = {}
    dropped_true: list[str] = []
    for name, entry in value.items():
        key = f"{section}.{name}"
        if entry is True:
            dropped_true.append(name)
            changes.append(f"{key}: true → removed (booleans invalid; built-in stays available)")
            continue
        if entry is False:
            out[name] = {"disabled": True}
            changes.append(f"{key}: false → {{disabled: true}}")
            continue
        if isinstance(entry, dict):
            out[name] = entry
            continue
        changes.append(f"{key}: invalid {type(entry).__name__} removed")

    if dropped_true and not out:
        # All entries were enable-flags — enable built-ins the schema way.
        changes.append(f"{section}: set to true (enable built-ins)")
        return True, changes
    return out, changes


def opencode_config_issues(data: dict[str, Any]) -> list[str]:
    """Human-readable schema issues for a parsed OpenCode config object."""
    issues: list[str] = []
    for section in ("lsp", "formatter"):
        value = data.get(section)
        if not isinstance(value, dict):
            continue
        for name, entry in value.items():
            if isinstance(entry, bool):
                issues.append(
                    f"OpenCode {section}.{name} is {str(entry).lower()} "
                    f"(expected object — e.g. {{disabled: true}} or command config)"
                )
            elif not isinstance(entry, dict):
                issues.append(
                    f"OpenCode {section}.{name} has invalid type "
                    f"{type(entry).__name__} (expected object)"
                )
    return issues


def sanitize_opencode_config(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return a schema-safer copy of ``data`` plus change descriptions."""
    out = deepcopy(data)
    changes: list[str] = []
    for section in ("lsp", "formatter"):
        if section not in out:
            continue
        new_val, section_changes = _normalize_named_map(section, out[section])
        if section_changes:
            out[section] = new_val
            changes.extend(section_changes)
    return out, changes
