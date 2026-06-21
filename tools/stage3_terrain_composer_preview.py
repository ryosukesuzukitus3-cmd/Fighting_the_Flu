"""Compose Stage3 terrain preview from hand-cut atlas pieces.

This is intentionally a preview tool, not the in-game renderer. It uses the
current Stage3 collision strip as a guide, then lays atlas pieces at their
native sizes. Debug output compares the current strip collision with a coarse
collision surface derived from the actually placed atlas caps.

Examples:
  python tools/stage3_terrain_composer_preview.py
  python tools/stage3_terrain_composer_preview.py --x 0 --x 3600 --debug-lines
  python tools/stage3_terrain_composer_preview.py --out captures/stage3_composer
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from stage3_alpha_mask_common import DEFAULT_MASK_DIR, mask_path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_OUT = ROOT / "captures" / "stage3_terrain_composer"
DEFAULT_VIEW_X = (0, 2200, 4400, 6600, 8800, 10800)
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"
ALPHA_SOLID_THRESHOLD = 24


@dataclass(frozen=True)
class Piece:
    group: str
    index: int
    image: pygame.Surface
    source: pygame.Rect
    label: str


@dataclass(frozen=True)
class SurfaceRun:
    x0: int
    x1: int
    y: int
    side: str


@dataclass(frozen=True)
class PlacedPiece:
    image: pygame.Surface
    x: int
    y: int
    clip: pygame.Rect
    side: str
    role: str


@dataclass(frozen=True)
class CollisionSurfaceRun:
    x0: int
    x1: int
    y: int
    side: str


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _stage3_segments(stage_path: Path) -> list[Any]:
    from src.entities.terrain import make_terrain_strip

    data = json.loads(stage_path.read_text(encoding="utf-8"))
    layouts = data.get("terrain_layout", [])
    if not layouts:
        raise ValueError(f"{stage_path} does not contain terrain_layout")
    layout = layouts[0]
    if layout.get("type") != "TerrainStrip":
        raise ValueError("stage3 terrain composer expects first layout to be TerrainStrip")
    start_x = float(layout.get("start_offset", 0))
    kwargs = {
        "length": int(layout.get("length", 12000)),
        "theme": str(layout.get("theme", "fortress")),
        "segment_w": int(layout.get("segment_w", 48)),
        "seed": int(layout.get("seed", 303)),
        "gap_min": int(layout.get("gap_min", 292)),
        "gap_max": int(layout.get("gap_max", 390)),
        "center_y": int(layout.get("center_y", 292)),
        "center_wave": int(layout.get("center_wave", 118)),
        "top_min": int(layout.get("top_min", 28)),
        "bottom_min": int(layout.get("bottom_min", 34)),
        "irregularity": int(layout.get("irregularity", 58)),
        "breakable_chance": float(layout.get("breakable_chance", 0.0)),
        "breakable_hp": int(layout.get("breakable_hp", 5)),
        "breakable_drop_chance": float(layout.get("breakable_drop_chance", 0.0)),
        "profile": str(layout.get("profile", "normal")),
    }
    return make_terrain_strip(start_x, **kwargs)


def _rect_from_json(raw: Any, *, group: str, index: int) -> tuple[pygame.Rect, str]:
    if isinstance(raw, dict):
        try:
            rect = pygame.Rect(int(raw["x"]), int(raw["y"]), int(raw["w"]), int(raw["h"]))
        except KeyError as exc:
            raise ValueError(f"{group}[{index}] missing key: {exc.args[0]}") from exc
        return rect, str(raw.get("label", ""))
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        rect = pygame.Rect(*(int(v) for v in raw[:4]))
        label = str(raw[4]) if len(raw) >= 5 else ""
        return rect, label
    raise ValueError(f"{group}[{index}] must be {{x,y,w,h}} or [x,y,w,h]")


def _source_crop(sheet: pygame.Surface, rect: pygame.Rect) -> pygame.Surface:
    crop = pygame.Surface(rect.size, pygame.SRCALPHA)
    crop.blit(sheet, (0, 0), rect)
    return crop


def _apply_manual_mask(crop: pygame.Surface, path: Path) -> pygame.Surface | None:
    if not path.exists():
        return None
    mask = pygame.image.load(str(path))
    if mask.get_size() != crop.get_size():
        raise ValueError(f"alpha mask size mismatch: {path}")
    masked = crop.copy()
    w, h = masked.get_size()
    for y in range(h):
        for x in range(w):
            if mask.get_at((x, y)).r >= 128:
                r, g, b, _a = masked.get_at((x, y))
                masked.set_at((x, y), (r, g, b, 0))
    return masked


def _load_pieces(
    rects_path: Path,
    *,
    mask_dir: Path,
) -> dict[str, list[Piece]]:
    data = json.loads(rects_path.read_text(encoding="utf-8"))
    sheet_path = _resolve(data.get("sheet", "assets/graphic/stage3_fortress_terrain_sheet.png"))
    sheet = pygame.image.load(str(sheet_path))
    bounds = pygame.Rect(0, 0, *sheet.get_size())
    groups_raw = data.get("groups", {})
    if not isinstance(groups_raw, dict):
        raise ValueError("rect config must contain object key: groups")

    pieces: dict[str, list[Piece]] = {}
    for group, value in groups_raw.items():
        rects_raw = value.get("rects", []) if isinstance(value, dict) else value
        if not isinstance(rects_raw, list):
            raise ValueError(f"{group}.rects must be a list")
        group_pieces: list[Piece] = []
        for i, raw in enumerate(rects_raw):
            rect, label = _rect_from_json(raw, group=group, index=i)
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError(f"{group}[{i}] has non-positive size")
            if not bounds.contains(rect):
                raise ValueError(f"{group}[{i}] is out of sheet bounds: {tuple(rect)}")
            source = _source_crop(sheet, rect)
            manual = _apply_manual_mask(source, mask_path(mask_dir, group, i, rect))
            image = manual if manual is not None else source
            group_pieces.append(Piece(group, i, image, rect, label or f"{group}:{i + 1}"))
        pieces[group] = group_pieces
    return pieces


def _load_backdrop(width: int, height: int) -> pygame.Surface:
    surface = pygame.Surface((width, height))
    surface.fill((6, 14, 17))
    try:
        raw = pygame.image.load(str(BACKGROUND_PATH))
    except (FileNotFoundError, pygame.error):
        return surface

    scale = max(width / raw.get_width(), height / raw.get_height())
    scaled = pygame.transform.smoothscale(
        raw,
        (max(width, int(raw.get_width() * scale)), max(height, int(raw.get_height() * scale))),
    )
    surface.blit(scaled, ((width - scaled.get_width()) // 2, (height - scaled.get_height()) // 2))
    veil = pygame.Surface((width, height), pygame.SRCALPHA)
    veil.fill((0, 4, 6, 82))
    surface.blit(veil, (0, 0))
    return surface


def _segment_for_world_x(segments: list[Any], world_x: float, side: str) -> Any | None:
    candidates = [
        segment
        for segment in segments
        if segment.side == side and segment.world_x <= world_x < segment.world_x + segment.rect.width
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda segment: segment.rect.height)


def _surface_y_at(segments: list[Any], world_x: float, side: str) -> int | None:
    segment = _segment_for_world_x(segments, world_x, side)
    if segment is None:
        return None
    return int(round(segment.surface_y))


def _surface_runs(
    segments: list[Any],
    *,
    camera_x: float,
    width: int,
    side: str,
    sample_step: int,
    tolerance: int,
) -> list[SurfaceRun]:
    samples: list[tuple[int, int]] = []
    for screen_x in range(-sample_step, width + sample_step + 1, sample_step):
        y = _surface_y_at(segments, camera_x + screen_x, side)
        if y is not None:
            samples.append((screen_x, y))
    if not samples:
        return []

    runs: list[SurfaceRun] = []
    run_x0, run_y = samples[0]
    run_x1 = run_x0 + sample_step
    ys = [run_y]
    for screen_x, y in samples[1:]:
        average_y = int(round(sum(ys) / len(ys)))
        if abs(y - average_y) <= tolerance and screen_x <= run_x1 + sample_step:
            run_x1 = screen_x + sample_step
            ys.append(y)
        else:
            runs.append(SurfaceRun(run_x0, run_x1, int(round(sum(ys) / len(ys))), side))
            run_x0 = screen_x
            run_x1 = screen_x + sample_step
            ys = [y]
    runs.append(SurfaceRun(run_x0, run_x1, int(round(sum(ys) / len(ys))), side))
    return runs


def _stable_seed(*values: int) -> int:
    seed = 0x4D595DF4
    for value in values:
        seed = ((seed * 1664525) + value + 1013904223) & 0xFFFFFFFF
    return seed


def _choice(rng: random.Random, pieces: list[Piece]) -> Piece:
    if not pieces:
        raise ValueError("required atlas piece group is empty")
    return pieces[rng.randrange(len(pieces))]


def _clip_blit(
    target: pygame.Surface,
    image: pygame.Surface,
    pos: tuple[int, int],
    *,
    clip: pygame.Rect | None = None,
) -> pygame.Rect | None:
    if clip is None:
        return target.blit(image, pos)
    clipped = clip.clip(target.get_rect())
    if clipped.width <= 0 or clipped.height <= 0:
        return None
    old_clip = target.get_clip()
    target.set_clip(clipped)
    drawn = target.blit(image, pos)
    target.set_clip(old_clip)
    return drawn.clip(clipped)


def _draw_body_fill(
    target: pygame.Surface,
    pieces: dict[str, list[Piece]],
    run: SurfaceRun,
    *,
    height: int,
    rng: random.Random,
    overlap: int,
    surface_depth: int,
) -> None:
    block_groups = [name for name in ("block_tall", "block_square") if pieces.get(name)]
    if not block_groups:
        return

    x = run.x0 - 16
    clip = pygame.Rect(run.x0, 0, run.x1 - run.x0, height)
    while x < run.x1 + 16:
        if pieces.get("block_tall") and rng.random() < 0.58:
            group = "block_tall"
        else:
            group = rng.choice(block_groups)
        piece = _choice(rng, pieces[group])
        image = _interior_piece_image(piece)
        iw, ih = image.get_size()

        if run.side == "bottom":
            y = run.y + surface_depth
            while y < height + ih:
                _clip_blit(target, image, (x, y), clip=clip)
                y += max(28, ih - overlap)
        else:
            flipped = pygame.transform.flip(image, False, True)
            y = run.y - surface_depth - ih
            while y > -ih * 2:
                _clip_blit(target, flipped, (x, y), clip=clip)
                y -= max(28, ih - overlap)

        x += max(28, iw - overlap)


def _draw_cap(
    target: pygame.Surface,
    pieces: dict[str, list[Piece]],
    run: SurfaceRun,
    *,
    height: int,
    rng: random.Random,
    overlap: int,
    placements: list[PlacedPiece] | None = None,
) -> None:
    caps = pieces.get("strip_top") or pieces.get("block_wide") or pieces.get("block_square")
    if not caps:
        return

    clip = pygame.Rect(run.x0, 0, run.x1 - run.x0, height)
    x = run.x0 - rng.randrange(0, 44)
    while x < run.x1:
        piece = _choice(rng, caps)
        image = piece.image
        if run.side == "bottom":
            y = run.y - 2
        else:
            image = pygame.transform.flip(image, False, True)
            y = run.y - image.get_height() + 2
        drawn = _clip_blit(target, image, (x, y), clip=clip)
        if placements is not None and drawn is not None and drawn.width > 0 and drawn.height > 0:
            placements.append(PlacedPiece(image, x, y, drawn, run.side, "cap"))
        x += max(40, image.get_width() - overlap)


def _interior_piece_image(piece: Piece) -> pygame.Surface:
    image = piece.image
    w, h = image.get_size()
    if h <= 18:
        return image
    trim = max(10, min(34, int(h * 0.16)))
    if h - trim < 12:
        return image
    return image.subsurface(pygame.Rect(0, trim, w, h - trim)).copy()


def _surface_band_depth(pieces: dict[str, list[Piece]]) -> int:
    caps = pieces.get("strip_top", [])
    if not caps:
        return 42
    heights = sorted(piece.image.get_height() for piece in caps)
    median = heights[len(heights) // 2]
    return max(56, min(94, int(median * 0.70)))


def _draw_body_base(
    target: pygame.Surface,
    run: SurfaceRun,
    *,
    height: int,
    surface_depth: int,
) -> None:
    base = pygame.Surface((max(1, run.x1 - run.x0), height), pygame.SRCALPHA)
    base.fill((8, 12, 14, 208))
    if run.side == "bottom":
        target.blit(base, (run.x0, max(0, run.y + surface_depth)))
    else:
        target.blit(base, (run.x0, 0), area=pygame.Rect(0, 0, base.get_width(), max(0, run.y - surface_depth)))


def _draw_props(
    target: pygame.Surface,
    pieces: dict[str, list[Piece]],
    run: SurfaceRun,
    *,
    rng: random.Random,
    height: int,
) -> None:
    props = pieces.get("floor_props", [])
    if run.side != "bottom" or not props or run.x1 - run.x0 < 180:
        return
    if rng.random() > 0.46:
        return
    piece = _choice(rng, props)
    x = rng.randint(run.x0 + 12, max(run.x0 + 12, run.x1 - piece.image.get_width() - 12))
    y = run.y - piece.image.get_height() + 6
    if -piece.image.get_height() < y < height:
        target.blit(piece.image, (x, y))


def _solid_edge_local_y(image: pygame.Surface, local_x: int, side: str) -> int | None:
    if local_x < 0 or local_x >= image.get_width():
        return None
    h = image.get_height()
    ys = range(h) if side == "bottom" else range(h - 1, -1, -1)
    for local_y in ys:
        if image.get_at((local_x, local_y)).a >= ALPHA_SOLID_THRESHOLD:
            return local_y
    return None


def _composer_surface_y_at(placements: list[PlacedPiece], screen_x: int, side: str) -> int | None:
    candidates: list[int] = []
    for placement in placements:
        if placement.side != side or placement.role != "cap":
            continue
        if not (placement.clip.left <= screen_x < placement.clip.right):
            continue
        local_x = screen_x - placement.x
        local_y = _solid_edge_local_y(placement.image, local_x, side)
        if local_y is None:
            continue
        y = placement.y + local_y
        if placement.clip.top <= y < placement.clip.bottom:
            candidates.append(y)
    if not candidates:
        return None
    return min(candidates) if side == "bottom" else max(candidates)


def _split_samples(samples: list[tuple[int, int | None]]) -> list[list[tuple[int, int]]]:
    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for x, y in samples:
        if y is None:
            if current:
                groups.append(current)
                current = []
        else:
            current.append((x, y))
    if current:
        groups.append(current)
    return groups


def _median_smoothed_samples(points: list[tuple[int, int]], radius: int = 2) -> list[tuple[int, int]]:
    smoothed: list[tuple[int, int]] = []
    for i, (x, _y) in enumerate(points):
        nearby = [y for _x, y in points[max(0, i - radius): i + radius + 1]]
        nearby.sort()
        smoothed.append((x, nearby[len(nearby) // 2]))
    return smoothed


def _composer_collision_runs(
    placements: list[PlacedPiece],
    *,
    width: int,
    side: str,
    sample_step: int,
    tolerance: int,
) -> list[CollisionSurfaceRun]:
    raw_samples = [
        (x, _composer_surface_y_at(placements, x, side))
        for x in range(0, width + 1, sample_step)
    ]
    runs: list[CollisionSurfaceRun] = []
    for group in _split_samples(raw_samples):
        samples = _median_smoothed_samples(group)
        if not samples:
            continue
        run_x0, run_y = samples[0]
        run_x1 = run_x0 + sample_step
        ys = [run_y]
        previous_x = run_x0
        for x, y in samples[1:]:
            average_y = int(round(sum(ys) / len(ys)))
            if abs(y - average_y) <= tolerance and x <= previous_x + sample_step * 2:
                run_x1 = x + sample_step
                ys.append(y)
            else:
                runs.append(CollisionSurfaceRun(
                    max(0, run_x0),
                    min(width, run_x1),
                    int(round(sum(ys) / len(ys))),
                    side,
                ))
                run_x0 = x
                run_x1 = x + sample_step
                ys = [y]
            previous_x = x
        runs.append(CollisionSurfaceRun(
            max(0, run_x0),
            min(width, run_x1),
            int(round(sum(ys) / len(ys))),
            side,
        ))
    return [run for run in runs if run.x1 > run.x0]


def _draw_sampled_line(
    target: pygame.Surface,
    *,
    width: int,
    sample_step: int,
    color: tuple[int, int, int],
    line_width: int,
    y_at: Any,
) -> None:
    points: list[tuple[int, int]] = []
    for x in range(0, width + 1, sample_step):
        y = y_at(x)
        if y is None:
            if len(points) > 1:
                pygame.draw.lines(target, color, False, points, line_width)
            points = []
        else:
            points.append((x, int(y)))
    if len(points) > 1:
        pygame.draw.lines(target, color, False, points, line_width)


def _draw_debug_legend(target: pygame.Surface) -> None:
    font = pygame.font.SysFont("consolas", 14) or pygame.font.Font(None, 14)
    labels = [
        ("thin: current strip", (210, 190, 168)),
        ("thick: composer cap edge", (120, 255, 186)),
    ]
    x, y = 18, 45
    box = pygame.Rect(x - 6, y - 5, 236, 43)
    fill = pygame.Surface(box.size, pygame.SRCALPHA)
    fill.fill((0, 8, 10, 150))
    target.blit(fill, box.topleft)
    for i, (text, color) in enumerate(labels):
        yy = y + i * 18
        pygame.draw.line(target, color, (x, yy + 7), (x + 30, yy + 7), 1 + i * 2)
        label = font.render(text, True, (224, 236, 232))
        target.blit(label, (x + 38, yy))


def _draw_collision_lines(
    target: pygame.Surface,
    segments: list[Any],
    placements: list[PlacedPiece],
    *,
    camera_x: float,
    width: int,
    sample_step: int,
    tolerance: int,
) -> None:
    for side, color in (("top", (255, 130, 92)), ("bottom", (92, 220, 255))):
        _draw_sampled_line(
            target,
            width=width,
            sample_step=sample_step,
            color=color,
            line_width=1,
            y_at=lambda x, side=side: _surface_y_at(segments, camera_x + x, side),
        )

    for side, color in (("top", (255, 228, 86)), ("bottom", (92, 255, 176))):
        runs = _composer_collision_runs(
            placements,
            width=width,
            side=side,
            sample_step=sample_step,
            tolerance=tolerance,
        )
        for run in runs:
            pygame.draw.line(target, color, (run.x0, run.y), (run.x1, run.y), 3)
    _draw_debug_legend(target)


def _draw_frame_label(target: pygame.Surface, text: str) -> None:
    font = pygame.font.SysFont("consolas", 18) or pygame.font.Font(None, 18)
    label = font.render(text, True, (224, 236, 232))
    bg = pygame.Rect(16, 14, label.get_width() + 14, label.get_height() + 8)
    fill = pygame.Surface(bg.size, pygame.SRCALPHA)
    fill.fill((0, 8, 10, 172))
    target.blit(fill, bg.topleft)
    target.blit(label, (bg.x + 7, bg.y + 4))


def _render_view(
    segments: list[Any],
    pieces: dict[str, list[Piece]],
    *,
    camera_x: float,
    width: int,
    height: int,
    sample_step: int,
    tolerance: int,
    collision_step: int,
    collision_tolerance: int,
    overlap: int,
    debug_lines: bool,
) -> pygame.Surface:
    surface = _load_backdrop(width, height)
    surface_depth = _surface_band_depth(pieces)
    placements: list[PlacedPiece] = []

    for side in ("top", "bottom"):
        runs = _surface_runs(
            segments,
            camera_x=camera_x,
            width=width,
            side=side,
            sample_step=sample_step,
            tolerance=tolerance,
        )
        for run in runs:
            _draw_body_base(surface, run, height=height, surface_depth=surface_depth)
            rng = random.Random(_stable_seed(int(camera_x), run.x0, run.x1, run.y, 1 if side == "top" else 2))
            _draw_body_fill(
                surface,
                pieces,
                run,
                height=height,
                rng=rng,
                overlap=overlap,
                surface_depth=surface_depth,
            )
        for run in runs:
            rng = random.Random(_stable_seed(int(camera_x), run.x0, run.x1, run.y, 11 if side == "top" else 12))
            _draw_cap(
                surface,
                pieces,
                run,
                height=height,
                rng=rng,
                overlap=overlap,
                placements=placements,
            )
            _draw_props(surface, pieces, run, rng=rng, height=height)

    if debug_lines:
        _draw_collision_lines(
            surface,
            segments,
            placements,
            camera_x=camera_x,
            width=width,
            sample_step=collision_step,
            tolerance=collision_tolerance,
        )
    _draw_frame_label(surface, f"stage3 composer preview  x={int(camera_x)}")
    return surface


def _write_index(paths: list[Path], out: Path) -> Path:
    path = out.with_name(f"{out.name}_index.html")
    cards = []
    for image_path in paths:
        src = html.escape(image_path.name, quote=True)
        caption = html.escape(image_path.stem)
        cards.append(f'<section><h2>{caption}</h2><img src="{src}" alt="{caption}"></section>')
    path.write_text(
        f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>Stage3 Terrain Composer Preview</title>
  <style>
    body {{
      margin: 24px;
      background: #0b1012;
      color: #e4ece9;
      font-family: Consolas, "Yu Gothic", monospace;
    }}
    section {{
      margin: 0 0 28px;
    }}
    h1, h2 {{
      font-weight: 600;
    }}
    img {{
      display: block;
      max-width: 100%;
      height: auto;
      image-rendering: auto;
      background: #050708;
      border: 1px solid #26383a;
    }}
  </style>
</head>
<body>
  <h1>Stage3 Terrain Composer Preview</h1>
  {''.join(cards)}
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _should_open_preview(requested: bool) -> bool:
    if requested:
        return True
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return False
    return sys.stdout.isatty()


def _open_file(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        print(f"[stage3-terrain-composer] open failed: {exc}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose Stage3 terrain preview from atlas pieces")
    parser.add_argument("--stage-json", default=str(DEFAULT_STAGE), help="Stage JSON path")
    parser.add_argument("--rects", default=str(DEFAULT_RECTS), help="Rect JSON path")
    parser.add_argument("--mask-dir", default=str(DEFAULT_MASK_DIR), help="Manual alpha mask directory")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output path prefix")
    parser.add_argument("--x", type=float, action="append", default=[], help="Camera X to render; can be repeated")
    parser.add_argument("--width", type=int, default=800, help="Preview width")
    parser.add_argument("--height", type=int, default=600, help="Preview height")
    parser.add_argument("--sample-step", type=int, default=48, help="Collision surface sample step")
    parser.add_argument("--tolerance", type=int, default=26, help="Y tolerance for merging visual runs")
    parser.add_argument("--collision-step", type=int, default=8, help="Sample step for composer-derived collision runs")
    parser.add_argument("--collision-tolerance", type=int, default=10, help="Y tolerance for composer-derived collision runs")
    parser.add_argument("--overlap", type=int, default=18, help="Atlas piece overlap to hide seams")
    parser.add_argument("--debug-lines", action="store_true", help="Compare current strip lines and composer-derived cap edge runs")
    parser.add_argument("--open", action="store_true", help="Open generated HTML preview")
    parser.add_argument("--no-open", action="store_true", help="Do not open generated HTML preview")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        pygame.init()
        pygame.font.init()
        stage_path = _resolve(args.stage_json)
        rects_path = _resolve(args.rects)
        mask_dir = _resolve(args.mask_dir)
        out = _resolve(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)

        segments = _stage3_segments(stage_path)
        pieces = _load_pieces(
            rects_path,
            mask_dir=mask_dir,
        )
        camera_xs = args.x or list(DEFAULT_VIEW_X)

        paths: list[Path] = []
        for i, camera_x in enumerate(camera_xs):
            image = _render_view(
                segments,
                pieces,
                camera_x=camera_x,
                width=max(320, args.width),
                height=max(240, args.height),
                sample_step=max(8, args.sample_step),
                tolerance=max(0, args.tolerance),
                collision_step=max(2, args.collision_step),
                collision_tolerance=max(0, args.collision_tolerance),
                overlap=max(0, args.overlap),
                debug_lines=args.debug_lines,
            )
            path = out.with_name(f"{out.name}_{i:02d}_x{int(camera_x)}.png")
            pygame.image.save(image, str(path))
            paths.append(path)

        index = _write_index(paths, out)
        for path in [*paths, index]:
            print(path)
        if not args.no_open and _should_open_preview(args.open):
            _open_file(index)
        return 0
    except Exception as exc:
        print(f"[stage3-terrain-composer] error: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
