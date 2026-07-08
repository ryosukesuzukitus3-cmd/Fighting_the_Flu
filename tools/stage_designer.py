"""Interactive stage layout designer for authored stage JSON.

The tool edits route shapes, terrain pieces, and world_events directly while
keeping stage JSON in a compact, reviewable layout.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH  # noqa: E402
from src.entities.stage3_composer_terrain import (  # noqa: E402
    Stage3ComposerLayout,
    build_stage3_composer_layout,
    build_stage3_piece_layout,
    draw_stage3_composer_layout,
    load_stage3_composer_pieces,
)
from src.entities.enemies.crawler import EnemyCrawler  # noqa: E402
from src.entities.enemies.debris import _rock_sprite  # noqa: E402
from src.entities.enemies.turret import EnemyTurret  # noqa: E402
from src.entities.terrain import Terrain, make_terrain_segments_from_event  # noqa: E402

try:  # noqa: E402
    from stage3_alpha_mask_common import DEFAULT_MASK_DIR
except ModuleNotFoundError:  # noqa: E402
    from tools.stage3_alpha_mask_common import DEFAULT_MASK_DIR

DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"
DEFAULT_STAGE_ID = 3
STAGE2_STAGE = ROOT / "data" / "stages" / "stage2.json"
STAGE2_RECTS = ROOT / "tools" / "stage2_terrain_rects.json"
STAGE2_MASK_DIR = ROOT / "tools" / "stage2_terrain_alpha_masks"
STAGE2_BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage2_cyber_static_bg.png"

VIEW_W = SCREEN_WIDTH
VIEW_H = SCREEN_HEIGHT
TOOLBAR_H = 48
PALETTE_W = 430
INFO_W = 360
MIN_WINDOW_W = VIEW_W + PALETTE_W + INFO_W
MIN_WINDOW_H = VIEW_H + TOOLBAR_H
PALETTE_COLS = 3
MIN_ZOOM = 0.25
MAX_ZOOM = 2.5

RECT_TERRAIN_TYPES = {"Terrain", "solid", "platform", "gate", "breakable_gate", "weapon_gate", "turret_mount"}
TERRAIN_LAYOUT_TYPES = {"AuthoredTerrain", "TerrainPath", "TerrainStrip", "TerrainPieces"}
ENEMY_COLOR = (255, 92, 108)
TERRAIN_COLOR = (255, 190, 88)
GATE_COLOR = (92, 225, 255)
BOSS_COLOR = (210, 130, 255)
POINT_TOP_COLOR = (255, 112, 112)
POINT_BOTTOM_COLOR = (92, 255, 176)

PIECE_ROLE_ORDER = [
    "floor_surface",
    "ceiling_surface",
    "body_fill",
    "fixed_floor_block",
    "fixed_ceiling_block",
    "exposed_column",
    "floor_prop",
    "decor_prop",
    "turret_mount",
    "breakable_block",
]
PIECE_COLLISION_ORDER = ["auto", "none", "surface", "rect"]
PIECE_SIDE_ORDER = ["bottom", "top"]
AUTO_FILL_REPLACE_ROLES = {"floor_surface", "ceiling_surface", "body_fill"}
FORMATION_ORDER = ["single", "line", "v_shape", "random"]


@dataclass(frozen=True)
class StageDesignerProfile:
    stage_id: int
    stage_json: Path
    rects: Path
    mask_dir: Path
    background: Path
    terrain_kind: str
    label: str
    fallback_rects: Path | None = None
    fallback_mask_dir: Path | None = None


STAGE_PROFILES: dict[int, StageDesignerProfile] = {
    2: StageDesignerProfile(
        stage_id=2,
        stage_json=STAGE2_STAGE,
        rects=STAGE2_RECTS,
        mask_dir=STAGE2_MASK_DIR,
        background=STAGE2_BACKGROUND_PATH,
        terrain_kind="data_block",
        label="Stage2",
        fallback_rects=DEFAULT_RECTS,
        fallback_mask_dir=DEFAULT_MASK_DIR,
    ),
    3: StageDesignerProfile(
        stage_id=3,
        stage_json=DEFAULT_STAGE,
        rects=DEFAULT_RECTS,
        mask_dir=DEFAULT_MASK_DIR,
        background=BACKGROUND_PATH,
        terrain_kind="fortress_block",
        label="Stage3",
    ),
}


def _event_templates_for_kind(terrain_kind: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("virus", {"type": "EnemyVirus", "x": 0, "count": 1, "formation": "single"}),
        ("takeshi", {"type": "EnemyTakeshi", "x": 0, "count": 1, "formation": "single"}),
        ("pachemon", {"type": "EnemyPachemon", "x": 0, "count": 1, "formation": "single"}),
        ("crawler bottom", {"type": "EnemyCrawler", "x": 0, "count": 1, "surface": "bottom", "surface_offset": 22}),
        ("crawler top", {"type": "EnemyCrawler", "x": 0, "count": 1, "surface": "top", "surface_offset": 22}),
        ("turret bottom", {"type": "EnemyTurret", "x": 0, "count": 1, "surface": "bottom", "surface_offset": 22}),
        ("turret top", {"type": "EnemyTurret", "x": 0, "count": 1, "surface": "top", "surface_offset": 22}),
        ("broly", {"type": "EnemyBroly", "x": 0, "count": 1, "formation": "single"}),
        ("debris large", {"type": "EnemyDebrisLarge", "x": 0, "count": 1, "formation": "single"}),
        ("cough sprayer", {"type": "EnemyCoughSprayer", "x": 0, "count": 1, "y": 300}),
        ("spore splitter", {"type": "EnemySporeSplitter", "x": 0, "count": 1, "y": 300, "fixed_drop": "WeaponItem"}),
        ("billy", {"type": "EnemyBilly", "x": 0, "count": 1, "y": 300}),
        ("solid block", {"type": "Terrain", "x": 0, "y": 360, "w": 140, "h": 92, "kind": terrain_kind}),
        ("ceiling block", {"type": "Terrain", "x": 0, "y": 0, "w": 132, "h": 92, "kind": terrain_kind, "surface_anchor": "ceiling"}),
        ("turret mount", {"type": "turret_mount", "x": 0, "y": 360, "w": 260, "h": 46, "kind": terrain_kind}),
        ("breakable gate", {"type": "breakable_gate", "x": 0, "y": 220, "w": 120, "h": 240, "kind": terrain_kind, "hp": 48, "drop_chance": 0.03}),
        ("weapon gate", {"type": "weapon_gate", "x": 0, "y": 330, "w": 110, "h": 170, "kind": terrain_kind, "hp": 44}),
    ]


EVENT_TEMPLATES: list[tuple[str, dict[str, Any]]] = _event_templates_for_kind("fortress_block")

EVENT_IMAGE_PATHS = {
    "EnemyVirus": "graphic/enemy_virus.png",
    "EnemyTakeshi": "graphic/enemy_タケシ.png",
    "EnemyPachemon": "graphic/enemy_パチえもん.png",
    "EnemyBroly": "graphic/enemy_ブロリー.png",
    "EnemyBilly": "graphic/enemy_billy-herrington.jpg",
    "EnemyCoughSprayer": "graphic/enemy_cough_sprayer.png",
    "EnemySporeSplitter": "graphic/enemy_spore_splitter.png",
}

EVENT_IMAGE_SCALES = {
    "EnemyVirus": 0.77,
    "EnemyTakeshi": 0.70,
    "EnemyPachemon": 0.70,
    "EnemyBroly": 0.70,
    "EnemyCoughSprayer": 2.0,
    "EnemySporeSplitter": 2.0,
}


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _load_stage(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("stage JSON must contain an object")
    if not data.get("terrain_layout"):
        raise ValueError("stage JSON must contain terrain_layout")
    if not isinstance(data.get("world_events", []), list):
        raise ValueError("stage JSON world_events must be a list")
    return data


def _stage_id_from_json(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return int(data.get("stage_id"))
    except (TypeError, ValueError):
        return None


def _profile_from_args(args: argparse.Namespace) -> StageDesignerProfile:
    stage_id = args.stage
    if stage_id is None and args.stage_json:
        stage_id = _stage_id_from_json(_resolve(args.stage_json))
    return STAGE_PROFILES.get(int(stage_id or DEFAULT_STAGE_ID), STAGE_PROFILES[DEFAULT_STAGE_ID])


def _profile_path(primary: Path, fallback: Path | None) -> Path:
    if primary.exists() or fallback is None:
        return primary
    return fallback


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def _format_scalar(key: str, value: Any, *, indent: int, comma: bool) -> list[str]:
    suffix = "," if comma else ""
    return [" " * indent + f"{_compact_json(key)}: {_compact_json(value)}{suffix}"]


def _format_point_list(key: str, points: list[Any], *, indent: int, comma: bool) -> list[str]:
    lines = [" " * indent + f"{_compact_json(key)}: ["]
    for i, point in enumerate(points):
        suffix = "," if i < len(points) - 1 else ""
        lines.append(" " * (indent + 2) + f"{_compact_json(point)}{suffix}")
    lines.append(" " * indent + f"]{',' if comma else ''}")
    return lines


def _format_guide_lines(key: str, guide_lines: list[Any], *, indent: int, comma: bool) -> list[str]:
    if not guide_lines:
        return [" " * indent + f"{_compact_json(key)}: []{',' if comma else ''}"]
    lines = [" " * indent + f"{_compact_json(key)}: ["]
    for i, line in enumerate(guide_lines):
        suffix = "," if i < len(guide_lines) - 1 else ""
        if isinstance(line, dict):
            side = str(line.get("side", "bottom"))
            points = line.get("points", [])
            lines.append(
                " " * (indent + 2)
                + f"{{\"side\": {_compact_json(side)}, \"points\": {_compact_json(points)}}}{suffix}"
            )
        else:
            lines.append(" " * (indent + 2) + f"{_compact_json(line)}{suffix}")
    lines.append(" " * indent + f"]{',' if comma else ''}")
    return lines


def _format_compact_item_list(key: str, values: list[Any], *, indent: int, comma: bool) -> list[str]:
    if not values:
        return [" " * indent + f"{_compact_json(key)}: []{',' if comma else ''}"]
    lines = [" " * indent + f"{_compact_json(key)}: ["]
    for i, value in enumerate(values):
        suffix = "," if i < len(values) - 1 else ""
        lines.append(" " * (indent + 2) + f"{_compact_json(value)}{suffix}")
    lines.append(" " * indent + f"]{',' if comma else ''}")
    return lines


def _format_layout_object(obj: dict[str, Any], *, indent: int, comma: bool) -> list[str]:
    lines = [" " * indent + "{"]
    keys = list(obj.keys())
    for i, key in enumerate(keys):
        value = obj[key]
        is_last = i == len(keys) - 1
        if key in {"top", "bottom"} and isinstance(value, list):
            lines.extend(_format_point_list(key, value, indent=indent + 2, comma=not is_last))
        elif key == "pieces" and isinstance(value, list):
            lines.extend(_format_compact_item_list(key, value, indent=indent + 2, comma=not is_last))
        elif key == "guide_lines" and isinstance(value, list):
            lines.extend(_format_guide_lines(key, value, indent=indent + 2, comma=not is_last))
        elif key in {"guide_top", "guide_bottom"} and isinstance(value, list):
            lines.extend(_format_point_list(key, value, indent=indent + 2, comma=not is_last))
        else:
            lines.extend(_format_scalar(key, value, indent=indent + 2, comma=not is_last))
    lines.append(" " * indent + f"}}{',' if comma else ''}")
    return lines


def _format_list(key: str, values: list[Any], *, indent: int, comma: bool) -> list[str]:
    if not values:
        return [" " * indent + f"{_compact_json(key)}: []{',' if comma else ''}"]
    lines = [" " * indent + f"{_compact_json(key)}: ["]
    for i, value in enumerate(values):
        is_last = i == len(values) - 1
        if isinstance(value, dict) and (
            value.get("type") in TERRAIN_LAYOUT_TYPES
            or "top" in value
            or "bottom" in value
        ):
            lines.extend(_format_layout_object(value, indent=indent + 2, comma=not is_last))
        else:
            lines.append(" " * (indent + 2) + f"{_compact_json(value)}{',' if not is_last else ''}")
    lines.append(" " * indent + f"]{',' if comma else ''}")
    return lines


def _format_stage_json(data: dict[str, Any]) -> str:
    preferred = [
        "stage_id",
        "bgm",
        "boss_terrain_mode",
        "random_drop_scale",
        "terrain_layout",
        "boss_terrain",
        "world_events",
        "events",
    ]
    keys = [key for key in preferred if key in data]
    keys.extend(key for key in data if key not in keys)

    lines = ["{"]
    for i, key in enumerate(keys):
        value = data[key]
        is_last = i == len(keys) - 1
        if isinstance(value, list):
            lines.extend(_format_list(key, value, indent=2, comma=not is_last))
        else:
            lines.extend(_format_scalar(key, value, indent=2, comma=not is_last))
    lines.append("}")
    return "\n".join(lines) + "\n"


def _write_stage(path: Path, data: dict[str, Any]) -> None:
    path.write_text(_format_stage_json(data), encoding="utf-8")


def _layout(data: dict[str, Any]) -> dict[str, Any]:
    return data["terrain_layout"][0]


def _layout_start_x(layout: dict[str, Any]) -> int:
    return int(layout.get("x", layout.get("world_x", layout.get("start_offset", 0))))


def _stage_length(data: dict[str, Any]) -> int:
    layout = _layout(data)
    length = int(layout.get("length", 12000))
    if layout.get("type") == "TerrainPieces":
        piece_xs = [
            int(piece.get("x", 0))
            for piece in layout.get("pieces", [])
            if isinstance(piece, dict) and "x" in piece
        ]
        length = max(length, max(piece_xs, default=0) + 900)
    xs = [
        int(ev.get("x", ev.get("world_x", ev.get("trigger_x", 0))))
        for ev in data.get("world_events", [])
        if any(k in ev for k in ("x", "world_x", "trigger_x"))
    ]
    return max(length, max(xs, default=0) + 900)


def _interp(points: list[Any], x: float, fallback: float) -> float:
    if not points:
        return fallback
    pairs = [(float(p[0]), float(p[1])) for p in points if isinstance(p, list) and len(p) >= 2]
    if not pairs:
        return fallback
    pairs.sort()
    if x <= pairs[0][0]:
        return pairs[0][1]
    for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
        if x0 <= x <= x1:
            t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return pairs[-1][1]


def _event_x(event: dict[str, Any]) -> float | None:
    for key in ("x", "world_x", "trigger_x"):
        if key in event:
            return float(event[key])
    return None


def _event_x_key(event: dict[str, Any]) -> str | None:
    for key in ("x", "world_x", "trigger_x"):
        if key in event:
            return key
    return None


def _event_y(event: dict[str, Any], data: dict[str, Any]) -> float:
    if "y" in event:
        return float(event["y"])
    if "anchor_y" in event:
        return float(event["anchor_y"])
    wx = _event_x(event) or 0.0
    offset = float(event.get("surface_offset", 0.0))
    layout = _layout(data)
    if event.get("surface") == "top":
        return _interp(layout.get("top", []), wx, 80.0) + offset
    if event.get("surface") == "bottom":
        return _interp(layout.get("bottom", []), wx, SCREEN_HEIGHT - 80.0) - offset
    if event.get("type") == "BossGate":
        return 48.0
    return SCREEN_HEIGHT / 2


def _event_can_use_anchor_y(event: dict[str, Any]) -> bool:
    if event.get("type") == "BossGate":
        return False
    if event.get("type") in RECT_TERRAIN_TYPES:
        return False
    if event.get("surface") in {"top", "bottom"} and "y" not in event:
        return False
    return str(event.get("type", "")).startswith("Enemy")


def _set_event_x(event: dict[str, Any], value: float) -> None:
    key = _event_x_key(event)
    if key is None:
        return
    next_x = int(round(value))
    if event.get("type") == "BossGate":
        current_x = int(round(_event_x(event) or 0.0))
        delta = next_x - current_x
        for gate_key in ("trigger_x", "lock_camera_x", "player_limit_x"):
            if gate_key in event:
                event[gate_key] = int(round(float(event[gate_key]) + delta))
        return
    event[key] = next_x


def _set_event_y(event: dict[str, Any], value: float) -> None:
    if event.get("type") == "BossGate":
        return
    if event.get("surface") in {"top", "bottom"} and "y" not in event:
        return
    key = "y" if "y" in event or not _event_can_use_anchor_y(event) else "anchor_y"
    event[key] = int(round(max(0.0, min(float(SCREEN_HEIGHT), value))))


def _event_template_name(index: int, templates: list[tuple[str, dict[str, Any]]] | None = None) -> str:
    templates = EVENT_TEMPLATES if templates is None else templates
    return templates[index % len(templates)][0]


def _position_new_event(event: dict[str, Any], wx: float, wy: float) -> None:
    if "x" in event:
        event["x"] = int(round(wx))
    if "world_x" in event:
        event["world_x"] = int(round(wx))
    if "trigger_x" in event:
        event["trigger_x"] = int(round(wx))
    if event.get("surface") in {"top", "bottom"} and "y" not in event:
        return
    if event.get("surface_anchor") == "ceiling":
        event["y"] = 0
        return
    if "y" in event or event.get("type") in RECT_TERRAIN_TYPES:
        event["y"] = int(round(max(0.0, min(float(SCREEN_HEIGHT), wy))))
        return
    if _event_can_use_anchor_y(event):
        event["anchor_y"] = int(round(max(0.0, min(float(SCREEN_HEIGHT), wy))))


def _piece_asset_id(piece: Any) -> str:
    return f"{piece.group}:{piece.index + 1}"


def _piece_defaults(role: str) -> dict[str, Any]:
    if role == "floor_surface":
        return {"role": role, "collision": "surface", "side": "bottom"}
    if role == "ceiling_surface":
        return {"role": role, "collision": "surface", "side": "top", "flip_y": True}
    if role == "body_fill":
        return {"role": role, "collision": "none", "side": "bottom"}
    if role == "fixed_ceiling_block":
        return {"role": role, "collision": "rect", "side": "top", "flip_y": True}
    if role in {"floor_prop", "turret_mount", "breakable_block", "fixed_floor_block", "exposed_column"}:
        return {"role": role, "collision": "rect", "side": "bottom"}
    return {"role": role, "collision": "none", "side": "bottom"}


def _event_material_role(event: dict[str, Any]) -> str | None:
    etype = str(event.get("type", ""))
    if etype == "turret_mount":
        return "turret_mount"
    if etype in {"breakable_gate", "weapon_gate"}:
        return "breakable_block"
    if etype in RECT_TERRAIN_TYPES:
        if str(event.get("surface_anchor", "floor")) == "ceiling":
            return "fixed_ceiling_block"
        return "fixed_floor_block"
    return None


def _clean_guide_points(points: list[Any]) -> list[list[int]]:
    by_x: dict[int, list[int]] = {}
    for point in points:
        if not isinstance(point, list) or len(point) < 2:
            continue
        x = int(round(float(point[0])))
        y = int(round(max(0.0, min(float(SCREEN_HEIGHT), float(point[1])))))
        by_x[x] = [x, y]
    return [by_x[x] for x in sorted(by_x)]


def _distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 0.0001:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx = ax + t * dx
    cy = ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _event_can_edit_y(event: dict[str, Any]) -> bool:
    if event.get("type") == "BossGate":
        return False
    if event.get("surface") in {"top", "bottom"} and "y" not in event:
        return False
    if "y" in event:
        return True
    return _event_can_use_anchor_y(event)


def _fit_surface(source: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    scale = min(max_w / max(1, source.get_width()), max_h / max(1, source.get_height()))
    scale = min(1.0, scale)
    if abs(scale - 1.0) < 0.001:
        return source.copy()
    return pygame.transform.smoothscale(
        source,
        (max(1, int(source.get_width() * scale)), max(1, int(source.get_height() * scale))),
    )


def _simple_turret_sprite(surface: str = "bottom") -> pygame.Surface:
    surf = pygame.Surface((46, 46), pygame.SRCALPHA)
    pygame.draw.circle(surf, (40, 56, 62), (23, 23), 19)
    pygame.draw.circle(surf, (95, 123, 126), (23, 23), 19, 2)
    barrel_y = 15 if surface == "top" else 26
    pygame.draw.rect(surf, (164, 222, 210), (20, barrel_y, 24, 7), border_radius=3)
    pygame.draw.circle(surf, (255, 112, 142), (23, 23), 5)
    return surf


def _simple_crawler_sprite(surface: str = "bottom") -> pygame.Surface:
    surf = pygame.Surface((58, 30), pygame.SRCALPHA)
    body = pygame.Rect(7, 7, 44, 16)
    pygame.draw.ellipse(surf, (86, 180, 146), body)
    pygame.draw.ellipse(surf, (170, 238, 202), body, 2)
    for x in (13, 24, 35, 46):
        pygame.draw.line(surf, (38, 88, 76), (x, 21), (x - 5, 28), 2)
    pygame.draw.circle(surf, (255, 120, 150), (43, 14), 3)
    if surface == "top":
        surf = pygame.transform.flip(surf, False, True)
    return surf


def _simple_debris_sprite() -> pygame.Surface:
    surf = pygame.Surface((46, 46), pygame.SRCALPHA)
    points = [(22, 2), (40, 12), (36, 32), (18, 43), (4, 26), (8, 9)]
    pygame.draw.polygon(surf, (92, 100, 108), points)
    pygame.draw.polygon(surf, (154, 162, 170), points, 2)
    pygame.draw.line(surf, (50, 56, 62), (12, 12), (31, 33), 2)
    return surf


def _event_color(event: dict[str, Any]) -> tuple[int, int, int]:
    t = str(event.get("type", ""))
    if t == "Boss" or t == "BossGate":
        return BOSS_COLOR
    if t in {"breakable_gate", "weapon_gate"}:
        return GATE_COLOR
    if t in RECT_TERRAIN_TYPES:
        return TERRAIN_COLOR
    return ENEMY_COLOR


def _event_is_enemy(event: dict[str, Any]) -> bool:
    return str(event.get("type", "")).startswith("Enemy")


def _event_rect(event: dict[str, Any], data: dict[str, Any], camera_x: float) -> pygame.Rect:
    wx = _event_x(event) or 0.0
    sx = int(round(wx - camera_x))
    if event.get("type") in RECT_TERRAIN_TYPES:
        return pygame.Rect(
            sx,
            int(round(float(event.get("y", _event_y(event, data))))),
            max(8, int(event.get("w", 28))),
            max(8, int(event.get("h", 28))),
        )
    if event.get("type") == "BossGate":
        return pygame.Rect(sx - 4, 0, 8, SCREEN_HEIGHT)
    y = int(round(_event_y(event, data)))
    size = 22 if str(event.get("type", "")).startswith("Enemy") else 26
    return pygame.Rect(sx - size // 2, y - size // 2, size, size)


@dataclass
class Selection:
    kind: str
    index: int
    side: str = ""
    sub_index: int = -1


class StageDesigner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.profile = _profile_from_args(args)
        self.stage_path = _resolve(args.stage_json) if args.stage_json else self.profile.stage_json
        self.rects_path = (
            _resolve(args.rects)
            if args.rects
            else _profile_path(self.profile.rects, self.profile.fallback_rects)
        )
        if args.mask_dir:
            self.mask_dir = _resolve(args.mask_dir)
        elif self.rects_path == self.profile.rects:
            self.mask_dir = self.profile.mask_dir
        else:
            self.mask_dir = _profile_path(self.profile.mask_dir, self.profile.fallback_mask_dir)
        self.background_path = _resolve(args.background) if args.background else self.profile.background
        self.event_templates = _event_templates_for_kind(self.profile.terrain_kind)
        self.data = _load_stage(self.stage_path)
        self.screen = pygame.display.set_mode(
            (max(MIN_WINDOW_W, args.window_w), max(MIN_WINDOW_H, args.window_h)),
            pygame.RESIZABLE,
        )
        pygame.display.set_caption(f"Stage designer - {self.profile.label}")
        self.font = pygame.font.SysFont("consolas", 16) or pygame.font.Font(None, 16)
        self.small_font = pygame.font.SysFont("consolas", 13) or pygame.font.Font(None, 13)
        self.camera_x = float(args.x)
        self.mode = str(args.mode)
        self.selection: Selection | None = None
        self.show_help = True
        self.show_overlays = True
        self.dragging = False
        self.drag_offset = pygame.Vector2(0, 0)
        self.drag_start_world = pygame.Vector2(0, 0)
        self.panning = False
        self.pan_anchor = pygame.Vector2(0, 0)
        self.pan_camera_x = self.camera_x
        self.pan_camera_y = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.cursor_world = pygame.Vector2(self.camera_x + VIEW_W / 2, VIEW_H / 2)
        self.last_mouse_pos = pygame.Vector2(VIEW_W / 2, TOOLBAR_H + VIEW_H / 2)
        self.event_palette_index = 0
        self.piece_palette_role = "floor_surface"
        self.piece_palette_index = 0
        self.guide_mode = False
        self.guide_side = "bottom"
        self.palette_scroll_y = 0.0
        self.max_palette_scroll_y = 0.0
        self.palette_drag: dict[str, Any] | None = None
        self._palette_hitboxes: list[tuple[pygame.Rect, dict[str, Any]]] = []
        self._event_image_cache: dict[str, pygame.Surface] = {}
        self._piece_preview_cache: dict[tuple[str, int, int, int], pygame.Surface] = {}
        self._composer_piece_cache_key: tuple[str, str] | None = None
        self._composer_piece_cache: dict[str, list[Any]] | None = None
        self.message = f"Ready: {self.profile.label}"
        self.dirty = False
        self.undo_stack: list[dict[str, Any]] = []
        self._terrain_cache_key: str | None = None
        self._terrain_cache: tuple[list[Any], dict[str, list[Any]]] | None = None
        self._composer_layout_cache_key: str | None = None
        self._composer_layout_cache: Stage3ComposerLayout | None = None
        self._piece_layout_cache_key: str | None = None
        self._piece_layout_cache: tuple[Stage3ComposerLayout, dict[str, list[Any]]] | None = None
        self._backdrop_cache: dict[tuple[int, int], pygame.Surface] = {}

    @property
    def view_rect(self) -> pygame.Rect:
        return pygame.Rect(0, TOOLBAR_H, VIEW_W, VIEW_H)

    @property
    def palette_rect(self) -> pygame.Rect:
        return pygame.Rect(VIEW_W, TOOLBAR_H, PALETTE_W, VIEW_H)

    @property
    def info_rect(self) -> pygame.Rect:
        width = max(INFO_W, self.screen.get_width() - VIEW_W - PALETTE_W)
        return pygame.Rect(VIEW_W + PALETTE_W, TOOLBAR_H, width, VIEW_H)

    def _visible_world_size(self) -> tuple[int, int]:
        return max(1, int(round(VIEW_W / self.zoom))), max(1, int(round(VIEW_H / self.zoom)))

    def _push_undo(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.data))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)

    def _invalidate_terrain_cache(self) -> None:
        self._terrain_cache_key = None
        self._terrain_cache = None
        self._composer_layout_cache_key = None
        self._composer_layout_cache = None
        self._piece_layout_cache_key = None
        self._piece_layout_cache = None

    def _composer_asset_paths(self, event: dict[str, Any] | None = None) -> tuple[Path, Path]:
        profile = getattr(self, "profile", None)
        rects_path = getattr(self, "rects_path", None)
        mask_dir = getattr(self, "mask_dir", None)

        if rects_path is None:
            if profile is not None:
                rects_path = _profile_path(profile.rects, profile.fallback_rects)
            elif event is not None and event.get("kind") == "data_block":
                rects_path = STAGE2_RECTS
            else:
                rects_path = DEFAULT_RECTS
        rects_path = Path(rects_path)

        if mask_dir is None:
            if profile is not None:
                if rects_path == profile.rects:
                    mask_dir = profile.mask_dir
                else:
                    mask_dir = _profile_path(profile.mask_dir, profile.fallback_mask_dir)
            elif event is not None and event.get("kind") == "data_block":
                mask_dir = STAGE2_MASK_DIR
            else:
                mask_dir = DEFAULT_MASK_DIR
        return rects_path, Path(mask_dir)

    def _terrain(self) -> tuple[list[Any], dict[str, list[Any]]]:
        key = json.dumps(_layout(self.data), sort_keys=True, ensure_ascii=False)
        if self._terrain_cache is not None and self._terrain_cache_key == key:
            return self._terrain_cache
        start_x = float(_layout(self.data).get("start_offset", 0))
        segments = make_terrain_segments_from_event(_layout(self.data), start_x, default_seed=int(self.data.get("stage_id", 3)))
        rects_path, mask_dir = self._composer_asset_paths()
        pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
        self._terrain_cache_key = key
        self._terrain_cache = (segments, pieces)
        return self._terrain_cache

    def _composer_layout(self) -> Stage3ComposerLayout:
        layout = _layout(self.data)
        length = _stage_length(self.data)
        key = "composer:" + json.dumps(
            {
                "layout": layout,
                "length": length,
                "height": SCREEN_HEIGHT,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if (
            getattr(self, "_composer_layout_cache_key", None) == key
            and getattr(self, "_composer_layout_cache", None) is not None
        ):
            return self._composer_layout_cache
        segments, pieces = self._terrain()
        composer_layout = build_stage3_composer_layout(
            segments,
            pieces,
            start_x=0,
            end_x=length,
            height=SCREEN_HEIGHT,
            sample_step=int(layout.get("composer_sample_step", 48)),
            tolerance=int(layout.get("composer_tolerance", 26)),
            collision_step=int(layout.get("composer_collision_step", 8)),
            collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
            overlap=int(layout.get("composer_overlap", 0)),
        )
        self._composer_layout_cache_key = key
        self._composer_layout_cache = composer_layout
        return composer_layout

    def _piece_layout(self) -> tuple[Stage3ComposerLayout, dict[str, list[Any]]]:
        layout = _layout(self.data)
        key = "pieces:" + json.dumps(layout, sort_keys=True, ensure_ascii=False)
        if (
            getattr(self, "_piece_layout_cache_key", None) == key
            and getattr(self, "_piece_layout_cache", None) is not None
        ):
            return self._piece_layout_cache
        rects_path, mask_dir = self._composer_asset_paths()
        pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
        composer_layout = build_stage3_piece_layout(
            layout,
            pieces,
            start_x=_layout_start_x(layout),
            collision_step=int(layout.get("composer_collision_step", 8)),
            collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
        )
        self._piece_layout_cache_key = key
        self._piece_layout_cache = (composer_layout, pieces)
        return self._piece_layout_cache

    def _composer_pieces(self, event: dict[str, Any] | None = None) -> dict[str, list[Any]]:
        rects_path, mask_dir = self._composer_asset_paths(event)
        key = (str(rects_path), str(mask_dir))
        if (
            getattr(self, "_composer_piece_cache_key", None) == key
            and getattr(self, "_composer_piece_cache", None) is not None
        ):
            return self._composer_piece_cache  # type: ignore[return-value]
        pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
        self._composer_piece_cache_key = key
        self._composer_piece_cache = pieces
        if not hasattr(self, "_piece_preview_cache"):
            self._piece_preview_cache = {}
        self._piece_preview_cache.clear()
        return pieces

    def _piece_roles(self, pieces: dict[str, list[Any]] | None = None) -> list[str]:
        pieces = pieces or self._composer_pieces()
        roles = [role for role in PIECE_ROLE_ORDER if pieces.get(role)]
        return roles or [role for role, values in pieces.items() if values]

    def _current_piece_role(self) -> str:
        roles = self._piece_roles()
        if self.piece_palette_role not in roles:
            self.piece_palette_role = roles[0]
            self.piece_palette_index = 0
        return self.piece_palette_role

    def _piece_palette_options(
        self,
        role: str | None = None,
        pieces: dict[str, list[Any]] | None = None,
    ) -> list[Any]:
        role = role or self._current_piece_role()
        pieces = pieces or self._composer_pieces()
        return pieces.get(role, [])

    def _current_piece_asset(self) -> Any | None:
        options = self._piece_palette_options()
        if not options:
            return None
        self.piece_palette_index %= len(options)
        return options[self.piece_palette_index]

    def _piece_palette_summary(self) -> str:
        piece = self._current_piece_asset()
        asset = _piece_asset_id(piece) if piece is not None else "-"
        return f"piece palette: {self._current_piece_role()} {asset}"

    def _event_rect_image(self, event: dict[str, Any], w: int, h: int) -> pygame.Surface | None:
        piece = self._event_rect_piece(event, w, h)
        return None if piece is None else piece.image

    def _event_rect_piece(self, event: dict[str, Any], w: int, h: int) -> Any | None:
        role = _event_material_role(event)
        if role is None:
            return None
        pieces_by_group = self._composer_pieces(event)
        asset = event.get("material_asset")
        if isinstance(asset, str) and ":" in asset:
            group, index_text = asset.split(":", 1)
            try:
                index = int(index_text) - 1
            except ValueError:
                index = -1
            group_pieces = pieces_by_group.get(group, [])
            if 0 <= index < len(group_pieces):
                return group_pieces[index]
        pieces = list(pieces_by_group.get(role, []))
        if not pieces:
            return None
        if str(event.get("type", "")) in {"breakable_gate", "weapon_gate"}:
            block_pieces = [piece for piece in pieces if piece.group in {"block_tall", "block_square", "block_wide"}]
            if block_pieces:
                pieces = block_pieces
        aspect = w / max(1, h)
        ranked = sorted(
            pieces,
            key=lambda piece: (
                abs((piece.image.get_width() / max(1, piece.image.get_height())) - aspect),
                abs(piece.image.get_width() - w) + abs(piece.image.get_height() - h),
            ),
        )
        return ranked[0]

    def _apply_event_rect_asset(self, event: dict[str, Any]) -> None:
        if event.get("kind") != "data_block":
            return
        role = _event_material_role(event)
        if role is None:
            return
        piece = self._event_rect_piece(event, int(event.get("w", 1)), int(event.get("h", 1)))
        if piece is None:
            return
        event["material_role"] = role
        event["material_asset"] = _piece_asset_id(piece)
        event["w"] = int(piece.image.get_width())
        event["h"] = int(piece.image.get_height())

    def _event_templates(self) -> list[tuple[str, dict[str, Any]]]:
        return getattr(self, "event_templates", EVENT_TEMPLATES)

    def _event_template_name(self, index: int) -> str:
        return _event_template_name(index, self._event_templates())

    def _palette_summary(self) -> list[str]:
        if self.mode == "terrain" and _layout(self.data).get("type") == "TerrainPieces":
            piece = self._current_piece_asset()
            asset = _piece_asset_id(piece) if piece is not None else "-"
            return [
                f"piece role: {self._current_piece_role()}",
                f"piece asset: {asset}",
                f"guide mode: {self.guide_mode}",
                f"new guide side: {self.guide_side}",
            ]
        return [f"event palette: {self._event_template_name(self.event_palette_index)}", f"guide mode: {self.guide_mode}"]

    def _palette_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = [
            {"kind": "event", "template_index": i}
            for i, _template in enumerate(self._event_templates())
        ]
        for role in self._piece_roles():
            for piece in self._piece_palette_options(role):
                entries.append({"kind": "piece", "role": role, "asset": _piece_asset_id(piece)})
        return entries

    def _palette_payload_key(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        if payload.get("kind") == "event":
            return ("event", int(payload.get("template_index", 0)))
        return ("piece", str(payload.get("role", "")), str(payload.get("asset", "")))

    def _current_palette_payload(self) -> dict[str, Any]:
        if self.mode == "events":
            return {"kind": "event", "template_index": self.event_palette_index}
        piece = self._current_piece_asset()
        return {
            "kind": "piece",
            "role": self._current_piece_role(),
            "asset": _piece_asset_id(piece) if piece is not None else "",
        }

    def _move_palette_cursor(self, dx: int, dy: int) -> None:
        entries = self._palette_entries()
        if not entries:
            self.message = "Palette is empty"
            return
        current_key = self._palette_payload_key(self._current_palette_payload())
        try:
            index = [self._palette_payload_key(entry) for entry in entries].index(current_key)
        except ValueError:
            index = 0
        next_index = max(0, min(len(entries) - 1, index + dx + dy * PALETTE_COLS))
        self._select_palette_payload(entries[next_index])

    def _event_image(self, event: dict[str, Any], *, max_w: int = 64, max_h: int = 52) -> pygame.Surface:
        etype = str(event.get("type", ""))
        material_role = str(event.get("material_role", _event_material_role(event) or ""))
        key = (
            f"{etype}:{event.get('kind', '')}:{event.get('surface', '')}:"
            f"{event.get('surface_anchor', '')}:{material_role}:{event.get('fixed_drop', '')}:"
            f"{event.get('enhanced', False)}:{event.get('w', '')}:{event.get('h', '')}:{max_w}x{max_h}"
        )
        if key in self._event_image_cache:
            return self._event_image_cache[key]

        image: pygame.Surface | None = None
        rel_path = EVENT_IMAGE_PATHS.get(etype)
        if rel_path:
            try:
                image = pygame.image.load(str(ROOT / "assets" / rel_path)).convert_alpha()
                scale = EVENT_IMAGE_SCALES.get(etype)
                if scale:
                    image = pygame.transform.smoothscale(
                        image,
                        (
                            max(1, int(image.get_width() * scale)),
                            max(1, int(image.get_height() * scale)),
                        ),
                    )
            except pygame.error:
                try:
                    image = pygame.image.load(str(ROOT / "assets" / rel_path)).convert()
                    image.set_colorkey(image.get_at((0, 0)))
                except pygame.error:
                    image = None
        if image is None and etype == "EnemyTurret":
            image = EnemyTurret._make_sprite(str(event.get("surface", "bottom")))
        if image is None and etype == "EnemyCrawler":
            image = EnemyCrawler._make_sprite(str(event.get("surface", "bottom")))
        if image is None and etype in {"EnemyDebrisLarge", "EnemyDebrisShard"}:
            image = _rock_sprite(84 if etype == "EnemyDebrisLarge" else 30, 17, (82, 80, 92))
        if image is None and etype in RECT_TERRAIN_TYPES:
            w = max(24, int(event.get("w", 72)))
            h = max(24, int(event.get("h", 54)))
            image = self._event_rect_image(event, w, h)
        if image is None and etype in RECT_TERRAIN_TYPES:
            w = max(24, int(event.get("w", 72)))
            h = max(24, int(event.get("h", 54)))
            image = Terrain._make_surface(
                w,
                h,
                str(event.get("kind", "fortress_block")),
                destructible=bool(event.get("destructible") or etype in {"breakable_gate", "weapon_gate"}),
                fixed_drop="WeaponItem" if etype == "weapon_gate" else None,
                surface_anchor=str(event.get("surface_anchor", "floor")),
                material_role=material_role or None,
            )
        if image is None:
            image = pygame.Surface((42, 42), pygame.SRCALPHA)
            pygame.draw.circle(image, _event_color(event), (21, 21), 18)
            pygame.draw.circle(image, (240, 248, 245), (21, 21), 18, 2)
        fitted = image.copy() if etype in RECT_TERRAIN_TYPES else _fit_surface(image, max_w, max_h)
        if bool(event.get("enhanced", False)):
            fitted = fitted.copy()
            tint = pygame.Surface(fitted.get_size(), pygame.SRCALPHA)
            tint.fill((255, 74, 132, 46))
            fitted.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            pygame.draw.rect(fitted, (255, 118, 166), fitted.get_rect(), 2)
        self._event_image_cache[key] = fitted
        return fitted

    def _load_backdrop(self, width: int = VIEW_W, height: int = VIEW_H) -> pygame.Surface:
        key = (width, height)
        if key in self._backdrop_cache:
            return self._backdrop_cache[key].copy()
        surface = pygame.Surface((width, height))
        surface.fill((6, 14, 17))
        background_path = getattr(self, "background_path", BACKGROUND_PATH)
        try:
            raw = pygame.image.load(str(background_path))
        except (FileNotFoundError, pygame.error):
            self._backdrop_cache[key] = surface.copy()
            return surface
        scale = max(width / raw.get_width(), height / raw.get_height())
        scaled = pygame.transform.smoothscale(
            raw,
            (max(width, int(raw.get_width() * scale)), max(height, int(raw.get_height() * scale))),
        )
        surface.blit(scaled, ((width - scaled.get_width()) // 2, (height - scaled.get_height()) // 2))
        veil = pygame.Surface((width, height), pygame.SRCALPHA)
        veil.fill((0, 4, 6, 90))
        surface.blit(veil, (0, 0))
        self._backdrop_cache[key] = surface.copy()
        return surface

    def _world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (
            int(round((x - self.camera_x) * self.zoom)),
            int(round((y - self.camera_y) * self.zoom + TOOLBAR_H)),
        )

    def _screen_to_world(self, pos: tuple[int, int]) -> tuple[float, float]:
        return (
            float(pos[0]) / self.zoom + self.camera_x,
            float(pos[1] - TOOLBAR_H) / self.zoom + self.camera_y,
        )

    def _update_cursor_world(self, pos: tuple[int, int]) -> None:
        self.last_mouse_pos.xy = pos
        if self.view_rect.collidepoint(pos):
            self.cursor_world.xy = self._screen_to_world(pos)

    def _clamp_camera(self) -> None:
        visible_w, visible_h = self._visible_world_size()
        max_x = max(0, _stage_length(self.data) - visible_w)
        self.camera_x = max(-180.0, min(float(max_x + 180), self.camera_x))
        if visible_h >= SCREEN_HEIGHT:
            self.camera_y = (float(SCREEN_HEIGHT) - float(visible_h)) / 2.0
        else:
            self.camera_y = max(0.0, min(float(SCREEN_HEIGHT - visible_h), self.camera_y))

    def _set_zoom(self, next_zoom: float, anchor_pos: tuple[int, int] | None = None) -> None:
        old_zoom = self.zoom
        next_zoom = max(MIN_ZOOM, min(MAX_ZOOM, next_zoom))
        if abs(next_zoom - old_zoom) < 0.001:
            return
        anchor = anchor_pos if anchor_pos is not None and self.view_rect.collidepoint(anchor_pos) else (VIEW_W // 2, TOOLBAR_H + VIEW_H // 2)
        before = self._screen_to_world(anchor)
        self.zoom = next_zoom
        self.camera_x = before[0] - float(anchor[0]) / self.zoom
        self.camera_y = before[1] - float(anchor[1] - TOOLBAR_H) / self.zoom
        self._clamp_camera()
        self._update_cursor_world(anchor)
        self.message = f"Zoom: {self.zoom:.2f}x"

    def _pan_camera(self, dx: float, dy: float = 0.0) -> None:
        self.camera_x += dx
        self.camera_y += dy
        self._clamp_camera()

    def _event_at(self, pos: tuple[int, int]) -> int | None:
        wx, wy = self._screen_to_world(pos)
        tolerance = max(5, int(round(8 / self.zoom)))
        best: tuple[int, float] | None = None
        for i, event in enumerate(self.data.get("world_events", [])):
            rects = [rect.inflate(tolerance, tolerance) for rect in self._event_preview_world_rects(event)]
            for rect in rects:
                if not rect.collidepoint(wx, wy):
                    continue
                dist = (rect.centerx - wx) ** 2 + (rect.centery - wy) ** 2
                if best is None or dist < best[1]:
                    best = (i, dist)
        return None if best is None else best[0]

    def _terrain_surface_y_at(self, world_x: float, side: str) -> float | None:
        layout = _layout(self.data)
        if layout.get("type") == "TerrainPieces":
            composer_layout, _pieces = self._piece_layout()
            for run in composer_layout.collision_runs:
                if run.side == side and run.x0 <= world_x <= run.x1:
                    return float(run.y)
        points = layout.get("top" if side == "top" else "bottom", [])
        if not points:
            points = layout.get("guide_top" if side == "top" else "guide_bottom", [])
        if not points:
            guide_points = [
                line.get("points", [])
                for line in layout.get("guide_lines", [])
                if isinstance(line, dict) and line.get("side", "bottom") == side
            ]
            points = guide_points[0] if guide_points else []
        if points:
            return _interp(points, world_x, 80.0 if side == "top" else SCREEN_HEIGHT - 80.0)
        return None

    def _event_anchor_y(self, event: dict[str, Any], world_x: float) -> float:
        if "y" in event:
            return float(event["y"])
        if "anchor_y" in event:
            return float(event["anchor_y"])
        if event.get("surface") in {"top", "bottom"}:
            surface = str(event.get("surface", "bottom"))
            sy = self._terrain_surface_y_at(world_x, surface)
            if sy is None:
                sy = 80.0 if surface == "top" else SCREEN_HEIGHT - 80.0
            offset = float(event.get("surface_offset", event.get("offset", 20)))
            return sy + offset if surface == "top" else sy - offset
        if event.get("type") == "BossGate":
            return 48.0
        safe_top, safe_bottom = self._safe_y_bounds(world_x)
        return (safe_top + safe_bottom) / 2.0

    def _safe_y_bounds(self, world_x: float, *, margin: float = 60.0) -> tuple[float, float]:
        top = float(margin)
        bottom = float(SCREEN_HEIGHT - margin)
        top_y = self._terrain_surface_y_at(world_x, "top")
        bottom_y = self._terrain_surface_y_at(world_x, "bottom")
        if top_y is not None:
            top = max(top, top_y + margin)
        if bottom_y is not None:
            bottom = min(bottom, bottom_y - margin)
        if bottom <= top:
            return float(margin), float(SCREEN_HEIGHT - margin)
        return top, bottom

    def _event_preview_positions(self, event: dict[str, Any]) -> list[tuple[float, float]]:
        count = max(1, int(event.get("count", 1)))
        base_x = _event_x(event) or 0.0
        if event.get("type") in RECT_TERRAIN_TYPES or event.get("type") == "BossGate":
            return [(base_x, self._event_anchor_y(event, base_x))]
        if event.get("surface") in {"top", "bottom"}:
            step = float(event.get("surface_step", event.get("step", 56)))
            return [(base_x + i * step, self._event_anchor_y(event, base_x + i * step)) for i in range(count)]
        if "y" in event:
            step = float(event.get("surface_step", event.get("step", 44)))
            return [(base_x + i * step, float(event["y"])) for i in range(count)]
        formation = str(event.get("formation", "single"))
        safe_top, safe_bottom = self._safe_y_bounds(base_x)
        center_y = float(event.get("anchor_y", (safe_top + safe_bottom) / 2.0))
        center_y = max(safe_top, min(safe_bottom, center_y))
        if formation in {"", "single"} or count <= 1:
            return [(base_x, center_y)]
        if formation == "line":
            if "anchor_y" in event:
                step_x = float(event.get("step", 44))
                step_y = float(event.get("formation_step_y", 44))
                mid = (count - 1) / 2.0
                return [
                    (
                        base_x + i * step_x,
                        max(safe_top, min(safe_bottom, center_y + (i - mid) * step_y)),
                    )
                    for i in range(count)
                ]
            step_y = (safe_bottom - safe_top) / max(count - 1, 1)
            return [(base_x, float(safe_top + i * step_y)) for i in range(count)]
        if formation == "v_shape":
            amp = min(60.0, max(24.0, (safe_bottom - safe_top) * 0.25))
            return [
                (
                    base_x + abs(i - count // 2) * 50,
                    max(safe_top, min(safe_bottom, center_y + (i - count // 2) * amp)),
                )
                for i in range(count)
            ]
        if "anchor_y" in event:
            return [
                (base_x + i * 40, max(safe_top, min(safe_bottom, center_y + ((i * 47) % 80) - 40)))
                for i in range(count)
            ]
        span = max(1.0, safe_bottom - safe_top)
        return [(base_x + i * 40, safe_top + ((i * 73) % int(span))) for i in range(count)]

    def _event_preview_world_rects(self, event: dict[str, Any]) -> list[pygame.Rect]:
        if event.get("type") in RECT_TERRAIN_TYPES or event.get("type") == "BossGate":
            return [_event_rect(event, self.data, 0)]
        preview = self._event_image(event, max_w=58, max_h=52)
        rects = []
        for wx, wy in self._event_preview_positions(event):
            rects.append(preview.get_rect(center=(int(round(wx)), int(round(wy)))))
        return rects

    def _terrain_point_at(self, pos: tuple[int, int]) -> Selection | None:
        wx, wy = self._screen_to_world(pos)
        tolerance = max(8.0, 10.0)
        best: tuple[Selection, float] | None = None
        layout = _layout(self.data)
        for side in ("top", "bottom"):
            for i, point in enumerate(layout.get(side, [])):
                if not isinstance(point, list) or len(point) < 2:
                    continue
                dx = float(point[0]) - wx
                dy = float(point[1]) - wy
                dist = dx * dx + dy * dy
                if dist <= tolerance * tolerance and (best is None or dist < best[1]):
                    best = (Selection("terrain", i, side), dist)
        return None if best is None else best[0]

    def _terrain_piece_at(self, pos: tuple[int, int]) -> Selection | None:
        wx, wy = self._screen_to_world(pos)
        composer_layout, _pieces = self._piece_layout()
        tolerance = max(3, int(round(6 / self.zoom)))
        best: tuple[Selection, float] | None = None
        for i, placement in enumerate(composer_layout.placements):
            rect = pygame.Rect(
                int(round(placement.x)),
                placement.y,
                placement.image.get_width(),
                placement.image.get_height(),
            ).inflate(tolerance, tolerance)
            if rect.collidepoint(wx, wy):
                dist = (rect.centerx - wx) ** 2 + (rect.centery - wy) ** 2
                if best is None or dist < best[1]:
                    best = (Selection("piece", i), dist)
        return None if best is None else best[0]

    def _select_at(self, pos: tuple[int, int]) -> None:
        self.selection = None
        if not self.view_rect.collidepoint(pos):
            return
        event_index = self._event_at(pos)
        piece_selection: Selection | None = None
        if _layout(self.data).get("type") == "TerrainPieces":
            piece_selection = self._terrain_piece_at(pos)
        elif self.mode == "terrain":
            piece_selection = self._terrain_point_at(pos)

        if event_index is not None and (self.mode != "terrain" or piece_selection is None):
            self.selection = Selection("event", event_index)
            ev = self.data["world_events"][event_index]
            self.message = f"Selected event #{event_index + 1}: {ev.get('type')}"
            return
        if piece_selection is not None:
            self.selection = piece_selection
            if self.selection.kind == "piece":
                self.message = f"Selected terrain piece #{self.selection.index + 1}"
            else:
                self.message = f"Selected {self.selection.side} point #{self.selection.index + 1}"
            return
        if event_index is not None:
            index = event_index
            self.selection = Selection("event", index)
            ev = self.data["world_events"][index]
            self.message = f"Selected event #{index + 1}: {ev.get('type')}"

    def _selected_event(self) -> dict[str, Any] | None:
        if self.selection is None or self.selection.kind != "event":
            return None
        events = self.data.get("world_events", [])
        if 0 <= self.selection.index < len(events):
            return events[self.selection.index]
        self.selection = None
        return None

    def _selected_point(self) -> list[Any] | None:
        if self.selection is None or self.selection.kind != "terrain":
            return None
        points = _layout(self.data).get(self.selection.side, [])
        if 0 <= self.selection.index < len(points):
            return points[self.selection.index]
        self.selection = None
        return None

    def _selected_piece(self) -> dict[str, Any] | None:
        if self.selection is None or self.selection.kind != "piece":
            return None
        pieces = _layout(self.data).get("pieces", [])
        if 0 <= self.selection.index < len(pieces):
            return pieces[self.selection.index]
        self.selection = None
        return None

    def _guide_lines(self) -> list[dict[str, Any]]:
        layout = _layout(self.data)
        lines = layout.get("guide_lines")
        if not isinstance(lines, list):
            lines = []
        if not lines:
            for key, side in (("guide_top", "top"), ("guide_bottom", "bottom")):
                points = _clean_guide_points(layout.get(key, []))
                if points:
                    lines.append({"side": side, "points": points})
            if lines:
                layout["guide_lines"] = lines
                layout.pop("guide_top", None)
                layout.pop("guide_bottom", None)
        layout["guide_lines"] = lines
        return lines

    def _selected_guide_line_index(self) -> int | None:
        if self.selection is None or self.selection.kind not in {"guide_line", "guide_point"}:
            return None
        lines = self._guide_lines()
        if 0 <= self.selection.index < len(lines):
            return self.selection.index
        return None

    def _selected_guide_line(self) -> dict[str, Any] | None:
        index = self._selected_guide_line_index()
        if index is None:
            return None
        return self._guide_lines()[index]

    def _guide_point_at(self, pos: tuple[int, int]) -> Selection | None:
        wx, wy = self._screen_to_world(pos)
        tolerance = max(7.0, 8.0 / self.zoom)
        best: tuple[Selection, float] | None = None
        for line_i, line in enumerate(self._guide_lines()):
            for point_i, point in enumerate(line.get("points", [])):
                if not isinstance(point, list) or len(point) < 2:
                    continue
                dx = float(point[0]) - wx
                dy = float(point[1]) - wy
                dist = dx * dx + dy * dy
                if dist <= tolerance * tolerance and (best is None or dist < best[1]):
                    best = (Selection("guide_point", line_i, sub_index=point_i), dist)
        return None if best is None else best[0]

    def _guide_line_at(self, pos: tuple[int, int]) -> Selection | None:
        wx, wy = self._screen_to_world(pos)
        tolerance = max(8.0, 10.0 / self.zoom)
        best: tuple[Selection, float] | None = None
        for line_i, line in enumerate(self._guide_lines()):
            points = _clean_guide_points(line.get("points", []))
            for point_a, point_b in zip(points, points[1:]):
                dist = _distance_to_segment(
                    wx,
                    wy,
                    float(point_a[0]),
                    float(point_a[1]),
                    float(point_b[0]),
                    float(point_b[1]),
                )
                if dist <= tolerance and (best is None or dist < best[1]):
                    best = (Selection("guide_line", line_i), dist)
        return None if best is None else best[0]

    def _add_guide_point_to_line(self, line_index: int, wx: float, wy: float) -> None:
        self._push_undo()
        lines = self._guide_lines()
        if not (0 <= line_index < len(lines)):
            return
        point = [int(round(wx)), int(round(max(0.0, min(float(SCREEN_HEIGHT), wy))))]
        points = _clean_guide_points([*lines[line_index].get("points", []), point])
        lines[line_index]["points"] = points
        point_index = next((i for i, p in enumerate(points) if p[0] == point[0]), len(points) - 1)
        self.selection = Selection("guide_point", line_index, sub_index=point_index)
        self.dirty = True
        self.message = f"Added guide point to {lines[line_index].get('side', 'bottom')} line"

    def _create_guide_line(self, wx: float, wy: float) -> None:
        self._push_undo()
        layout = _layout(self.data)
        line = {
            "side": self.guide_side,
            "points": [[int(round(wx)), int(round(max(0.0, min(float(SCREEN_HEIGHT), wy))))]],
        }
        lines = self._guide_lines()
        lines.append(line)
        layout["guide_lines"] = lines
        self.selection = Selection("guide_point", len(lines) - 1, sub_index=0)
        self.dirty = True
        self.message = f"Created {self.guide_side} guide line"

    def _toggle_selected_guide_side(self) -> None:
        line = self._selected_guide_line()
        if line is None:
            self.guide_side = "top" if self.guide_side == "bottom" else "bottom"
            self.message = f"New guide side: {self.guide_side}"
            return
        self._push_undo()
        line["side"] = "top" if line.get("side", "bottom") == "bottom" else "bottom"
        self.guide_side = str(line["side"])
        self.dirty = True
        self.message = f"Guide line side: {line['side']}"

    def _auto_fill_from_guides(self) -> None:
        layout = _layout(self.data)
        if layout.get("type") != "TerrainPieces":
            self.message = "TerrainPieces layout is required"
            return
        line = self._selected_guide_line()
        if line is None:
            lines = self._guide_lines()
            if len(lines) == 1:
                line = lines[0]
                self.selection = Selection("guide_line", 0)
            else:
                self.message = "Select one guide line before auto-fill"
                return
        side = "top" if line.get("side") == "top" else "bottom"
        points = _clean_guide_points(line.get("points", []))
        if len(points) < 2:
            self.message = "Need 2+ unique guide x points"
            return
        start = int(points[0][0])
        end = int(points[-1][0])
        if end <= start:
            self.message = "Guide range is empty"
            return
        local_points = [[int(round(float(p[0]) - start)), int(round(float(p[1])))] for p in points]
        if side == "top":
            top = local_points
            bottom = [[0, SCREEN_HEIGHT], [end - start, SCREEN_HEIGHT]]
        else:
            top = [[0, 0], [end - start, 0]]
            bottom = local_points
        authored = {
            "type": "AuthoredTerrain",
            "theme": str(layout.get("theme", "fortress")),
            "length": end - start,
            "segment_w": int(layout.get("composer_sample_step", 48)),
            "min_gap": 180,
            "curve": "smooth",
            "top": top,
            "bottom": bottom,
        }
        rects_path, mask_dir = self._composer_asset_paths()
        pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
        segments = make_terrain_segments_from_event(authored, start, default_seed=int(self.data.get("stage_id", 3)))
        composer = build_stage3_composer_layout(
            segments,
            pieces,
            start_x=start,
            end_x=end,
            sample_step=int(layout.get("composer_sample_step", 48)),
            tolerance=int(layout.get("composer_tolerance", 26)),
            collision_step=int(layout.get("composer_collision_step", 8)),
            collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
            overlap=int(layout.get("composer_overlap", 0)),
        )
        generated = []
        for placement in composer.placements:
            if placement.role not in AUTO_FILL_REPLACE_ROLES:
                continue
            if placement.side != side:
                continue
            raw: dict[str, Any] = {
                "asset": placement.asset,
                "x": int(placement.x),
                "y": int(placement.y),
                "role": placement.role,
                "collision": placement.collision,
                "side": placement.side,
            }
            if placement.role == "ceiling_surface" or (placement.role == "body_fill" and placement.side == "top"):
                raw["flip_y"] = True
            generated.append(raw)
        if not generated:
            self.message = "Auto fill generated no pieces"
            return
        self._push_undo()
        old_pieces = layout.setdefault("pieces", [])
        kept = [
            piece
            for piece in old_pieces
            if (
                not isinstance(piece, dict)
                or str(piece.get("role", "")) not in AUTO_FILL_REPLACE_ROLES
                or str(piece.get("side", "bottom")) != side
                or not (start <= int(piece.get("x", -999999)) <= end)
            )
        ]
        layout["pieces"] = [*kept, *generated]
        self.selection = None
        self._invalidate_terrain_cache()
        self.dirty = True
        self.message = f"Auto-filled {len(generated)} {side} pieces ({start}-{end})"

    def _add_event_template_at(self, index: int, wx: float, wy: float) -> None:
        self._push_undo()
        templates = self._event_templates()
        _name, template = templates[index % len(templates)]
        event = copy.deepcopy(template)
        self._apply_event_rect_asset(event)
        _position_new_event(event, wx, wy)
        events = self.data.setdefault("world_events", [])
        events.append(event)
        self.selection = Selection("event", len(events) - 1)
        self.dirty = True
        self.message = f"Added event: {event.get('type')}"

    def _add_event_at(self, wx: float, wy: float) -> None:
        self._add_event_template_at(self.event_palette_index, wx, wy)

    def _add_piece_asset_at(self, role: str, asset_id: str, wx: float, wy: float) -> None:
        layout = _layout(self.data)
        if layout.get("type") != "TerrainPieces":
            self.message = "TerrainPieces layout is required"
            return
        self._push_undo()
        raw = {
            "asset": asset_id,
            "x": int(round(wx)),
            "y": int(round(wy)),
            **_piece_defaults(role),
        }
        layout.setdefault("pieces", []).append(raw)
        self.selection = Selection("piece", len(layout["pieces"]) - 1)
        self._invalidate_terrain_cache()
        self.dirty = True
        self.message = f"Added piece: {raw['asset']}"

    def _add_piece_at(self, wx: float, wy: float) -> None:
        piece = self._current_piece_asset()
        if piece is None:
            self.message = "No terrain piece in palette"
            return
        self._add_piece_asset_at(self._current_piece_role(), _piece_asset_id(piece), wx, wy)

    def _add_palette_payload_at(self, payload: dict[str, Any], wx: float, wy: float) -> None:
        if payload.get("kind") == "event":
            self.event_palette_index = int(payload.get("template_index", 0)) % len(self._event_templates())
            self.mode = "events"
            self._add_event_template_at(self.event_palette_index, wx, wy)
            return
        if payload.get("kind") == "piece":
            role = str(payload.get("role", self._current_piece_role()))
            asset = str(payload.get("asset", ""))
            if not asset:
                self.message = "No terrain piece asset"
                return
            self.piece_palette_role = role
            asset_ids = [_piece_asset_id(piece) for piece in self._piece_palette_options(role)]
            if asset in asset_ids:
                self.piece_palette_index = asset_ids.index(asset)
            self.mode = "terrain"
            self._add_piece_asset_at(role, asset, wx, wy)
            return

    def _add_from_palette(self) -> None:
        if self.mode == "terrain":
            self._add_piece_at(self.cursor_world.x, self.cursor_world.y)
        else:
            self._add_event_at(self.cursor_world.x, self.cursor_world.y)

    def _delete_selection(self) -> None:
        if self.selection is None:
            self.message = "Nothing selected"
            return
        self._push_undo()
        if self.selection.kind == "event":
            events = self.data.get("world_events", [])
            if 0 <= self.selection.index < len(events):
                removed = events.pop(self.selection.index)
                self.message = f"Deleted event: {removed.get('type')}"
        elif self.selection.kind == "piece":
            pieces = _layout(self.data).get("pieces", [])
            if 0 <= self.selection.index < len(pieces):
                removed = pieces.pop(self.selection.index)
                self._invalidate_terrain_cache()
                self.message = f"Deleted piece: {removed.get('asset')}"
        elif self.selection.kind == "guide_point":
            lines = self._guide_lines()
            if 0 <= self.selection.index < len(lines):
                points = lines[self.selection.index].get("points", [])
                if 0 <= self.selection.sub_index < len(points):
                    points.pop(self.selection.sub_index)
                    if not points:
                        lines.pop(self.selection.index)
                    self.message = "Deleted guide point"
        elif self.selection.kind == "guide_line":
            lines = self._guide_lines()
            if 0 <= self.selection.index < len(lines):
                lines.pop(self.selection.index)
                self.message = "Deleted guide line"
        else:
            points = _layout(self.data).get(self.selection.side, [])
            if 0 <= self.selection.index < len(points):
                points.pop(self.selection.index)
                self._invalidate_terrain_cache()
                self.message = f"Deleted {self.selection.side} point"
        self.selection = None
        self.dirty = True

    def _duplicate_selection(self, *, offset: bool = True) -> None:
        if self.selection is None:
            self.message = "Nothing selected"
            return
        self._push_undo()
        if self.selection.kind == "event":
            events = self.data.get("world_events", [])
            if not (0 <= self.selection.index < len(events)):
                return
            clone = copy.deepcopy(events[self.selection.index])
            if offset and _event_x(clone) is not None:
                _set_event_x(clone, (_event_x(clone) or 0.0) + 96)
            if offset and clone.get("surface") not in {"top", "bottom"} and "y" in clone:
                clone["y"] = int(round(min(float(SCREEN_HEIGHT), float(clone["y"]) + 24)))
            if offset and clone.get("surface") not in {"top", "bottom"} and "anchor_y" in clone:
                clone["anchor_y"] = int(round(min(float(SCREEN_HEIGHT), float(clone["anchor_y"]) + 24)))
            events.insert(self.selection.index + 1, clone)
            self.selection = Selection("event", self.selection.index + 1)
            self.message = f"Duplicated event: {clone.get('type')}"
        elif self.selection.kind == "piece":
            pieces = _layout(self.data).get("pieces", [])
            if not (0 <= self.selection.index < len(pieces)):
                return
            clone = copy.deepcopy(pieces[self.selection.index])
            if offset:
                clone["x"] = int(round(float(clone.get("x", 0)) + 48))
                clone["y"] = int(round(float(clone.get("y", 0)) + 24))
            pieces.insert(self.selection.index + 1, clone)
            self.selection = Selection("piece", self.selection.index + 1)
            self._invalidate_terrain_cache()
            self.message = f"Duplicated piece: {clone.get('asset')}"
        else:
            point = self._selected_point()
            if point is None:
                return
            points = _layout(self.data).get(self.selection.side, [])
            clone = [int(round(float(point[0]) + 96)), int(round(float(point[1])))]
            points.insert(self.selection.index + 1, clone)
            self.selection = Selection("terrain", self.selection.index + 1, self.selection.side)
            self._invalidate_terrain_cache()
            self.message = f"Duplicated {self.selection.side} point"
        self.dirty = True

    def _cycle_event_palette(self, delta: int) -> None:
        self._select_palette_payload(
            {"kind": "event", "template_index": (self.event_palette_index + delta) % len(self._event_templates())}
        )

    def _cycle_piece_role(self, delta: int) -> None:
        roles = self._piece_roles()
        if not roles:
            self.message = "No terrain piece roles"
            return
        current = roles.index(self._current_piece_role()) if self._current_piece_role() in roles else 0
        self.piece_palette_role = roles[(current + delta) % len(roles)]
        self.piece_palette_index = 0
        self.message = self._piece_palette_summary()

    def _cycle_piece_asset(self, delta: int) -> None:
        if self.selection is not None and self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            role = str(piece.get("role", self._current_piece_role()))
            options = self._piece_palette_options(role)
            if not options:
                self.message = f"No assets for role: {role}"
                return
            current_asset = str(piece.get("asset", ""))
            asset_ids = [_piece_asset_id(option) for option in options]
            current = asset_ids.index(current_asset) if current_asset in asset_ids else 0
            self._push_undo()
            piece["asset"] = asset_ids[(current + delta) % len(asset_ids)]
            self._invalidate_terrain_cache()
            self.dirty = True
            self.message = f"Piece asset: {piece['asset']}"
            return
        options = self._piece_palette_options()
        if not options:
            self.message = "No terrain piece assets"
            return
        self.piece_palette_index = (self.piece_palette_index + delta) % len(options)
        self.message = self._piece_palette_summary()

    def _cycle_palette(self, delta: int) -> None:
        self._move_palette_cursor(delta, 0)

    def _selected_enemy_event(self) -> dict[str, Any] | None:
        event = self._selected_event()
        if event is None or not _event_is_enemy(event):
            self.message = "Select an enemy event first"
            return None
        return event

    def _ensure_event_anchor_y(self, event: dict[str, Any]) -> None:
        if "y" in event or "anchor_y" in event or not _event_can_use_anchor_y(event):
            return
        wx = _event_x(event) or self.cursor_world.x
        event["anchor_y"] = int(round(self._event_anchor_y(event, wx)))

    def _cycle_selected_event_formation(self) -> None:
        event = self._selected_enemy_event()
        if event is None:
            return
        if event.get("surface") in {"top", "bottom"} and "y" not in event:
            self.message = "Surface enemy formation follows the terrain"
            return
        current = str(event.get("formation", "single"))
        index = FORMATION_ORDER.index(current) if current in FORMATION_ORDER else 0
        self._push_undo()
        event["formation"] = FORMATION_ORDER[(index + 1) % len(FORMATION_ORDER)]
        if event["formation"] != "single":
            event["count"] = max(2, int(event.get("count", 1)))
            self._ensure_event_anchor_y(event)
        else:
            event["count"] = 1
        self.dirty = True
        self.message = f"Enemy formation: {event['formation']}"

    def _adjust_selected_event_count(self, delta: int) -> None:
        event = self._selected_enemy_event()
        if event is None:
            return
        self._push_undo()
        count = max(1, min(12, int(event.get("count", 1)) + delta))
        event["count"] = count
        if event.get("surface") not in {"top", "bottom"} or "y" in event:
            if count > 1 and str(event.get("formation", "single")) in {"", "single"}:
                event["formation"] = "line"
            elif count == 1:
                event["formation"] = "single"
            self._ensure_event_anchor_y(event)
        self.dirty = True
        self.message = f"Enemy count: {count}"

    def _toggle_selected_event_enhanced(self) -> None:
        event = self._selected_enemy_event()
        if event is None:
            return
        self._push_undo()
        enabled = not bool(event.get("enhanced", False))
        if enabled:
            event["enhanced"] = True
        else:
            event.pop("enhanced", None)
        self.dirty = True
        self.message = f"Enemy enhanced: {enabled}"

    def _cycle_selected_piece_collision(self) -> None:
        piece = self._selected_piece()
        if piece is None:
            self.message = "Select a terrain piece first"
            return
        current = str(piece.get("collision", "auto"))
        index = PIECE_COLLISION_ORDER.index(current) if current in PIECE_COLLISION_ORDER else 0
        self._push_undo()
        piece["collision"] = PIECE_COLLISION_ORDER[(index + 1) % len(PIECE_COLLISION_ORDER)]
        self._invalidate_terrain_cache()
        self.dirty = True
        self.message = f"Piece collision: {piece['collision']}"

    def _cycle_selected_piece_side(self) -> None:
        piece = self._selected_piece()
        if piece is None:
            self.message = "Select a terrain piece first"
            return
        current = str(piece.get("side", "bottom"))
        index = PIECE_SIDE_ORDER.index(current) if current in PIECE_SIDE_ORDER else 0
        self._push_undo()
        piece["side"] = PIECE_SIDE_ORDER[(index + 1) % len(PIECE_SIDE_ORDER)]
        self._invalidate_terrain_cache()
        self.dirty = True
        self.message = f"Piece side: {piece['side']}"

    def _toggle_selected_piece_flip(self, axis: str) -> None:
        piece = self._selected_piece()
        if piece is None:
            self.message = "Select a terrain piece first"
            return
        key = f"flip_{axis}"
        self._push_undo()
        enabled = not bool(piece.get(key, False))
        if enabled:
            piece[key] = True
        else:
            piece.pop(key, None)
        self._invalidate_terrain_cache()
        self.dirty = True
        self.message = f"Piece {key}: {enabled}"

    def _move_selection(self, dx: float, dy: float) -> None:
        if self.selection is None:
            return
        self._push_undo()
        if self.selection.kind == "event":
            event = self._selected_event()
            if event is None:
                return
            if _event_x(event) is not None:
                _set_event_x(event, (_event_x(event) or 0.0) + dx)
            if _event_can_edit_y(event):
                _set_event_y(event, _event_y(event, self.data) + dy)
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            piece["x"] = int(round(float(piece.get("x", 0)) + dx))
            piece["y"] = int(round(float(piece.get("y", 0)) + dy))
            self._invalidate_terrain_cache()
        elif self.selection.kind == "guide_point":
            line = self._selected_guide_line()
            if line is None:
                return
            points = line.get("points", [])
            if not (0 <= self.selection.sub_index < len(points)):
                return
            point = points[self.selection.sub_index]
            point[0] = int(round(float(point[0]) + dx))
            point[1] = int(round(max(0.0, min(float(SCREEN_HEIGHT), float(point[1]) + dy))))
            line["points"] = _clean_guide_points(points)
            self.selection.sub_index = min(self.selection.sub_index, len(line["points"]) - 1)
        else:
            point = self._selected_point()
            if point is None:
                return
            point[0] = int(round(float(point[0]) + dx))
            point[1] = int(round(max(0.0, min(float(SCREEN_HEIGHT), float(point[1]) + dy))))
            self._invalidate_terrain_cache()
        self.dirty = True

    def _set_selection_world_pos(self, wx: float, wy: float) -> None:
        if self.selection is None:
            return
        if self.selection.kind == "event":
            event = self._selected_event()
            if event is None:
                return
            _set_event_x(event, wx - self.drag_offset.x)
            if _event_can_edit_y(event):
                _set_event_y(event, wy - self.drag_offset.y)
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            piece["x"] = int(round(wx - self.drag_offset.x))
            piece["y"] = int(round(wy - self.drag_offset.y))
            self._invalidate_terrain_cache()
        elif self.selection.kind == "guide_point":
            line = self._selected_guide_line()
            if line is None:
                return
            points = line.get("points", [])
            if not (0 <= self.selection.sub_index < len(points)):
                return
            points[self.selection.sub_index] = [
                int(round(wx - self.drag_offset.x)),
                int(round(max(0.0, min(float(SCREEN_HEIGHT), wy - self.drag_offset.y)))),
            ]
            line["points"] = _clean_guide_points(points)
            x = points[self.selection.sub_index][0] if 0 <= self.selection.sub_index < len(points) else None
            if x is not None:
                for i, point in enumerate(line["points"]):
                    if point[0] == x:
                        self.selection.sub_index = i
                        break
        else:
            point = self._selected_point()
            if point is None:
                return
            point[0] = int(round(wx - self.drag_offset.x))
            point[1] = int(round(max(0.0, min(float(SCREEN_HEIGHT), wy - self.drag_offset.y))))
            self._invalidate_terrain_cache()
        self.dirty = True

    def _save(self) -> None:
        _write_stage(self.stage_path, self.data)
        self.dirty = False
        self.message = f"Saved: {self.stage_path}"

    def _undo(self) -> None:
        if not self.undo_stack:
            self.message = "Nothing to undo"
            return
        self.data = self.undo_stack.pop()
        self.selection = None
        self.dirty = True
        self._invalidate_terrain_cache()
        self.message = "Undo"

    def _draw_label(self, target: pygame.Surface, text: str, pos: tuple[int, int], color: tuple[int, int, int] = (232, 238, 236)) -> int:
        image = self.font.render(text, True, color)
        bg = pygame.Rect(pos[0] - 4, pos[1] - 3, image.get_width() + 8, image.get_height() + 6)
        pygame.draw.rect(target, (5, 9, 12), bg)
        target.blit(image, pos)
        return image.get_height() + 7

    def _draw_wrapped_label(
        self,
        target: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        max_w: int,
        color: tuple[int, int, int] = (232, 238, 236),
    ) -> int:
        if not text:
            return self.font.get_height() + 5
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            candidate = word if not current else f"{current} {word}"
            if self.font.size(candidate)[0] <= max_w:
                current = candidate
                continue
            if current:
                lines.append(current)
            if self.font.size(word)[0] <= max_w:
                current = word
                continue
            chunk = ""
            for char in word:
                candidate = f"{chunk}{char}"
                if self.font.size(candidate)[0] > max_w and chunk:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = candidate
            current = chunk
        if current:
            lines.append(current)
        y = pos[1]
        total = 0
        for line in lines:
            advance = self._draw_label(target, line, (pos[0], y), color)
            y += advance
            total += advance
        return total

    def _draw_terrain_points(self, target: pygame.Surface) -> None:
        if not self.show_overlays:
            return
        layout = _layout(self.data)
        for side, color in (("top", POINT_TOP_COLOR), ("bottom", POINT_BOTTOM_COLOR)):
            points = layout.get(side, [])
            screen_points = []
            for i, point in enumerate(points):
                if not isinstance(point, list) or len(point) < 2:
                    continue
                sx, sy = self._world_to_screen(float(point[0]), float(point[1]))
                sy -= TOOLBAR_H
                screen_points.append((sx, sy))
                selected = self.selection == Selection("terrain", i, side)
                radius = 6 if selected else 4
                pygame.draw.circle(target, color, (sx, sy), radius)
                pygame.draw.circle(target, (8, 10, 12), (sx, sy), radius, 1)
            if len(screen_points) >= 2:
                pygame.draw.lines(target, color, False, screen_points, 1)

    def _draw_terrain_pieces(self, target: pygame.Surface) -> None:
        if not self.show_overlays:
            return
        composer_layout, _pieces = self._piece_layout()
        for i, placement in enumerate(composer_layout.placements):
            sx, sy = self._world_to_screen(float(placement.x), float(placement.y))
            rect = pygame.Rect(
                sx,
                sy - TOOLBAR_H,
                max(1, int(round(placement.image.get_width() * self.zoom))),
                max(1, int(round(placement.image.get_height() * self.zoom))),
            )
            if rect.right < 0 or rect.left > target.get_width():
                continue
            selected = self.selection == Selection("piece", i)
            color = POINT_BOTTOM_COLOR if placement.side == "bottom" else POINT_TOP_COLOR if placement.side == "top" else TERRAIN_COLOR
            pygame.draw.rect(target, color, rect, 2 if selected else 1)
            if selected:
                label = self.small_font.render(placement.asset or placement.role, True, color)
                target.blit(label, (rect.left, max(0, rect.top - 16)))

    def _draw_guides(self, target: pygame.Surface) -> None:
        if not self.show_overlays:
            return
        for line_i, line in enumerate(self._guide_lines()):
            side = "top" if line.get("side") == "top" else "bottom"
            color = POINT_TOP_COLOR if side == "top" else POINT_BOTTOM_COLOR
            selected_line = self.selection is not None and self.selection.kind in {"guide_line", "guide_point"} and self.selection.index == line_i
            points = _clean_guide_points(line.get("points", []))
            screen_points: list[tuple[int, int]] = []
            for point in points:
                sx, sy = self._world_to_screen(float(point[0]), float(point[1]))
                screen_points.append((sx, sy - TOOLBAR_H))
            if len(screen_points) >= 2:
                pygame.draw.lines(target, color, False, screen_points, 4 if selected_line else 2)
            for point_i, (sx, sy) in enumerate(screen_points):
                selected_point = selected_line and self.selection is not None and self.selection.kind == "guide_point" and self.selection.sub_index == point_i
                radius = 7 if selected_point else 6 if selected_line else 4
                pygame.draw.circle(target, color, (sx, sy), radius)
                pygame.draw.circle(target, (5, 10, 12), (sx, sy), radius, 2 if selected_point else 1)
            if screen_points and (selected_line or self.guide_mode):
                label = self.small_font.render(f"{side} guide {line_i + 1}", True, color)
                target.blit(label, (screen_points[0][0] + 8, max(0, screen_points[0][1] - 18)))

    def _draw_events(self, target: pygame.Surface) -> None:
        for i, event in enumerate(self.data.get("world_events", [])):
            color = _event_color(event)
            selected = self.selection == Selection("event", i)
            if event.get("type") == "BossGate":
                if not self.show_overlays:
                    continue
                world_rect = _event_rect(event, self.data, 0)
                sx, sy = self._world_to_screen(world_rect.x, world_rect.y)
                rect = pygame.Rect(
                    sx,
                    sy - TOOLBAR_H,
                    max(1, int(round(world_rect.width * self.zoom))),
                    max(1, int(round(world_rect.height * self.zoom))),
                )
                pygame.draw.line(target, color, (rect.centerx, 0), (rect.centerx, target.get_height()), 3 if selected else 1)
                label = self.small_font.render(str(event.get("type", "")), True, color)
                target.blit(label, (rect.left, 2))
                continue

            if event.get("type") in RECT_TERRAIN_TYPES:
                world_rect = _event_rect(event, self.data, 0)
                sx, sy = self._world_to_screen(world_rect.x, world_rect.y)
                rect = pygame.Rect(
                    sx,
                    sy - TOOLBAR_H,
                    max(1, int(round(world_rect.width * self.zoom))),
                    max(1, int(round(world_rect.height * self.zoom))),
                )
                preview = self._event_image(event, max_w=rect.width, max_h=rect.height)
                target.blit(preview, rect.topleft)
                if self.show_overlays:
                    fill = (*color, 42 if selected else 20)
                    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                    overlay.fill(fill)
                    target.blit(overlay, rect.topleft)
                    pygame.draw.rect(target, color, rect, 2 if selected else 1)
                if self.show_overlays and (selected or event.get("type") in {"weapon_gate", "breakable_gate"}):
                    label = self.small_font.render(str(event.get("type", "")), True, color)
                    target.blit(label, (rect.left, max(0, rect.top - 16)))
                continue

            positions = self._event_preview_positions(event)
            preview = self._event_image(event, max_w=max(18, int(58 * self.zoom)), max_h=max(18, int(52 * self.zoom)))
            drawn_rects: list[pygame.Rect] = []
            for j, (wx, wy) in enumerate(positions):
                sx, sy = self._world_to_screen(wx, wy)
                rect = preview.get_rect(center=(sx, sy - TOOLBAR_H))
                if rect.right < 0 or rect.left > target.get_width() or rect.bottom < 0 or rect.top > target.get_height():
                    continue
                image = preview if j == 0 else preview.copy()
                if j != 0:
                    image.set_alpha(150)
                target.blit(image, rect.topleft)
                drawn_rects.append(rect)
                if self.show_overlays and selected:
                    pygame.draw.rect(target, color, rect.inflate(4, 4), 1)
            if self.show_overlays and len(drawn_rects) >= 2:
                centers = [rect.center for rect in drawn_rects]
                pygame.draw.lines(target, (*color, 180), False, centers, 1)
            if self.show_overlays and drawn_rects and (selected or len(positions) > 1):
                group_rect = drawn_rects[0].unionall(drawn_rects[1:]) if len(drawn_rects) > 1 else drawn_rects[0]
                pygame.draw.rect(target, color, group_rect.inflate(8, 8), 2 if selected else 1)
                label = self.small_font.render(
                    f"{event.get('type', '')} x{max(1, int(event.get('count', 1)))}",
                    True,
                    color,
                )
                target.blit(label, (group_rect.left, max(0, group_rect.top - 16)))

    def _draw_minimap(self, target: pygame.Surface) -> None:
        length = _stage_length(self.data)
        x, y, w, h = 14, 12, 330, 14
        pygame.draw.rect(target, (24, 32, 36), (x, y, w, h))
        visible_w, _visible_h = self._visible_world_size()
        view_x = x + int((self.camera_x / max(1, length)) * w)
        view_w = max(12, int((visible_w / max(1, length)) * w))
        pygame.draw.rect(target, (90, 220, 190), (view_x, y, view_w, h))
        pygame.draw.rect(target, (138, 160, 166), (x, y, w, h), 1)

    def _selected_summary(self) -> list[str]:
        if self.selection is None:
            return ["No selection"]
        if self.selection.kind == "event":
            event = self._selected_event()
            if event is None:
                return ["No selection"]
            return [
                f"event #{self.selection.index + 1}",
                f"type: {event.get('type')}",
                f"x: {_event_x(event)}",
                f"y: {_event_y(event, self.data):.0f}",
                f"count: {event.get('count', 1)}",
                f"formation: {event.get('formation', '-')}",
                f"enhanced: {bool(event.get('enhanced', False))}",
                f"keys: {', '.join(str(key) for key in event.keys())}",
            ]
        if self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return ["No selection"]
            return [
                f"piece #{self.selection.index + 1}",
                f"asset: {piece.get('asset')}",
                f"role: {piece.get('role')}",
                f"x: {piece.get('x')}",
                f"y: {piece.get('y')}",
                f"collision: {piece.get('collision', 'auto')}",
            ]
        if self.selection.kind == "guide_line":
            line = self._selected_guide_line()
            if line is None:
                return ["No selection"]
            return [
                f"guide line #{self.selection.index + 1}",
                f"side: {line.get('side', 'bottom')}",
                f"points: {len(line.get('points', []))}",
            ]
        if self.selection.kind == "guide_point":
            line = self._selected_guide_line()
            if line is None:
                return ["No selection"]
            points = line.get("points", [])
            if not (0 <= self.selection.sub_index < len(points)):
                return ["No selection"]
            point = points[self.selection.sub_index]
            return [
                f"guide point #{self.selection.sub_index + 1}",
                f"line: {self.selection.index + 1}",
                f"side: {line.get('side', 'bottom')}",
                f"x: {point[0]}",
                f"y: {point[1]}",
            ]
        point = self._selected_point()
        if point is None:
            return ["No selection"]
        return [
            f"{self.selection.side} point #{self.selection.index + 1}",
            f"x: {point[0]}",
            f"y: {point[1]}",
        ]

    def _draw_palette_title(self, target: pygame.Surface, text: str, pos: tuple[int, int]) -> int:
        image = self.font.render(text, True, (225, 232, 230))
        target.blit(image, pos)
        return image.get_height() + 8

    def _draw_piece_cell(self, target: pygame.Surface, rect: pygame.Rect, role: str, piece: Any) -> None:
        asset = _piece_asset_id(piece)
        selected_piece = self._current_piece_asset()
        selected_asset = _piece_asset_id(selected_piece) if selected_piece is not None else ""
        selected = self.mode == "terrain" and role == self._current_piece_role() and asset == selected_asset
        color = (91, 232, 188) if selected else (72, 92, 96)
        pygame.draw.rect(target, (8, 12, 15), rect)
        pygame.draw.rect(target, color, rect, 2 if selected else 1)
        image = piece.image
        scale = min(1.0, (rect.width - 12) / max(1, image.get_width()), 44 / max(1, image.get_height()))
        if scale >= 1.0:
            preview = image
        else:
            preview_size = (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale)))
            if not hasattr(self, "_piece_preview_cache"):
                self._piece_preview_cache = {}
            cache_key = (asset, id(image), preview_size[0], preview_size[1])
            preview = self._piece_preview_cache.get(cache_key)
            if preview is None:
                preview = pygame.transform.smoothscale(image, preview_size)
                self._piece_preview_cache[cache_key] = preview
        target.blit(preview, (rect.x + 6, rect.y + 6))
        label = self.small_font.render(asset, True, (220, 232, 228))
        target.blit(label, (rect.x + 6, rect.bottom - 18))

    def _draw_event_cell(self, target: pygame.Surface, rect: pygame.Rect, index: int, name: str, template: dict[str, Any]) -> None:
        selected = self.mode == "events" and index == self.event_palette_index
        color = (255, 175, 98) if selected else _event_color(template)
        pygame.draw.rect(target, (8, 12, 15), rect)
        pygame.draw.rect(target, color, rect, 2 if selected else 1)
        if _event_material_role(template):
            preview = self._event_image(template, max_w=rect.width, max_h=rect.height)
            target.blit(preview, (rect.x + 7, rect.y + 6))
            label = self.small_font.render(name, True, (230, 235, 232))
            target.blit(label, (rect.x + 7, rect.y + 8 + preview.get_height()))
            type_label = self.small_font.render(str(template.get("type", "")), True, (160, 178, 178))
            target.blit(type_label, (rect.x + 7, rect.bottom - 18))
            return
        preview = self._event_image(template, max_w=28, max_h=28)
        target.blit(preview, (rect.x + 7, rect.y + 6))
        label = self.small_font.render(name, True, (230, 235, 232))
        target.blit(label, (rect.x + 36, rect.y + 9))
        type_label = self.small_font.render(str(template.get("type", "")), True, (160, 178, 178))
        target.blit(type_label, (rect.x + 7, rect.bottom - 18))

    def _event_palette_cell_height(self, template: dict[str, Any]) -> int:
        if not _event_material_role(template):
            return 58
        image = self._event_image(template, max_w=PALETTE_W, max_h=SCREEN_HEIGHT)
        return max(58, image.get_height() + 34)

    def _event_palette_rects(
        self,
        x0: int,
        y: int,
        cell_w: int,
        gap: int,
        cols: int,
    ) -> tuple[list[tuple[int, pygame.Rect]], int]:
        rects: list[tuple[int, pygame.Rect]] = []
        col = 0
        event_h = 58
        full_w = self.palette_rect.width - 24
        for i, (_name, template) in enumerate(self._event_templates()):
            if _event_material_role(template):
                if col:
                    y += event_h + gap
                    col = 0
                height = self._event_palette_cell_height(template)
                rects.append((i, pygame.Rect(x0, y, full_w, height)))
                y += height + gap
                continue
            rects.append((i, pygame.Rect(x0 + col * (cell_w + gap), y, cell_w, event_h)))
            col += 1
            if col >= cols:
                y += event_h + gap
                col = 0
        if col:
            y += event_h + gap
        return rects, y

    def _palette_content_rects(self) -> tuple[dict[tuple[Any, ...], pygame.Rect], float]:
        panel = self.palette_rect
        x0 = panel.left + 12
        y = panel.top + 12
        cols = PALETTE_COLS
        gap = 8
        cell_w = max(96, (panel.width - 24 - gap * (cols - 1)) // cols)
        title_h = self.font.get_height() + 8
        piece_h = 76
        rects: dict[tuple[Any, ...], pygame.Rect] = {}

        y += title_h
        event_rects, y = self._event_palette_rects(x0, y, cell_w, gap, cols)
        for i, rect in event_rects:
            payload = {"kind": "event", "template_index": i}
            rects[self._palette_payload_key(payload)] = rect
        y += 12

        y += title_h
        pieces = self._composer_pieces()
        for role in self._piece_roles(pieces):
            y += title_h
            options = self._piece_palette_options(role, pieces)
            for i, piece in enumerate(options):
                col = i % cols
                row = i // cols
                payload = {"kind": "piece", "role": role, "asset": _piece_asset_id(piece)}
                rects[self._palette_payload_key(payload)] = pygame.Rect(
                    x0 + col * (cell_w + gap),
                    y + row * (piece_h + gap),
                    cell_w,
                    piece_h,
                )
            y += ((len(options) + cols - 1) // cols) * (piece_h + gap) + 12
        return rects, float(y - panel.top)

    def _ensure_palette_payload_visible(self, payload: dict[str, Any]) -> None:
        rects, content_h = self._palette_content_rects()
        self.max_palette_scroll_y = max(0.0, float(content_h - self.palette_rect.height + 20))
        rect = rects.get(self._palette_payload_key(payload))
        if rect is None:
            return
        visible_top = self.palette_rect.top + 8
        visible_bottom = self.palette_rect.bottom - 8
        screen_top = rect.top - self.palette_scroll_y
        screen_bottom = rect.bottom - self.palette_scroll_y
        if screen_top < visible_top:
            self.palette_scroll_y = rect.top - visible_top
        elif screen_bottom > visible_bottom:
            self.palette_scroll_y = rect.bottom - visible_bottom
        self.palette_scroll_y = max(0.0, min(self.max_palette_scroll_y, self.palette_scroll_y))

    def _draw_palette(self, target: pygame.Surface) -> None:
        panel = self.palette_rect
        pygame.draw.rect(target, (13, 17, 21), panel)
        pygame.draw.line(target, (48, 60, 64), (panel.left, panel.top), (panel.left, panel.bottom))
        pygame.draw.line(target, (48, 60, 64), (panel.right - 1, panel.top), (panel.right - 1, panel.bottom))

        self._palette_hitboxes = []
        old_clip = target.get_clip()
        target.set_clip(panel)
        x0 = panel.left + 12
        y = panel.top + 12 - int(round(self.palette_scroll_y))
        cols = PALETTE_COLS
        gap = 8
        cell_w = max(96, (panel.width - 24 - gap * (cols - 1)) // cols)

        y += self._draw_palette_title(target, "Event Palette", (x0, y))
        event_rects, y_after_events = self._event_palette_rects(x0, y, cell_w, gap, cols)
        event_templates = self._event_templates()
        for i, rect in event_rects:
            if rect.colliderect(panel):
                name, template = event_templates[i]
                self._draw_event_cell(target, rect, i, name, template)
                self._palette_hitboxes.append((rect.copy(), {"kind": "event", "template_index": i}))
        y = y_after_events + 12

        y += self._draw_palette_title(target, "Terrain Pieces", (x0, y))
        piece_h = 76
        pieces = self._composer_pieces()
        for role in self._piece_roles(pieces):
            y += self._draw_palette_title(target, role, (x0, y))
            options = self._piece_palette_options(role, pieces)
            for i, piece in enumerate(options):
                col = i % cols
                row = i // cols
                rect = pygame.Rect(x0 + col * (cell_w + gap), y + row * (piece_h + gap), cell_w, piece_h)
                if rect.colliderect(panel):
                    self._draw_piece_cell(target, rect, role, piece)
                    self._palette_hitboxes.append((rect.copy(), {"kind": "piece", "role": role, "asset": _piece_asset_id(piece)}))
            y += ((len(options) + cols - 1) // cols) * (piece_h + gap) + 12

        target.set_clip(old_clip)
        content_h = y - panel.top + int(round(self.palette_scroll_y))
        self.max_palette_scroll_y = max(0.0, float(content_h - panel.height + 20))
        self.palette_scroll_y = max(0.0, min(self.max_palette_scroll_y, self.palette_scroll_y))
        if self.max_palette_scroll_y > 0:
            track = pygame.Rect(panel.right - 8, panel.top + 8, 4, panel.height - 16)
            thumb_h = max(24, int(track.height * (panel.height / max(panel.height, content_h))))
            thumb_y = track.y + int((track.height - thumb_h) * (self.palette_scroll_y / self.max_palette_scroll_y))
            pygame.draw.rect(target, (38, 48, 52), track)
            pygame.draw.rect(target, (104, 138, 136), (track.x, thumb_y, track.width, thumb_h))

    def _palette_payload_at(self, pos: tuple[int, int]) -> dict[str, Any] | None:
        for rect, payload in self._palette_hitboxes:
            if rect.collidepoint(pos):
                return payload
        return None

    def _select_palette_payload(self, payload: dict[str, Any]) -> None:
        if payload.get("kind") == "event":
            self.event_palette_index = int(payload.get("template_index", 0)) % len(self._event_templates())
            self.mode = "events"
            self.message = f"Event palette: {self._event_template_name(self.event_palette_index)}"
            self._ensure_palette_payload_visible(payload)
            return
        if payload.get("kind") == "piece":
            role = str(payload.get("role", self._current_piece_role()))
            asset = str(payload.get("asset", ""))
            self.piece_palette_role = role
            asset_ids = [_piece_asset_id(piece) for piece in self._piece_palette_options(role)]
            if asset in asset_ids:
                self.piece_palette_index = asset_ids.index(asset)
            self.mode = "terrain"
            self.message = self._piece_palette_summary()
            self._ensure_palette_payload_visible(payload)

    def _draw_info_panel(self, target: pygame.Surface) -> None:
        panel = self.info_rect
        pygame.draw.rect(target, (13, 17, 21), panel)
        pygame.draw.line(target, (48, 60, 64), (panel.left, panel.top), (panel.left, panel.bottom))
        y = panel.top + 12
        old_clip = target.get_clip()
        target.set_clip(panel.inflate(-4, -4))
        help_lines = [
            "Stage Designer",
            "Drag palette item onto stage",
            "Click stage item to select",
            "Arrows move palette/selection",
            "Enemy: V formation / +/- count / B enhanced",
            "G guide mode / U guide side",
            "Guide: click add/select",
            "P auto-fill selected guide",
            "Shift-drag axis lock",
            "Ctrl-drag copy",
            "O overlays on/off",
            "Ctrl+Wheel zoom",
            "Wheel pan stage/palette",
            "Del delete selection",
            "[ ] palette",
            "M collision / X side / F/Y flip",
            "S save / Ctrl+Z undo",
            "C capture / H help",
            "",
        ] if self.show_help else ["Stage Designer", "H help", ""]
        for line in [*help_lines, *self._palette_summary(), "", *self._selected_summary()]:
            y += self._draw_wrapped_label(target, line, (panel.left + 14, y), panel.width - 30, (225, 232, 230))
        target.set_clip(old_clip)

    def _draw_drag_preview(self, target: pygame.Surface) -> None:
        if not self.palette_drag:
            return
        pos = pygame.mouse.get_pos()
        payload = self.palette_drag
        if payload.get("kind") == "event":
            index = int(payload.get("template_index", 0))
            templates = self._event_templates()
            name = _event_template_name(index, templates)
            template = templates[index % len(templates)][1]
            if _event_material_role(template):
                preview = self._event_image(template, max_w=PALETTE_W, max_h=SCREEN_HEIGHT)
            else:
                preview = self._event_image(template, max_w=58, max_h=46)
            label = self.font.render(name, True, (255, 210, 150))
            bg = pygame.Rect(
                pos[0] + 12,
                pos[1] + 12,
                max(preview.get_width(), label.get_width()) + 12,
                preview.get_height() + label.get_height() + 14,
            )
            pygame.draw.rect(target, (8, 12, 15), bg)
            pygame.draw.rect(target, (255, 210, 150), bg, 1)
            target.blit(preview, (bg.x + 6, bg.y + 5))
            target.blit(label, (bg.x + 6, bg.y + preview.get_height() + 8))
            return
        role = str(payload.get("role", ""))
        asset = str(payload.get("asset", ""))
        for piece in self._piece_palette_options(role):
            if _piece_asset_id(piece) == asset:
                image = piece.image
                scale = min(1.0, 120 / max(1, image.get_width()), 80 / max(1, image.get_height()))
                preview = image if scale >= 1.0 else pygame.transform.smoothscale(
                    image,
                    (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale))),
                )
                target.blit(preview, (pos[0] + 12, pos[1] + 12))
                return

    def render(self) -> pygame.Surface:
        surface = pygame.Surface(self.screen.get_size())
        surface.fill((10, 13, 16))
        visible_w, visible_h = self._visible_world_size()
        crop_y = max(0, int(round(self.camera_y)))
        canvas_h = max(SCREEN_HEIGHT, crop_y + visible_h)
        world_view = self._load_backdrop(visible_w, canvas_h)
        layout = _layout(self.data)
        if layout.get("type") == "TerrainPieces":
            composer_layout, _pieces = self._piece_layout()
            draw_stage3_composer_layout(world_view, composer_layout, camera_x=self.camera_x)
        else:
            composer_layout = self._composer_layout()
            draw_stage3_composer_layout(world_view, composer_layout, camera_x=self.camera_x)
        crop = pygame.Rect(0, crop_y, visible_w, visible_h)
        view = pygame.Surface((visible_w, visible_h), pygame.SRCALPHA)
        view.blit(world_view, (0, max(0, int(round(-self.camera_y)))), crop)
        if self.zoom != 1.0:
            view = pygame.transform.smoothscale(view, (VIEW_W, VIEW_H))
        if layout.get("type") == "TerrainPieces":
            self._draw_terrain_pieces(view)
        else:
            self._draw_terrain_points(view)
        self._draw_guides(view)
        self._draw_events(view)
        surface.blit(view, self.view_rect.topleft)

        toolbar = surface.subsurface(pygame.Rect(0, 0, surface.get_width(), TOOLBAR_H))
        toolbar.fill((8, 12, 15))
        self._draw_minimap(toolbar)
        dirty = "*" if self.dirty else ""
        overlay = "on" if self.show_overlays else "off"
        self._draw_label(toolbar, f"{dirty} mode={self.mode} x={int(self.camera_x)} z={self.zoom:.2f} O={overlay}", (360, 10), (220, 235, 230))
        self._draw_label(toolbar, self.message, (640, 10), (220, 235, 230))

        self._draw_palette(surface)
        self._draw_info_panel(surface)
        self._draw_drag_preview(surface)
        return surface

    def draw(self) -> None:
        self.screen.blit(self.render(), (0, 0))
        pygame.display.flip()

    def capture(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.render(), str(path))
        self.message = f"Captured: {path}"
        return path

    def _handle_key(self, event: pygame.event.Event) -> bool:
        mods = pygame.key.get_mods()
        typed = str(getattr(event, "unicode", ""))
        step = 10 if mods & pygame.KMOD_CTRL else 1
        if event.key == pygame.K_ESCAPE:
            return False
        if event.key == pygame.K_e:
            self.mode = "events"
            self.selection = None
            self.message = "Mode: events"
        elif event.key == pygame.K_t:
            self.mode = "terrain"
            self.selection = None
            self.message = "Mode: terrain"
        elif event.key == pygame.K_s:
            self._save()
        elif event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
            self._undo()
        elif event.key == pygame.K_c:
            path = ROOT / "captures" / "stage_designer_capture.png"
            self.capture(path)
        elif event.key == pygame.K_h:
            self.show_help = not self.show_help
        elif event.key == pygame.K_o:
            self.show_overlays = not self.show_overlays
            self.message = "Overlays: on" if self.show_overlays else "Overlays: off"
        elif event.key == pygame.K_v:
            self._cycle_selected_event_formation()
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS) or typed == "+":
            self._adjust_selected_event_count(1)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS) or typed == "-":
            self._adjust_selected_event_count(-1)
        elif event.key == pygame.K_b:
            self._toggle_selected_event_enhanced()
        elif event.key == pygame.K_g:
            self.guide_mode = not self.guide_mode
            self.selection = None
            self.message = "Guide mode: on" if self.guide_mode else "Guide mode: off"
        elif event.key == pygame.K_u:
            self._toggle_selected_guide_side()
        elif event.key == pygame.K_p:
            self._auto_fill_from_guides()
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self._delete_selection()
        elif event.key == pygame.K_LEFTBRACKET:
            self._cycle_palette(-1)
        elif event.key == pygame.K_RIGHTBRACKET:
            self._cycle_palette(1)
        elif event.key == pygame.K_m:
            self._cycle_selected_piece_collision()
        elif event.key == pygame.K_x:
            self._cycle_selected_piece_side()
        elif event.key == pygame.K_f:
            if self.selection is not None and self.selection.kind == "piece":
                self._toggle_selected_piece_flip("x")
        elif event.key == pygame.K_y:
            if self.selection is not None and self.selection.kind == "piece":
                self._toggle_selected_piece_flip("y")
        elif event.key == pygame.K_LEFT:
            if self.selection is not None:
                self._move_selection(-step, 0)
            else:
                self._move_palette_cursor(-1, 0)
        elif event.key == pygame.K_RIGHT:
            if self.selection is not None:
                self._move_selection(step, 0)
            else:
                self._move_palette_cursor(1, 0)
        elif event.key == pygame.K_UP:
            if self.selection is not None:
                self._move_selection(0, -step)
            else:
                self._move_palette_cursor(0, -1)
        elif event.key == pygame.K_DOWN:
            if self.selection is not None:
                self._move_selection(0, step)
            else:
                self._move_palette_cursor(0, 1)
        elif event.key == pygame.K_a:
            self._pan_camera(-(90 if mods & pygame.KMOD_CTRL else 24))
        elif event.key == pygame.K_d:
            self._pan_camera(90 if mods & pygame.KMOD_CTRL else 24)
        elif event.key == pygame.K_PAGEUP:
            self._pan_camera(-VIEW_W * 0.75)
        elif event.key == pygame.K_PAGEDOWN:
            self._pan_camera(VIEW_W * 0.75)
        elif event.key == pygame.K_HOME:
            self.camera_x = 0.0
            self.camera_y = 0.0
        elif event.key == pygame.K_END:
            visible_w, _visible_h = self._visible_world_size()
            self.camera_x = float(_stage_length(self.data) - visible_w)
            self._clamp_camera()
        return True

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        self._update_cursor_world(event.pos)
        if event.button == 1 and self.palette_rect.collidepoint(event.pos):
            payload = self._palette_payload_at(event.pos)
            if payload is not None:
                self._select_palette_payload(payload)
                self.palette_drag = copy.deepcopy(payload)
            return
        if event.button in (2, 3):
            self.panning = True
            self.pan_anchor = pygame.Vector2(event.pos)
            self.pan_camera_x = self.camera_x
            self.pan_camera_y = self.camera_y
            return
        if event.button != 1:
            return
        if self.guide_mode and self.view_rect.collidepoint(event.pos):
            self._handle_guide_mouse_down(event.pos)
            return
        self._select_at(event.pos)
        if self.selection is None:
            return
        wx, wy = self._screen_to_world(event.pos)
        copied_for_drag = False
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            self._duplicate_selection(offset=False)
            copied_for_drag = True
        if self.selection.kind == "event":
            event_obj = self._selected_event()
            if event_obj is None:
                return
            event_x = _event_x(event_obj) or wx
            event_y = self._event_anchor_y(event_obj, event_x)
            self.drag_offset.xy = (0.0, 0.0) if copied_for_drag else (wx - event_x, wy - event_y)
            self.drag_start_world.xy = (wx, event_y if copied_for_drag else wy)
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            piece_x = float(piece.get("x", 0))
            piece_y = float(piece.get("y", 0))
            self.drag_offset.xy = (0.0, 0.0) if copied_for_drag else (wx - piece_x, wy - piece_y)
            self.drag_start_world.xy = (wx, piece_y if copied_for_drag else wy)
        else:
            point = self._selected_point()
            if point is None:
                return
            self.drag_offset.xy = (wx - float(point[0]), wy - float(point[1]))
            self.drag_start_world.xy = (wx, wy)
        if not copied_for_drag:
            self._push_undo()
        self.dragging = True

    def _handle_guide_mouse_down(self, pos: tuple[int, int]) -> None:
        point_selection = self._guide_point_at(pos)
        if point_selection is not None:
            self.selection = point_selection
            line = self._selected_guide_line()
            if line is None:
                return
            points = line.get("points", [])
            if not (0 <= point_selection.sub_index < len(points)):
                return
            point = points[point_selection.sub_index]
            wx, wy = self._screen_to_world(pos)
            self.drag_offset.xy = (wx - float(point[0]), wy - float(point[1]))
            self.drag_start_world.xy = (wx, wy)
            self._push_undo()
            self.dragging = True
            self.message = f"Selected guide point #{point_selection.sub_index + 1}"
            return

        line_selection = self._guide_line_at(pos)
        if line_selection is not None:
            self.selection = line_selection
            line = self._selected_guide_line()
            side = str(line.get("side", "bottom")) if line else "bottom"
            self.guide_side = side
            self.message = f"Selected {side} guide line #{line_selection.index + 1}"
            return

        wx, wy = self._screen_to_world(pos)
        line_index = self._selected_guide_line_index()
        if line_index is None:
            self._create_guide_line(wx, wy)
        else:
            self._add_guide_point_to_line(line_index, wx, wy)

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        self._update_cursor_world(event.pos)
        if self.panning:
            dx = pygame.Vector2(event.pos).x - self.pan_anchor.x
            dy = pygame.Vector2(event.pos).y - self.pan_anchor.y
            self.camera_x = self.pan_camera_x - dx / self.zoom
            self.camera_y = self.pan_camera_y - dy / self.zoom
            self._clamp_camera()
            return
        if self.palette_drag is not None:
            return
        if self.dragging and self.selection is not None:
            wx, wy = self._screen_to_world(event.pos)
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                dx = wx - self.drag_start_world.x
                dy = wy - self.drag_start_world.y
                if abs(dx) >= abs(dy):
                    wy = self.drag_start_world.y
                else:
                    wx = self.drag_start_world.x
            self._set_selection_world_pos(wx, wy)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button in (2, 3):
            self.panning = False
        if event.button == 1:
            if self.palette_drag is not None:
                if self.view_rect.collidepoint(event.pos):
                    wx, wy = self._screen_to_world(event.pos)
                    self._add_palette_payload_at(self.palette_drag, wx, wy)
                self.palette_drag = None
            self.dragging = False

    def _handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (max(MIN_WINDOW_W, event.w), max(MIN_WINDOW_H, event.h)),
                pygame.RESIZABLE,
            )
        elif event.type == pygame.MOUSEWHEEL:
            mouse_pos = tuple(int(v) for v in self.last_mouse_pos)
            mods = pygame.key.get_mods()
            wheel_x = float(getattr(event, "precise_x", event.x))
            wheel_y = float(getattr(event, "precise_y", event.y))
            if mods & pygame.KMOD_CTRL and wheel_y != 0 and self.view_rect.collidepoint(mouse_pos):
                factor = 1.12 if wheel_y > 0 else 1 / 1.12
                self._set_zoom(self.zoom * factor, mouse_pos)
            elif self.palette_rect.collidepoint(mouse_pos):
                self.palette_scroll_y = max(0.0, min(self.max_palette_scroll_y, self.palette_scroll_y - wheel_y * 80))
            elif self.view_rect.collidepoint(mouse_pos):
                self._pan_camera(wheel_x * 90, -wheel_y * 90)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(event)
        elif event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        return True

    def run(self) -> int:
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                running = self._handle_event(event)
                if not running:
                    break
            self.draw()
            clock.tick(60)
        return 0


def _open_file(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        print(f"[stage-designer] open failed: {exc}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, choices=sorted(STAGE_PROFILES), default=None, help="stage profile to edit")
    parser.add_argument("--stage-json", default=None, help="stage JSON to edit (defaults to selected stage)")
    parser.add_argument("--rects", default=None, help="terrain rect config (defaults to selected stage)")
    parser.add_argument("--mask-dir", default=None, help="terrain alpha mask directory (defaults to selected stage)")
    parser.add_argument("--background", default=None, help="background image for the designer canvas")
    parser.add_argument("--x", type=float, default=0.0, help="initial camera x")
    parser.add_argument("--mode", choices=("events", "terrain"), default="events", help="initial editor mode")
    parser.add_argument("--window-w", type=int, default=MIN_WINDOW_W)
    parser.add_argument("--window-h", type=int, default=MIN_WINDOW_H)
    parser.add_argument("--capture", default=None, help="render one PNG and exit")
    parser.add_argument("--open", action="store_true", help="open captured PNG")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pygame.init()
    pygame.font.init()
    try:
        designer = StageDesigner(args)
        if args.capture:
            path = designer.capture(_resolve(args.capture))
            print(path)
            if args.open:
                _open_file(path)
            return 0
        return designer.run()
    except Exception as exc:
        print(f"[stage-designer] error: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
