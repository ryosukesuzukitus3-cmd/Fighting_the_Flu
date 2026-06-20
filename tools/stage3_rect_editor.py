"""Interactive editor for Stage3 terrain source rects.

Controls:
  Left drag        add a rect to the active group
  Left click       select an existing rect in the active group
  Drag selected edge/corner
                   resize the selected rect
  Right/Middle drag pan
  Mouse wheel      zoom around cursor
  1..9             switch active group
  Tab / Shift+Tab  switch active group
  Arrow keys       move selected rect by 1px (Ctrl = 10px)
  Shift+Arrows     resize selected rect by 1px (Ctrl = 10px)
  Delete           delete selected rect
  S                save JSON
  U or Ctrl+Z      undo
  A                toggle dim mode (active group / selected rect)
  B                toggle 1px outside boundary outline
  H                toggle help
  Esc              quit
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import pygame

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "tools" / "stage3_terrain_rects.json"
PALETTE = (
    (255, 91, 91),
    (255, 190, 64),
    (64, 210, 255),
    (145, 255, 115),
    (210, 120, 255),
    (255, 138, 218),
    (120, 190, 255),
)


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("groups"), dict):
        raise ValueError("config must contain object key: groups")
    return data


def _normalize_rect(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {
            "x": int(raw["x"]),
            "y": int(raw["y"]),
            "w": int(raw["w"]),
            "h": int(raw["h"]),
            **({"label": str(raw["label"])} if raw.get("label") else {}),
        }
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        rect = {"x": int(raw[0]), "y": int(raw[1]), "w": int(raw[2]), "h": int(raw[3])}
        if len(raw) >= 5 and raw[4]:
            rect["label"] = str(raw[4])
        return rect
    raise ValueError("rect must be {x,y,w,h} or [x,y,w,h]")


def _group_names(data: dict[str, Any]) -> list[str]:
    return list(data["groups"].keys())


def _ensure_group(data: dict[str, Any], name: str) -> dict[str, Any]:
    groups = data["groups"]
    if name not in groups:
        raise ValueError(f"unknown group: {name}")
    value = groups[name]
    group_index = _group_names(data).index(name)
    if isinstance(value, list):
        value = {"color": list(PALETTE[group_index % len(PALETTE)]), "rects": value}
        groups[name] = value
    if not isinstance(value, dict):
        raise ValueError(f"group must be object or list: {name}")
    value.setdefault("color", list(PALETTE[group_index % len(PALETTE)]))
    rects = value.setdefault("rects", [])
    if not isinstance(rects, list):
        raise ValueError(f"{name}.rects must be a list")
    value["rects"] = [_normalize_rect(rect) for rect in rects]
    return value


def _rects(data: dict[str, Any], group: str) -> list[dict[str, Any]]:
    return _ensure_group(data, group)["rects"]


def _group_color(data: dict[str, Any], group: str) -> tuple[int, int, int]:
    raw = _ensure_group(data, group).get("color", (255, 255, 255))
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        return (255, 255, 255)
    return tuple(max(0, min(255, int(v))) for v in raw[:3])


def _rect_to_pygame(rect: dict[str, Any]) -> pygame.Rect:
    return pygame.Rect(int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"]))


def _rect_dict(rect: pygame.Rect) -> dict[str, int]:
    return {"x": int(rect.x), "y": int(rect.y), "w": int(rect.w), "h": int(rect.h)}


def _clamp_rect(rect: pygame.Rect, sheet: pygame.Surface) -> pygame.Rect:
    bounds = pygame.Rect(0, 0, *sheet.get_size())
    rect = rect.copy()
    rect.w = max(1, rect.w)
    rect.h = max(1, rect.h)
    if rect.left < bounds.left:
        rect.left = bounds.left
    if rect.top < bounds.top:
        rect.top = bounds.top
    if rect.right > bounds.right:
        rect.right = bounds.right
    if rect.bottom > bounds.bottom:
        rect.bottom = bounds.bottom
    rect.w = max(1, rect.w)
    rect.h = max(1, rect.h)
    return rect


class Stage3RectEditor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.config_path = _resolve(args.config)
        self.data = _load_json(self.config_path)
        self.sheet_path = _resolve(args.sheet) if args.sheet else _resolve(self.data.get("sheet", ""))
        self.sheet = pygame.image.load(str(self.sheet_path))
        self.groups = _group_names(self.data)
        if not self.groups:
            raise ValueError("config has no rect groups")
        self.active_group = args.group if args.group in self.groups else self.groups[0]
        for group in self.groups:
            _ensure_group(self.data, group)

        self.screen = pygame.display.set_mode((args.window_w, args.window_h), pygame.RESIZABLE)
        pygame.display.set_caption("Stage3 rect editor")
        self.font = pygame.font.SysFont("consolas", 16) or pygame.font.Font(None, 16)
        self.small_font = pygame.font.SysFont("consolas", 13) or pygame.font.Font(None, 13)

        self.zoom = args.zoom if args.zoom > 0 else self._fit_zoom()
        self.offset = pygame.Vector2(0, 0)
        self._center_image()
        self.scaled_cache: tuple[float, pygame.Surface] | None = None

        self.selected_index: int | None = None
        self.drag_start: tuple[int, int] | None = None
        self.draft_rect: pygame.Rect | None = None
        self.resize_handle: str | None = None
        self.resize_start_rect: pygame.Rect | None = None
        self.panning = False
        self.pan_anchor = pygame.Vector2(0, 0)
        self.pan_offset = pygame.Vector2(0, 0)
        self.dim_mode = "group"
        self.show_boundary_outline = False
        self.show_help = True
        self.dirty = False
        self.message = "Ready"
        self.undo_stack: list[dict[str, Any]] = []

    def _fit_zoom(self) -> float:
        sw, sh = self.sheet.get_size()
        ww, wh = self.screen.get_size()
        return max(0.1, min((ww - 24) / sw, (wh - 88) / sh, 1.0))

    def _center_image(self) -> None:
        sw, sh = self.sheet.get_size()
        ww, wh = self.screen.get_size()
        self.offset.xy = ((ww - sw * self.zoom) / 2, (wh - sh * self.zoom) / 2 + 20)

    def _push_undo(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.data))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)

    def _screen_to_image(self, pos: tuple[int, int]) -> tuple[int, int]:
        x = int((pos[0] - self.offset.x) / self.zoom)
        y = int((pos[1] - self.offset.y) / self.zoom)
        sw, sh = self.sheet.get_size()
        return max(0, min(sw, x)), max(0, min(sh, y))

    def _image_to_screen_rect(self, rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(
            int(self.offset.x + rect.x * self.zoom),
            int(self.offset.y + rect.y * self.zoom),
            max(1, int(rect.w * self.zoom)),
            max(1, int(rect.h * self.zoom)),
        )

    def _sheet_screen_rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.offset.x),
            int(self.offset.y),
            max(1, int(self.sheet.get_width() * self.zoom)),
            max(1, int(self.sheet.get_height() * self.zoom)),
        )

    def _active_rects(self) -> list[dict[str, Any]]:
        return _rects(self.data, self.active_group)

    def _selected_rect(self) -> pygame.Rect | None:
        if self.selected_index is None:
            return None
        rects = self._active_rects()
        if 0 <= self.selected_index < len(rects):
            return _rect_to_pygame(rects[self.selected_index])
        self.selected_index = None
        return None

    def _set_selected_rect(self, rect: pygame.Rect) -> None:
        if self.selected_index is None:
            return
        rects = self._active_rects()
        if 0 <= self.selected_index < len(rects):
            rects[self.selected_index] = _rect_dict(_clamp_rect(rect, self.sheet))
            self.dirty = True

    def _find_rect_at(self, image_pos: tuple[int, int]) -> int | None:
        point = pygame.Vector2(image_pos)
        rects = self._active_rects()
        for i in range(len(rects) - 1, -1, -1):
            if _rect_to_pygame(rects[i]).collidepoint(point.x, point.y):
                return i
        return None

    def _resize_handle_at(self, image_pos: tuple[int, int]) -> str | None:
        rect = self._selected_rect()
        if rect is None:
            return None

        x, y = image_pos
        tolerance = max(2, int(8 / max(0.01, self.zoom)))
        if not rect.inflate(tolerance * 2, tolerance * 2).collidepoint(x, y):
            return None

        near_left = abs(x - rect.left) <= tolerance and rect.top - tolerance <= y <= rect.bottom + tolerance
        near_right = abs(x - rect.right) <= tolerance and rect.top - tolerance <= y <= rect.bottom + tolerance
        near_top = abs(y - rect.top) <= tolerance and rect.left - tolerance <= x <= rect.right + tolerance
        near_bottom = abs(y - rect.bottom) <= tolerance and rect.left - tolerance <= x <= rect.right + tolerance

        handle = ""
        if near_top:
            handle += "n"
        elif near_bottom:
            handle += "s"
        if near_left:
            handle += "w"
        elif near_right:
            handle += "e"
        return handle or None

    def _begin_resize(self, handle: str) -> None:
        rect = self._selected_rect()
        if rect is None:
            return
        self._push_undo()
        self.resize_handle = handle
        self.resize_start_rect = rect.copy()
        self.drag_start = None
        self.draft_rect = None
        self.message = f"Resizing {self.active_group} #{self.selected_index + 1}: {handle}"

    def _resized_rect(self, image_pos: tuple[int, int]) -> pygame.Rect | None:
        if self.resize_handle is None or self.resize_start_rect is None:
            return None
        x, y = image_pos
        start = self.resize_start_rect
        min_size = 1
        left = start.left
        right = start.right
        top = start.top
        bottom = start.bottom
        bounds = pygame.Rect(0, 0, *self.sheet.get_size())

        if "w" in self.resize_handle:
            left = max(bounds.left, min(x, right - min_size))
        elif "e" in self.resize_handle:
            right = min(bounds.right, max(x, left + min_size))

        if "n" in self.resize_handle:
            top = max(bounds.top, min(y, bottom - min_size))
        elif "s" in self.resize_handle:
            bottom = min(bounds.bottom, max(y, top + min_size))

        return pygame.Rect(left, top, right - left, bottom - top)

    def _cycle_group(self, direction: int) -> None:
        index = self.groups.index(self.active_group)
        self.active_group = self.groups[(index + direction) % len(self.groups)]
        self.selected_index = None
        self.message = f"Group: {self.active_group}"

    def _switch_group_by_number(self, key: int) -> None:
        if pygame.K_1 <= key <= pygame.K_9:
            index = key - pygame.K_1
            if index < len(self.groups):
                self.active_group = self.groups[index]
                self.selected_index = None
                self.message = f"Group: {self.active_group}"

    def _zoom_at(self, factor: float, mouse_pos: tuple[int, int]) -> None:
        before = pygame.Vector2(self._screen_to_image(mouse_pos))
        self.zoom = max(0.08, min(8.0, self.zoom * factor))
        after_screen = pygame.Vector2(before.x * self.zoom, before.y * self.zoom)
        self.offset = pygame.Vector2(mouse_pos) - after_screen
        self.scaled_cache = None

    def _save(self) -> None:
        self.config_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.dirty = False
        self.message = f"Saved: {self.config_path}"

    def _undo(self) -> None:
        if not self.undo_stack:
            self.message = "Nothing to undo"
            return
        self.data = self.undo_stack.pop()
        self.selected_index = None
        self.dirty = True
        self.message = "Undo"

    def _delete_selected(self) -> None:
        if self.selected_index is None:
            self.message = "No selected rect"
            return
        rects = self._active_rects()
        if 0 <= self.selected_index < len(rects):
            self._push_undo()
            del rects[self.selected_index]
            self.selected_index = None
            self.dirty = True
            self.message = "Deleted rect"

    def _move_or_resize_selected(self, key: int, mods: int) -> None:
        rect = self._selected_rect()
        if rect is None:
            return
        step = 10 if mods & pygame.KMOD_CTRL else 1
        self._push_undo()
        if mods & pygame.KMOD_SHIFT:
            if key == pygame.K_LEFT:
                rect.w -= step
            elif key == pygame.K_RIGHT:
                rect.w += step
            elif key == pygame.K_UP:
                rect.h -= step
            elif key == pygame.K_DOWN:
                rect.h += step
        else:
            if key == pygame.K_LEFT:
                rect.x -= step
            elif key == pygame.K_RIGHT:
                rect.x += step
            elif key == pygame.K_UP:
                rect.y -= step
            elif key == pygame.K_DOWN:
                rect.y += step
        self._set_selected_rect(rect)
        self.message = "Adjusted selected rect"

    def _handle_key(self, event: pygame.event.Event) -> bool:
        mods = pygame.key.get_mods()
        if event.key == pygame.K_ESCAPE:
            return False
        if event.key == pygame.K_TAB:
            self._cycle_group(-1 if mods & pygame.KMOD_SHIFT else 1)
        elif pygame.K_1 <= event.key <= pygame.K_9:
            self._switch_group_by_number(event.key)
        elif event.key == pygame.K_s:
            self._save()
        elif event.key == pygame.K_u or (event.key == pygame.K_z and mods & pygame.KMOD_CTRL):
            self._undo()
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self._delete_selected()
        elif event.key == pygame.K_a:
            self.dim_mode = "selected" if self.dim_mode == "group" else "group"
            self.message = f"Dim mode: {self.dim_mode}"
        elif event.key == pygame.K_b:
            self.show_boundary_outline = not self.show_boundary_outline
            state = "visible" if self.show_boundary_outline else "hidden"
            self.message = f"Boundary outline: {state}"
        elif event.key == pygame.K_h:
            self.show_help = not self.show_help
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            ww, wh = self.screen.get_size()
            self._zoom_at(1.15, (ww // 2, wh // 2))
        elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
            ww, wh = self.screen.get_size()
            self._zoom_at(1 / 1.15, (ww // 2, wh // 2))
        elif event.key == pygame.K_HOME:
            self.zoom = self._fit_zoom()
            self._center_image()
            self.scaled_cache = None
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            self._move_or_resize_selected(event.key, mods)
        return True

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button in (2, 3):
            self.panning = True
            self.pan_anchor = pygame.Vector2(event.pos)
            self.pan_offset = self.offset.copy()
            return
        if event.button != 1:
            return
        if not self._sheet_screen_rect().collidepoint(event.pos):
            return

        image_pos = self._screen_to_image(event.pos)
        hit = self._find_rect_at(image_pos)
        mods = pygame.key.get_mods()
        if hit is not None and not (mods & pygame.KMOD_SHIFT):
            self.selected_index = hit
            handle = self._resize_handle_at(image_pos)
            if handle is not None:
                self._begin_resize(handle)
                return
            rect = self._active_rects()[hit]
            self.message = f"Selected {self.active_group} #{hit + 1}: {rect}; drag edge/corner to resize"
            return
        if not (mods & pygame.KMOD_SHIFT):
            handle = self._resize_handle_at(image_pos)
            if handle is not None:
                self._begin_resize(handle)
                return
        self.selected_index = None
        self.drag_start = image_pos
        self.draft_rect = pygame.Rect(image_pos[0], image_pos[1], 1, 1)

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.panning:
            self.offset = self.pan_offset + (pygame.Vector2(event.pos) - self.pan_anchor)
            return
        if self.resize_handle is not None:
            rect = self._resized_rect(self._screen_to_image(event.pos))
            if rect is not None:
                self._set_selected_rect(rect)
            return
        if self.drag_start is None:
            return
        x0, y0 = self.drag_start
        x1, y1 = self._screen_to_image(event.pos)
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        self.draft_rect = pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button in (2, 3):
            self.panning = False
            return
        if event.button == 1 and self.resize_handle is not None:
            rect = self._selected_rect()
            self.message = f"Resized rect: {tuple(rect) if rect is not None else ''}"
            self.resize_handle = None
            self.resize_start_rect = None
            return
        if event.button != 1 or self.drag_start is None or self.draft_rect is None:
            return
        rect = _clamp_rect(self.draft_rect, self.sheet)
        self.drag_start = None
        self.draft_rect = None
        if rect.w < 3 or rect.h < 3:
            self.message = "Rect too small"
            return
        self._push_undo()
        self._active_rects().append(_rect_dict(rect))
        self.selected_index = len(self._active_rects()) - 1
        self.dirty = True
        self.message = f"Added {self.active_group} #{self.selected_index + 1}: {tuple(rect)}"

    def _handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            self.scaled_cache = None
        elif event.type == pygame.MOUSEWHEEL:
            self._zoom_at(1.12 if event.y > 0 else 1 / 1.12, pygame.mouse.get_pos())
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self._zoom_at(1.12, event.pos)
            elif event.button == 5:
                self._zoom_at(1 / 1.12, event.pos)
            else:
                self._handle_mouse_down(event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(event)
        elif event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        return True

    def _scaled_sheet(self) -> pygame.Surface:
        size = (max(1, int(self.sheet.get_width() * self.zoom)), max(1, int(self.sheet.get_height() * self.zoom)))
        if self.scaled_cache is None or self.scaled_cache[0] != self.zoom or self.scaled_cache[1].get_size() != size:
            self.scaled_cache = (self.zoom, pygame.transform.smoothscale(self.sheet, size))
        return self.scaled_cache[1]

    def _hole_rects(self) -> list[pygame.Rect]:
        if self.draft_rect is not None:
            return [self.draft_rect]
        if self.dim_mode == "selected":
            selected = self._selected_rect()
            return [selected] if selected is not None else []
        return [_rect_to_pygame(rect) for rect in self._active_rects()]

    def _draw_dim_overlay(self) -> None:
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 172))
        for rect in self._hole_rects():
            overlay.fill((0, 0, 0, 0), self._image_to_screen_rect(rect))
        self.screen.blit(overlay, (0, 0))

    def _outside_outline_segments(self, rect: pygame.Rect) -> list[pygame.Rect]:
        bounds = pygame.Rect(0, 0, *self.sheet.get_size())
        candidates = [
            pygame.Rect(rect.x - 1, rect.y - 1, rect.w + 2, 1),
            pygame.Rect(rect.x - 1, rect.y + rect.h, rect.w + 2, 1),
            pygame.Rect(rect.x - 1, rect.y, 1, rect.h),
            pygame.Rect(rect.x + rect.w, rect.y, 1, rect.h),
        ]
        segments = []
        for segment in candidates:
            clipped = segment.clip(bounds)
            if clipped.w > 0 and clipped.h > 0:
                segments.append(clipped)
        return segments

    def _draw_boundary_outlines(self) -> None:
        if not self.show_boundary_outline:
            return
        color = (*_group_color(self.data, self.active_group), 235)
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        for rect in self._hole_rects():
            for segment in self._outside_outline_segments(rect):
                pygame.draw.rect(overlay, color, self._image_to_screen_rect(segment))
        self.screen.blit(overlay, (0, 0))

    def _draw_text(self, text: str, pos: tuple[int, int], color: tuple[int, int, int] = (230, 232, 235)) -> int:
        image = self.font.render(text, True, color)
        bg = pygame.Rect(pos[0] - 4, pos[1] - 3, image.get_width() + 8, image.get_height() + 6)
        pygame.draw.rect(self.screen, (8, 10, 13), bg)
        self.screen.blit(image, pos)
        return image.get_height() + 6

    def _draw_ui(self) -> None:
        color = _group_color(self.data, self.active_group)
        dirty = "*" if self.dirty else ""
        rect_count = len(self._active_rects())
        selected = f" selected=#{self.selected_index + 1}" if self.selected_index is not None else ""
        outline = "on" if self.show_boundary_outline else "off"
        mouse = self._screen_to_image(pygame.mouse.get_pos())
        y = 8
        y += self._draw_text(
            f"{dirty} group={self.active_group} rects={rect_count}{selected} outline={outline} zoom={self.zoom:.2f} mouse={mouse}",
            (10, y),
            color,
        )
        if self.message:
            y += self._draw_text(self.message, (10, y), (230, 232, 235))
        if not self.show_help:
            return
        help_lines = [
            "L-drag add | click select | drag edge/corner resize | Shift+L-drag force add",
            "S save | Del delete | U/Ctrl+Z undo | A dim | B outline | H help",
            "Wheel zoom | RMB/MMB pan | 1..9/Tab group | arrows move | Shift+arrows resize",
        ]
        for line in help_lines:
            y += self._draw_text(line, (10, y), (190, 198, 208))

    def draw(self) -> None:
        self.screen.fill((12, 14, 18))
        self.screen.blit(self._scaled_sheet(), self.offset)
        self._draw_dim_overlay()
        self._draw_boundary_outlines()
        self._draw_ui()
        pygame.display.flip()

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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="rect JSON to edit")
    parser.add_argument("--sheet", default=None, help="override sheet image path")
    parser.add_argument("--group", default=None, help="initial active group")
    parser.add_argument("--window-w", type=int, default=1500)
    parser.add_argument("--window-h", type=int, default=900)
    parser.add_argument("--zoom", type=float, default=0.0, help="initial zoom; 0 fits image to window")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pygame.init()
    pygame.font.init()
    try:
        editor = Stage3RectEditor(args)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, pygame.error) as exc:
        print(f"[stage3-rect-editor] error: {exc}")
        return 2
    return editor.run()


if __name__ == "__main__":
    raise SystemExit(main())
