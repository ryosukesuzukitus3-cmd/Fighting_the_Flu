"""Shared helpers for Stage3 terrain alpha mask files."""
from __future__ import annotations

import re
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASK_DIR = ROOT / "tools" / "stage3_terrain_alpha_masks"


def safe_group_name(group: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", group).strip("_") or "group"


def mask_filename(group: str, index: int, rect: pygame.Rect) -> str:
    safe = safe_group_name(group)
    return f"{safe}_{index + 1:02d}_x{rect.x}_y{rect.y}_w{rect.w}_h{rect.h}.png"


def mask_path(mask_dir: Path, group: str, index: int, rect: pygame.Rect) -> Path:
    return mask_dir / mask_filename(group, index, rect)
