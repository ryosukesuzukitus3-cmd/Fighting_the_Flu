"""Interactive editor for Stage3 terrain alpha masks.

The mask PNGs use white pixels for transparent areas and black pixels for
opaque areas. The terrain composer prefers these manual masks when they exist.

Controls:
  Left drag              paint transparent
  Right drag             restore opaque
  Shift + Left click     flood-fill transparent from clicked pixel
  Shift + Right click    flood-fill opaque from clicked pixel
  Mouse wheel            brush size
  Ctrl + Mouse wheel     zoom
  Shift + Mouse wheel    flood tolerance
  Middle drag            pan
  [ / ] or P / N         previous / next rect
  Tab / Shift+Tab        switch group
  1..9                   switch group
  A                      seed mask from border-connected dark pixels
  C                      clear current mask
  S                      save current mask
  O                      toggle magenta mask overlay
  G                      toggle pixel grid
  H                      toggle help
  Esc                    quit
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

import pygame

from stage3_alpha_mask_common import DEFAULT_MASK_DIR, mask_path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "tools" / "stage3_terrain_rects.json"


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("groups"), dict):
        raise ValueError("config must contain object key: groups")
    return data


def _rect_from_json(raw: Any) -> pygame.Rect:
    if isinstance(raw, dict):
        return pygame.Rect(int(raw["x"]), int(raw["y"]), int(raw["w"]), int(raw["h"]))
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        return pygame.Rect(*(int(v) for v in raw[:4]))
    raise ValueError("rect must be {x,y,w,h} or [x,y,w,h]")


def _rects_for_group(data: dict[str, Any], group: str) -> list[pygame.Rect]:
    value = data["groups"].get(group)
    rects_raw = value.get("rects", []) if isinstance(value, dict) else value
    if not isinstance(rects_raw, list):
        raise ValueError(f"{group}.rects must be a list")
    return [_rect_from_json(raw) for raw in rects_raw]


def _checker(size: tuple[int, int], cell: int = 8) -> pygame.Surface:
    surf = pygame.Surface(size)
    a = (32, 38, 42)
    b = (52, 60, 64)
    w, h = size
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            color = a if ((x // cell) + (y // cell)) % 2 == 0 else b
            pygame.draw.rect(surf, color, (x, y, cell, cell))
    return surf


def _font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont("consolas", size) or pygame.font.Font(None, size)


def _color_distance(a: pygame.Color, b: pygame.Color) -> int:
    return max(abs(a.r - b.r), abs(a.g - b.g), abs(a.b - b.b))


class Stage3AlphaMaskEditor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.config_path = _resolve(args.config)
        self.data = _load_json(self.config_path)
        self.sheet_path = _resolve(args.sheet) if args.sheet else _resolve(self.data.get("sheet", ""))
        self.sheet = pygame.image.load(str(self.sheet_path))
        self.mask_dir = _resolve(args.mask_dir)
        self.groups = list(self.data["groups"].keys())
        if not self.groups:
            raise ValueError("config has no rect groups")
        self.rects_by_group = {group: _rects_for_group(self.data, group) for group in self.groups}

        start_group = args.group if args.group in self.groups else self._first_non_empty_group()
        self.group_index = self.groups.index(start_group)
        self.rect_index = max(0, min(args.index, max(0, len(self.current_rects) - 1)))

        self.screen = pygame.display.set_mode((args.window_w, args.window_h), pygame.RESIZABLE)
        pygame.display.set_caption("Stage3 alpha mask editor")
        self.font = _font(16)
        self.small_font = _font(13)
        self.zoom = max(0.2, args.zoom)
        self.offset = pygame.Vector2(0, 0)
        self.brush = max(1, args.brush)
        self.tolerance = max(0, args.tolerance)
        self.show_help = True
        self.show_overlay = True
        self.show_grid = False
        self.painting: int | None = None
        self.panning = False
        self.pan_anchor = pygame.Vector2(0, 0)
        self.pan_offset = pygame.Vector2(0, 0)
        self.message = "Ready"
        self.dirty = False
        self.preview_cache: pygame.Surface | None = None
        self.scaled_cache: tuple[float, pygame.Surface] | None = None

        self.crop = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.mask = pygame.Surface((1, 1))
        self._load_current()
        self._fit()

    @property
    def current_group(self) -> str:
        return self.groups[self.group_index]

    @property
    def current_rects(self) -> list[pygame.Rect]:
        return self.rects_by_group[self.current_group]

    @property
    def current_rect(self) -> pygame.Rect:
        rects = self.current_rects
        if not rects:
            return pygame.Rect(0, 0, 1, 1)
        self.rect_index = max(0, min(self.rect_index, len(rects) - 1))
        return rects[self.rect_index]

    @property
    def current_mask_path(self) -> Path:
        return mask_path(self.mask_dir, self.current_group, self.rect_index, self.current_rect)

    def _first_non_empty_group(self) -> str:
        for group in self.groups:
            if self.rects_by_group.get(group):
                return group
        return self.groups[0]

    def _load_current(self) -> None:
        rect = self.current_rect
        self.crop = pygame.Surface(rect.size, pygame.SRCALPHA)
        self.crop.blit(self.sheet, (0, 0), rect)
        self.mask = pygame.Surface(rect.size)
        self.mask.fill((0, 0, 0))
        path = self.current_mask_path
        if path.exists():
            loaded = pygame.image.load(str(path)).convert()
            if loaded.get_size() == rect.size:
                self.mask.blit(loaded, (0, 0))
                self.message = f"Loaded mask: {path.name}"
            else:
                self.message = f"Ignored size-mismatched mask: {path.name}"
        else:
            self.message = f"No mask yet: {path.name}"
        self.dirty = False
        self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self.preview_cache = None
        self.scaled_cache = None

    def _fit(self) -> None:
        w, h = self.crop.get_size()
        sw, sh = self.screen.get_size()
        self.zoom = max(0.2, min((sw - 40) / max(1, w), (sh - 116) / max(1, h), 8.0))
        self.offset.xy = ((sw - w * self.zoom) / 2, (sh - h * self.zoom) / 2 + 28)
        self._invalidate_preview()

    def _save_if_dirty(self) -> None:
        if self.dirty:
            self._save()

    def _save(self) -> None:
        self.mask_dir.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.mask, str(self.current_mask_path))
        self.dirty = False
        self.message = f"Saved: {self.current_mask_path}"

    def _clear(self) -> None:
        self.mask.fill((0, 0, 0))
        self.dirty = True
        self.message = "Cleared mask"
        self._invalidate_preview()

    def _screen_rect(self) -> pygame.Rect:
        w, h = self.crop.get_size()
        return pygame.Rect(
            int(self.offset.x),
            int(self.offset.y),
            max(1, int(w * self.zoom)),
            max(1, int(h * self.zoom)),
        )

    def _screen_to_image(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        rect = self._screen_rect()
        if not rect.collidepoint(pos):
            return None
        x = int((pos[0] - self.offset.x) / self.zoom)
        y = int((pos[1] - self.offset.y) / self.zoom)
        w, h = self.crop.get_size()
        if not (0 <= x < w and 0 <= y < h):
            return None
        return x, y

    def _paint(self, pos: tuple[int, int], value: int) -> None:
        color = (255, 255, 255) if value else (0, 0, 0)
        pygame.draw.circle(self.mask, color, pos, self.brush)
        self.dirty = True
        self._invalidate_preview()

    def _flood(self, start: tuple[int, int], value: int) -> None:
        w, h = self.crop.get_size()
        sx, sy = start
        seed = self.crop.get_at((sx, sy))
        seen = bytearray(w * h)
        queue: deque[tuple[int, int]] = deque([(sx, sy)])
        seen[sy * w + sx] = 1
        color = (255, 255, 255) if value else (0, 0, 0)
        changed = 0

        while queue:
            x, y = queue.popleft()
            if _color_distance(self.crop.get_at((x, y)), seed) > self.tolerance:
                continue
            self.mask.set_at((x, y), color)
            changed += 1
            if x > 0:
                idx = y * w + x - 1
                if not seen[idx]:
                    seen[idx] = 1
                    queue.append((x - 1, y))
            if x < w - 1:
                idx = y * w + x + 1
                if not seen[idx]:
                    seen[idx] = 1
                    queue.append((x + 1, y))
            if y > 0:
                idx = (y - 1) * w + x
                if not seen[idx]:
                    seen[idx] = 1
                    queue.append((x, y - 1))
            if y < h - 1:
                idx = (y + 1) * w + x
                if not seen[idx]:
                    seen[idx] = 1
                    queue.append((x, y + 1))

        self.dirty = True
        self.message = f"Flood {'transparent' if value else 'opaque'}: {changed} px"
        self._invalidate_preview()

    def _seed_border_dark(self) -> None:
        w, h = self.crop.get_size()
        seen = bytearray(w * h)
        queue: deque[tuple[int, int]] = deque()

        def is_bg(x: int, y: int) -> bool:
            c = self.crop.get_at((x, y))
            brightest = max(c.r, c.g, c.b)
            darkest = min(c.r, c.g, c.b)
            return brightest <= 30 and brightest - darkest <= 14

        def push(x: int, y: int) -> None:
            idx = y * w + x
            if not seen[idx] and is_bg(x, y):
                seen[idx] = 1
                queue.append((x, y))

        for x in range(w):
            push(x, 0)
            push(x, h - 1)
        for y in range(h):
            push(0, y)
            push(w - 1, y)

        changed = 0
        while queue:
            x, y = queue.popleft()
            self.mask.set_at((x, y), (255, 255, 255))
            changed += 1
            if x > 0:
                push(x - 1, y)
            if x < w - 1:
                push(x + 1, y)
            if y > 0:
                push(x, y - 1)
            if y < h - 1:
                push(x, y + 1)
        self.dirty = True
        self.message = f"Seeded border dark mask: {changed} px"
        self._invalidate_preview()

    def _switch_group(self, delta: int) -> None:
        self._save_if_dirty()
        self.group_index = (self.group_index + delta) % len(self.groups)
        self.rect_index = 0
        self._load_current()
        self._fit()

    def _switch_group_number(self, key: int) -> None:
        index = key - pygame.K_1
        if 0 <= index < len(self.groups):
            self._save_if_dirty()
            self.group_index = index
            self.rect_index = 0
            self._load_current()
            self._fit()

    def _switch_rect(self, delta: int) -> None:
        rects = self.current_rects
        if not rects:
            return
        self._save_if_dirty()
        self.rect_index = (self.rect_index + delta) % len(rects)
        self._load_current()
        self._fit()

    def _zoom_at(self, factor: float, mouse_pos: tuple[int, int]) -> None:
        image_pos = self._screen_to_image(mouse_pos)
        if image_pos is None:
            image_pos = (self.crop.get_width() // 2, self.crop.get_height() // 2)
        before = pygame.Vector2(image_pos)
        self.zoom = max(0.2, min(24.0, self.zoom * factor))
        after_screen = pygame.Vector2(before.x * self.zoom, before.y * self.zoom)
        self.offset = pygame.Vector2(mouse_pos) - after_screen
        self._invalidate_preview()

    def _handle_key(self, event: pygame.event.Event) -> bool:
        mods = pygame.key.get_mods()
        if event.key == pygame.K_ESCAPE:
            self._save_if_dirty()
            return False
        if event.key == pygame.K_TAB:
            self._switch_group(-1 if mods & pygame.KMOD_SHIFT else 1)
        elif pygame.K_1 <= event.key <= pygame.K_9:
            self._switch_group_number(event.key)
        elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_n):
            self._switch_rect(1)
        elif event.key in (pygame.K_LEFTBRACKET, pygame.K_p):
            self._switch_rect(-1)
        elif event.key == pygame.K_s:
            self._save()
        elif event.key == pygame.K_c:
            self._clear()
        elif event.key == pygame.K_a:
            self._seed_border_dark()
        elif event.key == pygame.K_o:
            self.show_overlay = not self.show_overlay
        elif event.key == pygame.K_g:
            self.show_grid = not self.show_grid
        elif event.key == pygame.K_h:
            self.show_help = not self.show_help
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            sw, sh = self.screen.get_size()
            self._zoom_at(1.15, (sw // 2, sh // 2))
        elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
            sw, sh = self.screen.get_size()
            self._zoom_at(1 / 1.15, (sw // 2, sh // 2))
        elif event.key == pygame.K_HOME:
            self._fit()
        return True

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 2:
            self.panning = True
            self.pan_anchor = pygame.Vector2(event.pos)
            self.pan_offset = self.offset.copy()
            return
        image_pos = self._screen_to_image(event.pos)
        if image_pos is None:
            return
        mods = pygame.key.get_mods()
        if event.button == 1:
            if mods & pygame.KMOD_SHIFT:
                self._flood(image_pos, 1)
            else:
                self.painting = 1
                self._paint(image_pos, 1)
        elif event.button == 3:
            if mods & pygame.KMOD_SHIFT:
                self._flood(image_pos, 0)
            else:
                self.painting = 0
                self._paint(image_pos, 0)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button == 2:
            self.panning = False
        if event.button in (1, 3):
            self.painting = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.panning:
            self.offset = self.pan_offset + (pygame.Vector2(event.pos) - self.pan_anchor)
            self._invalidate_preview()
            return
        if self.painting is None:
            return
        image_pos = self._screen_to_image(event.pos)
        if image_pos is not None:
            self._paint(image_pos, self.painting)

    def _handle_wheel(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_CTRL:
            self._zoom_at(1.12 if event.y > 0 else 1 / 1.12, pygame.mouse.get_pos())
        elif mods & pygame.KMOD_SHIFT:
            self.tolerance = max(0, min(80, self.tolerance + event.y))
            self.message = f"Tolerance: {self.tolerance}"
        else:
            self.brush = max(1, min(80, self.brush + event.y))
            self.message = f"Brush: {self.brush}"

    def _preview(self) -> pygame.Surface:
        if self.preview_cache is not None:
            return self.preview_cache
        preview = _checker(self.crop.get_size())
        cut = self.crop.copy()
        overlay = pygame.Surface(self.crop.get_size(), pygame.SRCALPHA)
        w, h = self.crop.get_size()
        for y in range(h):
            for x in range(w):
                if self.mask.get_at((x, y)).r >= 128:
                    r, g, b, _a = cut.get_at((x, y))
                    cut.set_at((x, y), (r, g, b, 0))
                    if self.show_overlay:
                        overlay.set_at((x, y), (255, 60, 180, 118))
        preview.blit(cut, (0, 0))
        if self.show_overlay:
            preview.blit(overlay, (0, 0))
        self.preview_cache = preview
        return preview

    def _scaled_preview(self) -> pygame.Surface:
        if self.scaled_cache is not None and self.scaled_cache[0] == self.zoom:
            return self.scaled_cache[1]
        preview = self._preview()
        size = (
            max(1, int(preview.get_width() * self.zoom)),
            max(1, int(preview.get_height() * self.zoom)),
        )
        scaled = pygame.transform.scale(preview, size)
        self.scaled_cache = (self.zoom, scaled)
        return scaled

    def _draw_text(self, text: str, pos: tuple[int, int], color: tuple[int, int, int] = (230, 236, 232)) -> int:
        label = self.font.render(text, True, color)
        self.screen.blit(label, pos)
        return label.get_height() + 4

    def _draw_help(self) -> None:
        if not self.show_help:
            return
        lines = [
            "Left drag: transparent / Right drag: opaque / Shift+click: flood",
            "Wheel: brush / Ctrl+wheel: zoom / Shift+wheel: tolerance",
            "[ ] or P/N: rect / Tab: group / A: auto seed / C: clear / S: save",
            "O: overlay / G: grid / Home: fit / Esc: save and quit",
        ]
        x, y = 16, self.screen.get_height() - 82
        box = pygame.Surface((self.screen.get_width() - 32, 72), pygame.SRCALPHA)
        box.fill((0, 0, 0, 168))
        self.screen.blit(box, (x - 8, y - 8))
        for line in lines:
            y += self._draw_text(line, (x, y), (218, 224, 220))

    def _draw_grid(self) -> None:
        if not self.show_grid or self.zoom < 5:
            return
        rect = self._screen_rect()
        color = (255, 255, 255, 34)
        grid = pygame.Surface(rect.size, pygame.SRCALPHA)
        step = max(1, int(self.zoom))
        for x in range(0, rect.w, step):
            pygame.draw.line(grid, color, (x, 0), (x, rect.h))
        for y in range(0, rect.h, step):
            pygame.draw.line(grid, color, (0, y), (rect.w, y))
        self.screen.blit(grid, rect.topleft)

    def draw(self) -> None:
        self.screen.fill((16, 19, 22))
        scaled = self._scaled_preview()
        pos = (int(self.offset.x), int(self.offset.y))
        self.screen.blit(scaled, pos)
        pygame.draw.rect(self.screen, (90, 120, 124), self._screen_rect(), 1)
        self._draw_grid()

        rect = self.current_rect
        dirty = "*" if self.dirty else ""
        title = (
            f"{dirty}{self.current_group} #{self.rect_index + 1}/{max(1, len(self.current_rects))} "
            f"rect=({rect.x},{rect.y},{rect.w},{rect.h}) "
            f"brush={self.brush} tol={self.tolerance} zoom={self.zoom:.2f}"
        )
        self._draw_text(title, (14, 10))
        self._draw_text(str(self.current_mask_path), (14, 32), (172, 188, 184))
        self._draw_text(self.message, (14, 54), (255, 210, 128))
        self._draw_help()
        pygame.display.flip()

    def run(self) -> None:
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._save_if_dirty()
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    self._invalidate_preview()
                elif event.type == pygame.KEYDOWN:
                    running = self._handle_key(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._handle_mouse_up(event)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self._handle_wheel(event)
            self.draw()
            clock.tick(60)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit manual alpha masks for Stage3 terrain rects")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Rect JSON path")
    parser.add_argument("--sheet", default="", help="Override terrain sheet path")
    parser.add_argument("--mask-dir", default=str(DEFAULT_MASK_DIR), help="Directory for mask PNGs")
    parser.add_argument("--group", default="", help="Initial group")
    parser.add_argument("--index", type=int, default=0, help="Initial 0-based rect index")
    parser.add_argument("--window-w", type=int, default=1220, help="Window width")
    parser.add_argument("--window-h", type=int, default=820, help="Window height")
    parser.add_argument("--zoom", type=float, default=2.0, help="Initial zoom")
    parser.add_argument("--brush", type=int, default=8, help="Initial brush radius in pixels")
    parser.add_argument("--tolerance", type=int, default=10, help="Initial flood color tolerance")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        pygame.init()
        pygame.font.init()
        Stage3AlphaMaskEditor(args).run()
        return 0
    except Exception as exc:
        print(f"[stage3-alpha-mask-editor] error: {exc}")
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
