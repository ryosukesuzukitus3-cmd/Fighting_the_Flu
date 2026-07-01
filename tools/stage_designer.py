"""Interactive stage layout designer for authored stage JSON.

The first target is Stage3, where both the route shape and world_events are
authored by hand. The tool edits the JSON directly while keeping the file in a
compact, reviewable layout.
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
    build_stage3_piece_layout,
    load_stage3_composer_pieces,
    render_stage3_composer_surface,
    render_stage3_piece_surface,
)
from src.entities.terrain import make_terrain_segments_from_event  # noqa: E402

try:  # noqa: E402
    from stage3_alpha_mask_common import DEFAULT_MASK_DIR
except ModuleNotFoundError:  # noqa: E402
    from tools.stage3_alpha_mask_common import DEFAULT_MASK_DIR

DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"

VIEW_W = SCREEN_WIDTH
VIEW_H = SCREEN_HEIGHT
TOOLBAR_H = 48
PANEL_W = 390
MIN_WINDOW_W = VIEW_W + PANEL_W
MIN_WINDOW_H = VIEW_H + TOOLBAR_H

RECT_TERRAIN_TYPES = {"Terrain", "solid", "platform", "gate", "breakable_gate", "weapon_gate", "turret_mount"}
TERRAIN_LAYOUT_TYPES = {"AuthoredTerrain", "TerrainPath", "TerrainStrip", "TerrainPieces"}
ENEMY_COLOR = (255, 92, 108)
TERRAIN_COLOR = (255, 190, 88)
GATE_COLOR = (92, 225, 255)
BOSS_COLOR = (210, 130, 255)
POINT_TOP_COLOR = (255, 112, 112)
POINT_BOTTOM_COLOR = (92, 255, 176)


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
    event["y"] = int(round(max(0.0, min(float(SCREEN_HEIGHT), value))))


def _event_color(event: dict[str, Any]) -> tuple[int, int, int]:
    t = str(event.get("type", ""))
    if t == "Boss" or t == "BossGate":
        return BOSS_COLOR
    if t in {"breakable_gate", "weapon_gate"}:
        return GATE_COLOR
    if t in RECT_TERRAIN_TYPES:
        return TERRAIN_COLOR
    return ENEMY_COLOR


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


class StageDesigner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.stage_path = _resolve(args.stage_json)
        self.rects_path = _resolve(args.rects)
        self.mask_dir = _resolve(args.mask_dir)
        self.data = _load_stage(self.stage_path)
        self.screen = pygame.display.set_mode(
            (max(MIN_WINDOW_W, args.window_w), max(MIN_WINDOW_H, args.window_h)),
            pygame.RESIZABLE,
        )
        pygame.display.set_caption("Stage designer")
        self.font = pygame.font.SysFont("consolas", 16) or pygame.font.Font(None, 16)
        self.small_font = pygame.font.SysFont("consolas", 13) or pygame.font.Font(None, 13)
        self.camera_x = float(args.x)
        self.mode = str(args.mode)
        self.selection: Selection | None = None
        self.show_help = True
        self.dragging = False
        self.drag_offset = pygame.Vector2(0, 0)
        self.panning = False
        self.pan_anchor = pygame.Vector2(0, 0)
        self.pan_camera_x = self.camera_x
        self.message = "Ready"
        self.dirty = False
        self.undo_stack: list[dict[str, Any]] = []
        self._terrain_cache_key: str | None = None
        self._terrain_cache: tuple[list[Any], dict[str, list[Any]]] | None = None

    @property
    def view_rect(self) -> pygame.Rect:
        return pygame.Rect(0, TOOLBAR_H, VIEW_W, VIEW_H)

    def _push_undo(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.data))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)

    def _invalidate_terrain_cache(self) -> None:
        self._terrain_cache_key = None
        self._terrain_cache = None

    def _terrain(self) -> tuple[list[Any], dict[str, list[Any]]]:
        key = json.dumps(_layout(self.data), sort_keys=True, ensure_ascii=False)
        if self._terrain_cache is not None and self._terrain_cache_key == key:
            return self._terrain_cache
        start_x = float(_layout(self.data).get("start_offset", 0))
        segments = make_terrain_segments_from_event(_layout(self.data), start_x, default_seed=int(self.data.get("stage_id", 3)))
        pieces = load_stage3_composer_pieces(self.rects_path, mask_dir=self.mask_dir)
        self._terrain_cache_key = key
        self._terrain_cache = (segments, pieces)
        return self._terrain_cache

    def _piece_layout(self) -> tuple[Stage3ComposerLayout, dict[str, list[Any]]]:
        layout = _layout(self.data)
        key = "pieces:" + json.dumps(layout, sort_keys=True, ensure_ascii=False)
        if self._terrain_cache is not None and self._terrain_cache_key == key:
            return self._terrain_cache
        pieces = load_stage3_composer_pieces(self.rects_path, mask_dir=self.mask_dir)
        composer_layout = build_stage3_piece_layout(
            layout,
            pieces,
            start_x=_layout_start_x(layout),
            collision_step=int(layout.get("composer_collision_step", 8)),
            collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
        )
        self._terrain_cache_key = key
        self._terrain_cache = (composer_layout, pieces)
        return self._terrain_cache

    def _load_backdrop(self) -> pygame.Surface:
        surface = pygame.Surface((VIEW_W, VIEW_H))
        surface.fill((6, 14, 17))
        try:
            raw = pygame.image.load(str(BACKGROUND_PATH))
        except (FileNotFoundError, pygame.error):
            return surface
        scale = max(VIEW_W / raw.get_width(), VIEW_H / raw.get_height())
        scaled = pygame.transform.smoothscale(
            raw,
            (max(VIEW_W, int(raw.get_width() * scale)), max(VIEW_H, int(raw.get_height() * scale))),
        )
        surface.blit(scaled, ((VIEW_W - scaled.get_width()) // 2, (VIEW_H - scaled.get_height()) // 2))
        veil = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        veil.fill((0, 4, 6, 90))
        surface.blit(veil, (0, 0))
        return surface

    def _world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        return int(round(x - self.camera_x)), int(round(y + TOOLBAR_H))

    def _screen_to_world(self, pos: tuple[int, int]) -> tuple[float, float]:
        return float(pos[0]) + self.camera_x, float(pos[1] - TOOLBAR_H)

    def _clamp_camera(self) -> None:
        max_x = max(0, _stage_length(self.data) - VIEW_W)
        self.camera_x = max(-180.0, min(float(max_x + 180), self.camera_x))

    def _event_at(self, pos: tuple[int, int]) -> int | None:
        vx, vy = pos[0], pos[1] - TOOLBAR_H
        best: tuple[int, float] | None = None
        for i, event in enumerate(self.data.get("world_events", [])):
            rect = _event_rect(event, self.data, self.camera_x).inflate(10, 10)
            if rect.collidepoint(vx, vy):
                dist = (rect.centerx - vx) ** 2 + (rect.centery - vy) ** 2
                if best is None or dist < best[1]:
                    best = (i, dist)
        return None if best is None else best[0]

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
        vx, vy = pos[0], pos[1] - TOOLBAR_H
        composer_layout, _pieces = self._piece_layout()
        best: tuple[Selection, float] | None = None
        for i, placement in enumerate(composer_layout.placements):
            rect = pygame.Rect(
                int(round(placement.x - self.camera_x)),
                placement.y,
                placement.image.get_width(),
                placement.image.get_height(),
            ).inflate(6, 6)
            if rect.collidepoint(vx, vy):
                dist = (rect.centerx - vx) ** 2 + (rect.centery - vy) ** 2
                if best is None or dist < best[1]:
                    best = (Selection("piece", i), dist)
        return None if best is None else best[0]

    def _select_at(self, pos: tuple[int, int]) -> None:
        self.selection = None
        if not self.view_rect.collidepoint(pos):
            return
        if self.mode == "terrain":
            if _layout(self.data).get("type") == "TerrainPieces":
                self.selection = self._terrain_piece_at(pos)
                if self.selection is not None:
                    self.message = f"Selected terrain piece #{self.selection.index + 1}"
                return
            self.selection = self._terrain_point_at(pos)
            if self.selection is not None:
                self.message = f"Selected {self.selection.side} point #{self.selection.index + 1}"
            return
        index = self._event_at(pos)
        if index is not None:
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
            _set_event_y(event, _event_y(event, self.data) + dy)
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            piece["x"] = int(round(float(piece.get("x", 0)) + dx))
            piece["y"] = int(round(float(piece.get("y", 0)) + dy))
            self._invalidate_terrain_cache()
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
            _set_event_y(event, wy - self.drag_offset.y)
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            piece["x"] = int(round(wx - self.drag_offset.x))
            piece["y"] = int(round(wy - self.drag_offset.y))
            self._invalidate_terrain_cache()
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

    def _draw_terrain_points(self, target: pygame.Surface) -> None:
        layout = _layout(self.data)
        for side, color in (("top", POINT_TOP_COLOR), ("bottom", POINT_BOTTOM_COLOR)):
            points = layout.get(side, [])
            screen_points = []
            for i, point in enumerate(points):
                if not isinstance(point, list) or len(point) < 2:
                    continue
                sx, sy = int(round(float(point[0]) - self.camera_x)), int(round(float(point[1])))
                screen_points.append((sx, sy))
                selected = self.selection == Selection("terrain", i, side)
                radius = 6 if selected else 4
                pygame.draw.circle(target, color, (sx, sy), radius)
                pygame.draw.circle(target, (8, 10, 12), (sx, sy), radius, 1)
            if len(screen_points) >= 2:
                pygame.draw.lines(target, color, False, screen_points, 1)

    def _draw_terrain_pieces(self, target: pygame.Surface) -> None:
        composer_layout, _pieces = self._piece_layout()
        for i, placement in enumerate(composer_layout.placements):
            rect = pygame.Rect(
                int(round(placement.x - self.camera_x)),
                placement.y,
                placement.image.get_width(),
                placement.image.get_height(),
            )
            if rect.right < 0 or rect.left > VIEW_W:
                continue
            selected = self.selection == Selection("piece", i)
            color = POINT_BOTTOM_COLOR if placement.side == "bottom" else POINT_TOP_COLOR if placement.side == "top" else TERRAIN_COLOR
            pygame.draw.rect(target, color, rect, 2 if selected else 1)
            if selected:
                label = self.small_font.render(placement.asset or placement.role, True, color)
                target.blit(label, (rect.left, max(0, rect.top - 16)))

    def _draw_events(self, target: pygame.Surface) -> None:
        for i, event in enumerate(self.data.get("world_events", [])):
            rect = _event_rect(event, self.data, self.camera_x)
            color = _event_color(event)
            selected = self.selection == Selection("event", i)
            if event.get("type") == "BossGate":
                pygame.draw.line(target, color, (rect.centerx, 0), (rect.centerx, VIEW_H), 3 if selected else 1)
            elif event.get("type") in RECT_TERRAIN_TYPES:
                fill = (*color, 55 if selected else 32)
                overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                overlay.fill(fill)
                target.blit(overlay, rect.topleft)
                pygame.draw.rect(target, color, rect, 2 if selected else 1)
            else:
                pygame.draw.ellipse(target, (*color, 92), rect)
                pygame.draw.ellipse(target, color, rect, 3 if selected else 1)
            if selected or event.get("type") in {"Boss", "BossGate", "weapon_gate", "breakable_gate"}:
                label = self.small_font.render(str(event.get("type", "")), True, color)
                target.blit(label, (rect.left, max(0, rect.top - 16)))

    def _draw_minimap(self, target: pygame.Surface) -> None:
        length = _stage_length(self.data)
        x, y, w, h = 14, 12, 330, 14
        pygame.draw.rect(target, (24, 32, 36), (x, y, w, h))
        view_x = x + int((self.camera_x / max(1, length)) * w)
        view_w = max(12, int((VIEW_W / max(1, length)) * w))
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
                f"keys: {', '.join(event.keys())}",
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
        point = self._selected_point()
        if point is None:
            return ["No selection"]
        return [
            f"{self.selection.side} point #{self.selection.index + 1}",
            f"x: {point[0]}",
            f"y: {point[1]}",
        ]

    def render(self) -> pygame.Surface:
        surface = pygame.Surface(self.screen.get_size())
        surface.fill((10, 13, 16))
        view = self._load_backdrop()
        layout = _layout(self.data)
        if layout.get("type") == "TerrainPieces":
            _composer_layout, pieces = self._piece_layout()
            render_stage3_piece_surface(
                view,
                layout,
                pieces,
                camera_x=self.camera_x,
                start_x=_layout_start_x(layout),
                collision_step=int(layout.get("composer_collision_step", 8)),
                collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
            )
            if self.mode == "terrain":
                self._draw_terrain_pieces(view)
        else:
            segments, pieces = self._terrain()
            render_stage3_composer_surface(
                view,
                segments,
                pieces,
                camera_x=self.camera_x,
                sample_step=int(layout.get("composer_sample_step", 48)),
                tolerance=int(layout.get("composer_tolerance", 26)),
                collision_step=int(layout.get("composer_collision_step", 8)),
                collision_tolerance=int(layout.get("composer_collision_tolerance", 10)),
                overlap=int(layout.get("composer_overlap", 0)),
            )
            self._draw_terrain_points(view)
        self._draw_events(view)
        surface.blit(view, self.view_rect.topleft)

        toolbar = surface.subsurface(pygame.Rect(0, 0, surface.get_width(), TOOLBAR_H))
        toolbar.fill((8, 12, 15))
        self._draw_minimap(toolbar)
        dirty = "*" if self.dirty else ""
        self._draw_label(toolbar, f"{dirty} mode={self.mode} x={int(self.camera_x)}", (360, 10), (220, 235, 230))
        self._draw_label(toolbar, self.message, (540, 10), (220, 235, 230))

        panel = pygame.Rect(VIEW_W, TOOLBAR_H, max(0, surface.get_width() - VIEW_W), VIEW_H)
        pygame.draw.rect(surface, (13, 17, 21), panel)
        pygame.draw.line(surface, (48, 60, 64), (panel.left, panel.top), (panel.left, panel.bottom))
        y = panel.top + 12
        help_lines = [
            "Stage Designer",
            "E events / T terrain/pieces",
            "Drag selected item",
            "Arrows move (Ctrl=10)",
            "A/D or wheel pan",
            "S save / Ctrl+Z undo",
            "C capture / H help",
            "",
        ] if self.show_help else ["Stage Designer", "H help", ""]
        for line in [*help_lines, *self._selected_summary()]:
            y += self._draw_label(surface, line, (panel.left + 14, y), (225, 232, 230))
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
        elif event.key == pygame.K_LEFT:
            self._move_selection(-step, 0)
        elif event.key == pygame.K_RIGHT:
            self._move_selection(step, 0)
        elif event.key == pygame.K_UP:
            self._move_selection(0, -step)
        elif event.key == pygame.K_DOWN:
            self._move_selection(0, step)
        elif event.key == pygame.K_a:
            self.camera_x -= 90 if mods & pygame.KMOD_CTRL else 24
            self._clamp_camera()
        elif event.key == pygame.K_d:
            self.camera_x += 90 if mods & pygame.KMOD_CTRL else 24
            self._clamp_camera()
        elif event.key == pygame.K_PAGEUP:
            self.camera_x -= VIEW_W * 0.75
            self._clamp_camera()
        elif event.key == pygame.K_PAGEDOWN:
            self.camera_x += VIEW_W * 0.75
            self._clamp_camera()
        elif event.key == pygame.K_HOME:
            self.camera_x = 0.0
        elif event.key == pygame.K_END:
            self.camera_x = float(_stage_length(self.data) - VIEW_W)
            self._clamp_camera()
        return True

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button in (2, 3):
            self.panning = True
            self.pan_anchor = pygame.Vector2(event.pos)
            self.pan_camera_x = self.camera_x
            return
        if event.button != 1:
            return
        self._select_at(event.pos)
        if self.selection is None:
            return
        wx, wy = self._screen_to_world(event.pos)
        if self.selection.kind == "event":
            event_obj = self._selected_event()
            if event_obj is None:
                return
            self.drag_offset.xy = (wx - (_event_x(event_obj) or wx), wy - _event_y(event_obj, self.data))
        elif self.selection.kind == "piece":
            piece = self._selected_piece()
            if piece is None:
                return
            self.drag_offset.xy = (wx - float(piece.get("x", 0)), wy - float(piece.get("y", 0)))
        else:
            point = self._selected_point()
            if point is None:
                return
            self.drag_offset.xy = (wx - float(point[0]), wy - float(point[1]))
        self._push_undo()
        self.dragging = True

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.panning:
            dx = pygame.Vector2(event.pos).x - self.pan_anchor.x
            self.camera_x = self.pan_camera_x - dx
            self._clamp_camera()
            return
        if self.dragging and self.selection is not None:
            wx, wy = self._screen_to_world(event.pos)
            self._set_selection_world_pos(wx, wy)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button in (2, 3):
            self.panning = False
        if event.button == 1:
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
            self.camera_x -= event.y * 90
            self._clamp_camera()
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
    parser.add_argument("--stage-json", default=str(DEFAULT_STAGE), help="stage JSON to edit")
    parser.add_argument("--rects", default=str(DEFAULT_RECTS), help="Stage3 rect config")
    parser.add_argument("--mask-dir", default=str(DEFAULT_MASK_DIR), help="Stage3 alpha mask directory")
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
