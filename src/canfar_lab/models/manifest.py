from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ProjectKind(str, Enum):
    PIXI = "pixi"
    UV = "uv"


class EnvManifest(BaseModel):
    name: str
    kind: ProjectKind
    saved_at: str
    saved_from: str
    user: str
    full: bool = False
