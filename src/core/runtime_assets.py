"""Build the packaged data manifest from authored stages and sound aliases.

This module deliberately has no pygame imports, so packaging can validate files
before building an executable. Paths retain their repository-relative layout.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.story.aliases import SE
from src.core.terrain_composer import (
    CANONICAL_TERRAIN_COMPOSER_RENDERER,
    DEFAULT_COMPOSER_MASK_DIR,
    DEFAULT_COMPOSER_RECTS_PATH,
    is_terrain_composer_renderer,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[2]


def _local_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"runtime resource must be relative: {value}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"runtime resource escapes project root: {value}")
    return path


def _composer_references(value):
    if isinstance(value, dict):
        # Use the runtime resolver's field names, including older authored data.
        if is_terrain_composer_renderer(value.get("renderer")):
            rects = value.get("composer_rects", value.get("rects_path"))
            masks = value.get("composer_mask_dir", value.get("mask_dir"))
            if value.get("renderer") == CANONICAL_TERRAIN_COMPOSER_RENDERER and (not rects or not masks):
                raise ValueError("terrain_composer requires composer_rects and composer_mask_dir")
            yield rects or str(DEFAULT_COMPOSER_RECTS_PATH), False
            yield masks or str(DEFAULT_COMPOSER_MASK_DIR), True
        for child in value.values():
            yield from _composer_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _composer_references(child)


def terrain_resource_paths(root: Path = RUNTIME_ROOT) -> tuple[Path, ...]:
    """Return required terrain catalogs/mask folders from every stage JSON."""
    root = root.resolve()
    stages = sorted((root / "data" / "stages").glob("stage*.json"))
    if not stages:
        raise FileNotFoundError(f"no stage JSON files under {root / 'data' / 'stages'}")
    paths: set[Path] = set()
    for stage in stages:
        for value, directory in _composer_references(json.loads(stage.read_text(encoding="utf-8"))):
            if not isinstance(value, str) or not value:
                raise ValueError(f"invalid terrain resource in {stage.name}: {value!r}")
            path = _local_path(root, value)
            if not (path.is_dir() if directory else path.is_file()):
                raise FileNotFoundError(f"{stage.name}: missing terrain resource {value}")
            paths.add(path)
    return tuple(sorted(paths))


def runtime_data_files(root: Path = RUNTIME_ROOT) -> tuple[Path, ...]:
    """List data files, excluding unselected candidate art and sound effects."""
    root = root.resolve()
    assets = root / "assets"
    if not assets.is_dir():
        raise FileNotFoundError(f"missing assets directory: {assets}")
    selected_sounds = {_local_path(root, f"assets/{path}") for path in SE.values() if path}
    for path in selected_sounds:
        if not path.is_file():
            raise FileNotFoundError(f"missing aliased sound: {path.relative_to(root)}")
    files = set((root / "data" / "stages").glob("stage*.json"))
    for path in assets.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(assets)
        if relative.parts[:2] == ("graphic", "candidates"):
            continue
        if relative.parts[:3] == ("music", "se", "candidates") and path not in selected_sounds:
            continue
        files.add(path)
    for path in terrain_resource_paths(root):
        if path.is_dir():
            files.update(item for item in path.rglob("*") if item.is_file())
        else:
            files.add(path)
    return tuple(sorted(files))


def pyinstaller_datas(root: Path = RUNTIME_ROOT) -> list[tuple[str, str]]:
    root = root.resolve()
    return [(str(path), path.relative_to(root).parent.as_posix()) for path in runtime_data_files(root)]
