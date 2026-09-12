"""AstroAI-supported routers, panel models, and recommended agents."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from astroai_lab.agent.bundle_path import bundle_root


@dataclass(frozen=True)
class Router:
    id: str
    key: str
    panel_default: str
    panel_models: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class SupportCatalog:
    routers: tuple[Router, ...]
    panel_roles: dict[str, dict[str, str]]
    recommended_agents: tuple[str, ...]
    panel_agents: tuple[str, ...]

    @property
    def dsh_keys(self) -> tuple[str, ...]:
        return tuple(r.key for r in self.routers)

    def key_to_route(self) -> dict[str, tuple[str, str]]:
        return {r.key: (r.id, r.panel_default) for r in self.routers}

    def router_by_id(self, router_id: str) -> Router | None:
        for router in self.routers:
            if router.id == router_id:
                return router
        return None

    def role_model(self, role: str, router_id: str) -> str | None:
        row = self.panel_roles.get(role) or {}
        if router_id in row:
            return row[router_id]
        router = self.router_by_id(router_id)
        return router.panel_default if router else None


def support_yaml_path() -> Path:
    return bundle_root() / "support.yaml"


@lru_cache
def load_support() -> SupportCatalog:
    path = support_yaml_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    routers: list[Router] = []
    for entry in raw.get("routers") or []:
        if not isinstance(entry, dict):
            continue
        routers.append(
            Router(
                id=str(entry["id"]),
                key=str(entry["key"]),
                panel_default=str(entry["panel_default"]),
                panel_models=tuple(str(m) for m in (entry.get("panel_models") or [])),
                notes=str(entry.get("notes") or ""),
            )
        )
    roles_raw = raw.get("panel_roles") or {}
    panel_roles: dict[str, dict[str, str]] = {}
    if isinstance(roles_raw, dict):
        for role, mapping in roles_raw.items():
            if isinstance(mapping, dict):
                panel_roles[str(role)] = {str(k): str(v) for k, v in mapping.items()}
    agents = raw.get("agents") or {}
    recommended = tuple(str(a) for a in (agents.get("recommended") or []))
    panel = tuple(str(a) for a in (agents.get("panel") or []))
    return SupportCatalog(
        routers=tuple(routers),
        panel_roles=panel_roles,
        recommended_agents=recommended,
        panel_agents=panel,
    )


def brand_logo_path() -> Path | None:
    """Vendored AstroAI logo, if present."""
    data = Path(__file__).resolve().parent.parent / "data" / "brand" / "astroai-logo.png"
    return data if data.is_file() else None


def routers_status(*, keys_present: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Rows for ``panel routers`` / ``agent routers``."""
    cat = load_support()
    present = keys_present if keys_present is not None else {}
    rows: list[dict[str, Any]] = []
    for router in cat.routers:
        rows.append(
            {
                "id": router.id,
                "key": router.key,
                "key_present": router.key in present,
                "panel_default": router.panel_default,
                "panel_models": list(router.panel_models),
                "notes": router.notes,
            }
        )
    return rows


def clear_support_cache() -> None:
    load_support.cache_clear()
