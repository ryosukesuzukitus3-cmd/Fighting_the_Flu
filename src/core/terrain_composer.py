"""Shared terrain-composer names and asset catalog resolution.

This module intentionally stays independent from pygame so validation can inspect
composer catalogs without loading the runtime renderer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_TERRAIN_COMPOSER_RENDERER = "terrain_composer"
LEGACY_TERRAIN_COMPOSER_RENDERER = "stage3_composer"
TERRAIN_COMPOSER_RENDERERS = frozenset(
    {
        CANONICAL_TERRAIN_COMPOSER_RENDERER,
        LEGACY_TERRAIN_COMPOSER_RENDERER,
    }
)

DEFAULT_COMPOSER_RECTS_PATH = Path("tools/stage3_terrain_rects.json")
DEFAULT_COMPOSER_MASK_DIR = Path("tools/stage3_terrain_alpha_masks")


def is_terrain_composer_renderer(value: object) -> bool:
    """Return whether *value* selects the canonical or legacy composer."""

    return isinstance(value, str) and value in TERRAIN_COMPOSER_RENDERERS


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def resolve_composer_paths(event: Mapping[str, Any]) -> tuple[Path, Path]:
    """Resolve composer rect and mask paths relative to the repository root."""

    rects_path = event.get("composer_rects", event.get("rects_path"))
    mask_dir = event.get("composer_mask_dir", event.get("mask_dir"))
    if event.get("renderer") == CANONICAL_TERRAIN_COMPOSER_RENDERER:
        if not rects_path or not mask_dir:
            raise ValueError(
                "terrain_composer requires composer_rects and composer_mask_dir"
            )
    rects_path = rects_path or DEFAULT_COMPOSER_RECTS_PATH
    mask_dir = mask_dir or DEFAULT_COMPOSER_MASK_DIR
    return _resolve_repo_path(rects_path), _resolve_repo_path(mask_dir)


@dataclass(frozen=True)
class ComposerCatalog:
    """JSON-only metadata from a terrain-composer rect catalog."""

    path: Path
    roles: frozenset[str]
    assets: frozenset[str]


@lru_cache(maxsize=None)
def _load_composer_catalog(path: Path) -> ComposerCatalog:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"composer catalog must contain an object: {path}")

    roles_data = data.get("roles", {})
    groups_data = data.get("groups", {})
    if not isinstance(roles_data, dict):
        raise ValueError(f"composer catalog roles must contain an object: {path}")
    if not isinstance(groups_data, dict):
        raise ValueError(f"composer catalog groups must contain an object: {path}")

    assets: set[str] = set()
    for group, group_data in groups_data.items():
        if not isinstance(group, str) or not isinstance(group_data, dict):
            continue
        rects = group_data.get("rects", [])
        if not isinstance(rects, list):
            continue
        assets.update(f"{group}:{index}" for index in range(1, len(rects) + 1))

    return ComposerCatalog(
        path=path,
        roles=frozenset(str(role) for role in roles_data),
        assets=frozenset(assets),
    )


def load_composer_catalog(
    path: str | Path = DEFAULT_COMPOSER_RECTS_PATH,
) -> ComposerCatalog:
    """Load and cache JSON-only composer catalog metadata."""

    return _load_composer_catalog(_resolve_repo_path(path))


@dataclass(frozen=True)
class TerrainMaterialCatalog:
    """Composer assets used to skin an individual rectangular terrain block."""

    rects_path: Path
    mask_dir: Path


TERRAIN_MATERIAL_CATALOGS: Mapping[str, TerrainMaterialCatalog] = {
    "clot": TerrainMaterialCatalog(
        rects_path=_resolve_repo_path("tools/stage1_terrain_rects.json"),
        mask_dir=_resolve_repo_path("tools/stage1_terrain_alpha_masks"),
    ),
    "data_block": TerrainMaterialCatalog(
        rects_path=_resolve_repo_path("tools/stage2_terrain_rects.json"),
        mask_dir=_resolve_repo_path("tools/stage2_terrain_alpha_masks"),
    ),
    "fortress_block": TerrainMaterialCatalog(
        rects_path=_resolve_repo_path(DEFAULT_COMPOSER_RECTS_PATH),
        mask_dir=_resolve_repo_path(DEFAULT_COMPOSER_MASK_DIR),
    ),
}


def terrain_material_catalog_for_kind(kind: object) -> TerrainMaterialCatalog | None:
    """Return the composer material catalog for a supported terrain kind."""

    return TERRAIN_MATERIAL_CATALOGS.get(kind) if isinstance(kind, str) else None
