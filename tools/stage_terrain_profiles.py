"""Shared stage terrain tooling profiles.

Stage-specific asset paths and preview positions live here so the designer,
preview, and reporting tools can select the same inputs without duplicating
defaults.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGE_ID = 3


@dataclass(frozen=True)
class StageTerrainProfile:
    stage_id: int
    stage_json: Path
    rects: Path
    mask_dir: Path
    background: Path
    terrain_kind: str
    label: str
    preview_camera_xs: tuple[float, ...]
    fallback_rects: Path | None = None
    fallback_mask_dir: Path | None = None
    organic_autofill: bool = False
    autofill_overlap: int = 0


_STAGE3_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
_STAGE3_MASK_DIR = ROOT / "tools" / "stage3_terrain_alpha_masks"

STAGE_TERRAIN_PROFILES: Mapping[int, StageTerrainProfile] = MappingProxyType(
    {
        1: StageTerrainProfile(
            stage_id=1,
            stage_json=ROOT / "data" / "stages" / "stage1.json",
            rects=ROOT / "tools" / "stage1_terrain_rects.json",
            mask_dir=ROOT / "tools" / "stage1_terrain_alpha_masks",
            background=ROOT / "assets" / "graphic" / "stage1_fever_corridor_bg.png",
            terrain_kind="clot",
            label="Stage1",
            preview_camera_xs=(0, 1600, 3200, 4800, 6400, 8000),
            organic_autofill=True,
            autofill_overlap=24,
        ),
        2: StageTerrainProfile(
            stage_id=2,
            stage_json=ROOT / "data" / "stages" / "stage2.json",
            rects=ROOT / "tools" / "stage2_terrain_rects.json",
            mask_dir=ROOT / "tools" / "stage2_terrain_alpha_masks",
            background=ROOT / "assets" / "graphic" / "stage2_cyber_static_bg.png",
            terrain_kind="data_block",
            label="Stage2",
            preview_camera_xs=(0, 1600, 3200, 4800, 6400, 8000),
            fallback_rects=_STAGE3_RECTS,
            fallback_mask_dir=_STAGE3_MASK_DIR,
        ),
        3: StageTerrainProfile(
            stage_id=3,
            stage_json=ROOT / "data" / "stages" / "stage3.json",
            rects=_STAGE3_RECTS,
            mask_dir=_STAGE3_MASK_DIR,
            background=ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png",
            terrain_kind="fortress_block",
            label="Stage3",
            preview_camera_xs=(0, 2200, 4400, 6600, 8800, 10800),
        ),
    }
)


def stage_id_from_json(path: str | Path) -> int:
    """Read a stage id from JSON, raising a user-facing error when invalid."""

    stage_path = Path(path)
    try:
        data = json.loads(stage_path.read_text(encoding="utf-8"))
        return int(data["stage_id"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"cannot determine stage_id from {stage_path}: {exc}") from exc


def resolve_stage_terrain_profile(
    *,
    stage_id: int | None = None,
    stage_json: str | Path | None = None,
) -> StageTerrainProfile:
    """Resolve a profile without silently substituting another stage."""

    inferred_id = stage_id_from_json(stage_json) if stage_json is not None else None
    if stage_id is not None and inferred_id is not None and stage_id != inferred_id:
        raise ValueError(
            f"--stage {stage_id} conflicts with stage_id {inferred_id} in {stage_json}"
        )
    selected_id = stage_id if stage_id is not None else inferred_id
    selected_id = DEFAULT_STAGE_ID if selected_id is None else selected_id
    try:
        return STAGE_TERRAIN_PROFILES[selected_id]
    except KeyError as exc:
        supported = ", ".join(str(value) for value in sorted(STAGE_TERRAIN_PROFILES))
        raise ValueError(
            f"stage {selected_id} has no terrain tooling profile; supported: {supported}"
        ) from exc
