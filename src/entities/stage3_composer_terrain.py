from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RECTS_PATH = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_MASK_DIR = ROOT / "tools" / "stage3_terrain_alpha_masks"
ALPHA_SOLID_THRESHOLD = 24
DEFAULT_SAMPLE_STEP = 48
DEFAULT_TOLERANCE = 26
DEFAULT_COLLISION_STEP = 8
DEFAULT_COLLISION_TOLERANCE = 10
DEFAULT_OVERLAP = 0
SURFACE_CAP_OVERHANG = 2


@dataclass(frozen=True)
class Stage3ComposerPiece:
    group: str
    index: int
    image: pygame.Surface
    source: pygame.Rect
    label: str


@dataclass(frozen=True)
class Stage3SurfaceRun:
    x0: int
    x1: int
    y: int
    side: str


@dataclass(frozen=True)
class Stage3PlacedPiece:
    image: pygame.Surface
    x: int
    y: int
    clip: pygame.Rect
    side: str
    role: str


@dataclass(frozen=True)
class Stage3CollisionRun:
    x0: int
    x1: int
    y: int
    side: str


@dataclass(frozen=True)
class Stage3CollisionRect:
    x: int
    y: int
    w: int
    h: int
    side: str = ""


@dataclass(frozen=True)
class Stage3ComposerLayout:
    surface_runs: tuple[Stage3SurfaceRun, ...]
    placements: tuple[Stage3PlacedPiece, ...]
    collision_runs: tuple[Stage3CollisionRun, ...]
    collision_rects: tuple[Stage3CollisionRect, ...]
    surface_depth: int
    bounds: pygame.Rect


_PIECE_CACHE: dict[tuple[str, str], dict[str, list[Stage3ComposerPiece]]] = {}


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _safe_group_name(group: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", group).strip("_") or "group"


def _mask_path(mask_dir: Path, group: str, index: int, rect: pygame.Rect) -> Path:
    safe = _safe_group_name(group)
    name = f"{safe}_{index + 1:02d}_x{rect.x}_y{rect.y}_w{rect.w}_h{rect.h}.png"
    return mask_dir / name


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


def load_stage3_composer_pieces(
    rects_path: str | Path = DEFAULT_RECTS_PATH,
    *,
    mask_dir: str | Path = DEFAULT_MASK_DIR,
) -> dict[str, list[Stage3ComposerPiece]]:
    rects = _resolve(rects_path)
    masks = _resolve(mask_dir)
    cache_key = (str(rects), str(masks))
    if cache_key in _PIECE_CACHE:
        return _PIECE_CACHE[cache_key]

    data = json.loads(rects.read_text(encoding="utf-8"))
    sheet_path = _resolve(data.get("sheet", "assets/graphic/stage3_fortress_terrain_sheet.png"))
    sheet = pygame.image.load(str(sheet_path))
    bounds = pygame.Rect(0, 0, *sheet.get_size())
    groups_raw = data.get("groups", {})
    if not isinstance(groups_raw, dict):
        raise ValueError("rect config must contain object key: groups")

    pieces: dict[str, list[Stage3ComposerPiece]] = {}
    for group, value in groups_raw.items():
        rects_raw = value.get("rects", []) if isinstance(value, dict) else value
        if not isinstance(rects_raw, list):
            raise ValueError(f"{group}.rects must be a list")
        group_pieces: list[Stage3ComposerPiece] = []
        for i, raw in enumerate(rects_raw):
            rect, label = _rect_from_json(raw, group=group, index=i)
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError(f"{group}[{i}] has non-positive size")
            if not bounds.contains(rect):
                raise ValueError(f"{group}[{i}] is out of sheet bounds: {tuple(rect)}")
            source = _source_crop(sheet, rect)
            manual = _apply_manual_mask(source, _mask_path(masks, group, i, rect))
            image = manual if manual is not None else source
            group_pieces.append(Stage3ComposerPiece(group, i, image, rect, label or f"{group}:{i + 1}"))
        pieces[group] = group_pieces
    _PIECE_CACHE[cache_key] = pieces
    return pieces


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
    start_x: int,
    end_x: int,
    side: str,
    sample_step: int,
    tolerance: int,
) -> list[Stage3SurfaceRun]:
    samples: list[tuple[int, int]] = []
    for world_x in range(start_x - sample_step, end_x + sample_step + 1, sample_step):
        y = _surface_y_at(segments, world_x, side)
        if y is not None:
            samples.append((world_x, y))
    if not samples:
        return []

    runs: list[Stage3SurfaceRun] = []
    run_x0, run_y = samples[0]
    run_x1 = run_x0 + sample_step
    ys = [run_y]
    for world_x, y in samples[1:]:
        average_y = int(round(sum(ys) / len(ys)))
        if abs(y - average_y) <= tolerance and world_x <= run_x1 + sample_step:
            run_x1 = world_x + sample_step
            ys.append(y)
        else:
            runs.append(Stage3SurfaceRun(run_x0, run_x1, int(round(sum(ys) / len(ys))), side))
            run_x0 = world_x
            run_x1 = world_x + sample_step
            ys = [y]
    runs.append(Stage3SurfaceRun(run_x0, run_x1, int(round(sum(ys) / len(ys))), side))
    return runs


def _stable_seed(*values: int) -> int:
    seed = 0x4D595DF4
    for value in values:
        seed = ((seed * 1664525) + value + 1013904223) & 0xFFFFFFFF
    return seed


def _choice(rng: random.Random, pieces: list[Stage3ComposerPiece]) -> Stage3ComposerPiece:
    if not pieces:
        raise ValueError("required atlas piece group is empty")
    return pieces[rng.randrange(len(pieces))]


def _opaque_bounds(image: pygame.Surface) -> pygame.Rect:
    w, h = image.get_size()
    min_x, min_y = w, h
    max_x, max_y = -1, -1
    for y in range(h):
        for x in range(w):
            if image.get_at((x, y)).a >= ALPHA_SOLID_THRESHOLD:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x or max_y < min_y:
        return pygame.Rect(0, 0, w, h)
    return pygame.Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _place_piece(
    placements: list[Stage3PlacedPiece],
    image: pygame.Surface,
    x: int,
    y: int,
    *,
    clip: pygame.Rect,
    side: str,
    role: str,
    allow_partial: bool = True,
) -> None:
    image_rect = pygame.Rect(x, y, image.get_width(), image.get_height())
    if not allow_partial and not clip.contains(image_rect):
        return
    clipped = image_rect.clip(clip)
    if clipped.width <= 0 or clipped.height <= 0:
        return
    placements.append(Stage3PlacedPiece(image, x, y, clipped, side, role))


def _surface_band_depth(pieces: dict[str, list[Stage3ComposerPiece]]) -> int:
    caps = pieces.get("strip_top", [])
    if not caps:
        return 96
    heights = sorted(piece.image.get_height() for piece in caps)
    median = heights[len(heights) // 2]
    return max(94, min(148, int(median) - SURFACE_CAP_OVERHANG))


def _add_body_fill(
    placements: list[Stage3PlacedPiece],
    pieces: dict[str, list[Stage3ComposerPiece]],
    run: Stage3SurfaceRun,
    *,
    height: int,
    rng: random.Random,
    overlap: int,
    surface_depth: int,
) -> None:
    square_pieces = pieces.get("block_square") or []
    body_pieces = [piece for piece in square_pieces if piece.image.get_width() <= 130]
    body_pieces = body_pieces or square_pieces or pieces.get("block_tall")
    if not body_pieces:
        return

    clip = pygame.Rect(run.x0, -height, run.x1 - run.x0, height * 3)
    y = run.y + surface_depth if run.side == "bottom" else run.y - surface_depth
    row_heights = sorted(piece.image.get_height() for piece in body_pieces)
    row_step = max(32, row_heights[len(row_heights) // 2] - max(0, overlap))
    while (run.side == "bottom" and y < height) or (run.side == "top" and y > 0):
        x = run.x0
        while x < run.x1:
            piece = _choice(rng, body_pieces)
            image = piece.image
            if run.side == "top":
                image = pygame.transform.flip(image, False, True)
            iw, ih = image.get_size()
            py = y if run.side == "bottom" else y - ih
            _place_piece(placements, image, x, py, clip=clip, side=run.side, role="body", allow_partial=False)
            x += max(32, iw - max(0, overlap))
        y = y + row_step if run.side == "bottom" else y - row_step


def _add_cap(
    placements: list[Stage3PlacedPiece],
    pieces: dict[str, list[Stage3ComposerPiece]],
    run: Stage3SurfaceRun,
    *,
    height: int,
    rng: random.Random,
    overlap: int,
) -> None:
    caps = pieces.get("strip_top") or pieces.get("block_wide") or pieces.get("block_square")
    if not caps:
        return

    clip = pygame.Rect(run.x0, 0, run.x1 - run.x0, height)
    x = run.x0
    while x < run.x1:
        piece = _choice(rng, caps)
        image = piece.image
        if run.side == "bottom":
            y = run.y - SURFACE_CAP_OVERHANG
        else:
            image = pygame.transform.flip(image, False, True)
            y = run.y - image.get_height() + SURFACE_CAP_OVERHANG
        _place_piece(placements, image, x, y, clip=clip, side=run.side, role="cap")
        x += max(40, image.get_width() - max(0, overlap))


def _add_props(
    placements: list[Stage3PlacedPiece],
    pieces: dict[str, list[Stage3ComposerPiece]],
    run: Stage3SurfaceRun,
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
    opaque = _opaque_bounds(piece.image)
    x = rng.randint(run.x0 + 12, max(run.x0 + 12, run.x1 - piece.image.get_width() - 12))
    y = run.y - opaque.bottom + 6
    if -piece.image.get_height() < y < height:
        clip = pygame.Rect(x, y, piece.image.get_width(), piece.image.get_height())
        _place_piece(placements, piece.image, x, y, clip=clip, side=run.side, role="prop")


def _prop_collision_rects(placements: list[Stage3PlacedPiece]) -> list[Stage3CollisionRect]:
    rects: list[Stage3CollisionRect] = []
    for placement in placements:
        if placement.role != "prop":
            continue
        opaque = _opaque_bounds(placement.image)
        world = pygame.Rect(
            placement.x + opaque.x,
            placement.y + opaque.y,
            opaque.width,
            opaque.height,
        ).clip(placement.clip)
        if world.width <= 0 or world.height <= 0:
            continue
        world = world.inflate(-min(8, world.width // 5), -min(8, world.height // 5))
        if world.width <= 0 or world.height <= 0:
            continue
        rects.append(Stage3CollisionRect(world.x, world.y, world.width, world.height))
    return rects


def _solid_edge_local_y(image: pygame.Surface, local_x: int, side: str) -> int | None:
    if local_x < 0 or local_x >= image.get_width():
        return None
    h = image.get_height()
    ys = range(h) if side == "bottom" else range(h - 1, -1, -1)
    for local_y in ys:
        if image.get_at((local_x, local_y)).a >= ALPHA_SOLID_THRESHOLD:
            return local_y
    return None


def _composer_surface_y_at(placements: list[Stage3PlacedPiece], world_x: int, side: str) -> int | None:
    candidates: list[int] = []
    for placement in placements:
        if placement.side != side or placement.role != "cap":
            continue
        if not (placement.clip.left <= world_x < placement.clip.right):
            continue
        local_x = world_x - placement.x
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
    placements: list[Stage3PlacedPiece],
    *,
    start_x: int,
    end_x: int,
    side: str,
    sample_step: int,
    tolerance: int,
) -> list[Stage3CollisionRun]:
    raw_samples = [
        (x, _composer_surface_y_at(placements, x, side))
        for x in range(start_x, end_x + 1, sample_step)
    ]
    runs: list[Stage3CollisionRun] = []
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
                runs.append(Stage3CollisionRun(run_x0, min(end_x, run_x1), int(round(sum(ys) / len(ys))), side))
                run_x0 = x
                run_x1 = x + sample_step
                ys = [y]
            previous_x = x
        runs.append(Stage3CollisionRun(run_x0, min(end_x, run_x1), int(round(sum(ys) / len(ys))), side))
    return [run for run in runs if run.x1 > run.x0]


def build_stage3_composer_layout(
    segments: list[Any],
    pieces: dict[str, list[Stage3ComposerPiece]] | None = None,
    *,
    start_x: int | None = None,
    end_x: int | None = None,
    height: int = SCREEN_HEIGHT,
    sample_step: int = DEFAULT_SAMPLE_STEP,
    tolerance: int = DEFAULT_TOLERANCE,
    collision_step: int = DEFAULT_COLLISION_STEP,
    collision_tolerance: int = DEFAULT_COLLISION_TOLERANCE,
    overlap: int = DEFAULT_OVERLAP,
) -> Stage3ComposerLayout:
    if not segments:
        empty = pygame.Rect(0, 0, 0, height)
        return Stage3ComposerLayout((), (), (), (), 0, empty)
    if pieces is None:
        pieces = load_stage3_composer_pieces()

    min_x = min(int(segment.world_x) for segment in segments)
    max_x = max(int(segment.world_x + segment.rect.width) for segment in segments)
    start = min_x if start_x is None else int(start_x)
    end = max_x if end_x is None else int(end_x)
    surface_depth = _surface_band_depth(pieces)
    surface_runs: list[Stage3SurfaceRun] = []
    placements: list[Stage3PlacedPiece] = []

    for side in ("top", "bottom"):
        runs = _surface_runs(
            segments,
            start_x=start,
            end_x=end,
            side=side,
            sample_step=sample_step,
            tolerance=tolerance,
        )
        surface_runs.extend(runs)
        for run in runs:
            rng = random.Random(_stable_seed(run.x0, run.x1, run.y, 1 if side == "top" else 2))
            _add_body_fill(
                placements,
                pieces,
                run,
                height=height,
                rng=rng,
                overlap=overlap,
                surface_depth=surface_depth,
            )
        for run in runs:
            rng = random.Random(_stable_seed(run.x0, run.x1, run.y, 11 if side == "top" else 12))
            _add_cap(placements, pieces, run, height=height, rng=rng, overlap=overlap)
            _add_props(placements, pieces, run, rng=rng, height=height)

    collision_runs: list[Stage3CollisionRun] = []
    for side in ("top", "bottom"):
        collision_runs.extend(
            _composer_collision_runs(
                placements,
                start_x=start,
                end_x=end,
                side=side,
                sample_step=collision_step,
                tolerance=collision_tolerance,
            )
        )
    collision_rects = _prop_collision_rects(placements)
    bounds = pygame.Rect(start, 0, max(0, end - start), height)
    return Stage3ComposerLayout(
        tuple(surface_runs),
        tuple(placements),
        tuple(collision_runs),
        tuple(collision_rects),
        surface_depth,
        bounds,
    )


def _blit_with_world_clip(
    target: pygame.Surface,
    image: pygame.Surface,
    world_pos: tuple[int, int],
    *,
    camera_x: float,
    clip: pygame.Rect,
) -> None:
    screen_pos = (int(round(world_pos[0] - camera_x)), world_pos[1])
    screen_clip = pygame.Rect(
        int(round(clip.x - camera_x)),
        clip.y,
        clip.width,
        clip.height,
    ).clip(target.get_rect())
    if screen_clip.width <= 0 or screen_clip.height <= 0:
        return
    old_clip = target.get_clip()
    target.set_clip(screen_clip)
    target.blit(image, screen_pos)
    target.set_clip(old_clip)


def draw_stage3_composer_layout(
    target: pygame.Surface,
    layout: Stage3ComposerLayout,
    *,
    camera_x: float,
    debug_lines: bool = False,
) -> None:
    target_rect = target.get_rect()
    base_color = (28, 33, 36, 232)
    for run in layout.surface_runs:
        sx = int(round(run.x0 - camera_x))
        ex = int(round(run.x1 - camera_x))
        if ex < 0 or sx > target_rect.width:
            continue
        width = max(1, ex - sx)
        base = pygame.Surface((width, target_rect.height), pygame.SRCALPHA)
        base.fill(base_color)
        if run.side == "bottom":
            target.blit(base, (sx, max(0, run.y + layout.surface_depth)))
        else:
            area_h = max(0, run.y - layout.surface_depth)
            target.blit(base, (sx, 0), area=pygame.Rect(0, 0, width, area_h))

    for placement in layout.placements:
        if placement.clip.right < camera_x or placement.clip.left > camera_x + target_rect.width:
            continue
        _blit_with_world_clip(
            target,
            placement.image,
            (placement.x, placement.y),
            camera_x=camera_x,
            clip=placement.clip,
        )

    if debug_lines:
        _draw_collision_debug(target, layout, camera_x=camera_x)


def _draw_sampled_line(
    target: pygame.Surface,
    *,
    start_x: int,
    end_x: int,
    sample_step: int,
    color: tuple[int, int, int],
    line_width: int,
    camera_x: float,
    y_at: Any,
) -> None:
    points: list[tuple[int, int]] = []
    for world_x in range(start_x, end_x + 1, sample_step):
        y = y_at(world_x)
        if y is None:
            if len(points) > 1:
                pygame.draw.lines(target, color, False, points, line_width)
            points = []
        else:
            points.append((int(round(world_x - camera_x)), int(y)))
    if len(points) > 1:
        pygame.draw.lines(target, color, False, points, line_width)


def _draw_collision_debug(target: pygame.Surface, layout: Stage3ComposerLayout, *, camera_x: float) -> None:
    for run in layout.collision_runs:
        sx = int(round(run.x0 - camera_x))
        ex = int(round(run.x1 - camera_x))
        if ex < 0 or sx > target.get_width():
            continue
        color = (255, 228, 86) if run.side == "top" else (92, 255, 176)
        pygame.draw.line(target, color, (sx, run.y), (ex, run.y), 3)
    for rect in layout.collision_rects:
        screen_rect = pygame.Rect(
            int(round(rect.x - camera_x)),
            rect.y,
            rect.w,
            rect.h,
        )
        if screen_rect.right < 0 or screen_rect.left > target.get_width():
            continue
        pygame.draw.rect(target, (255, 158, 92), screen_rect, 2)


def _draw_current_strip_debug(
    target: pygame.Surface,
    segments: list[Any],
    *,
    camera_x: float,
    sample_step: int,
) -> None:
    start_x = int(camera_x)
    end_x = int(camera_x + target.get_width())
    for side, color in (("top", (255, 130, 92)), ("bottom", (92, 220, 255))):
        _draw_sampled_line(
            target,
            start_x=start_x,
            end_x=end_x,
            sample_step=sample_step,
            color=color,
            line_width=1,
            camera_x=camera_x,
            y_at=lambda world_x, side=side: _surface_y_at(segments, world_x, side),
        )


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


def render_stage3_composer_surface(
    target: pygame.Surface,
    segments: list[Any],
    pieces: dict[str, list[Stage3ComposerPiece]],
    *,
    camera_x: float,
    sample_step: int = DEFAULT_SAMPLE_STEP,
    tolerance: int = DEFAULT_TOLERANCE,
    collision_step: int = DEFAULT_COLLISION_STEP,
    collision_tolerance: int = DEFAULT_COLLISION_TOLERANCE,
    overlap: int = DEFAULT_OVERLAP,
    debug_lines: bool = False,
) -> Stage3ComposerLayout:
    width = target.get_width()
    layout = build_stage3_composer_layout(
        segments,
        pieces,
        start_x=int(camera_x),
        end_x=int(camera_x + width),
        height=target.get_height(),
        sample_step=sample_step,
        tolerance=tolerance,
        collision_step=collision_step,
        collision_tolerance=collision_tolerance,
        overlap=overlap,
    )
    draw_stage3_composer_layout(target, layout, camera_x=camera_x, debug_lines=debug_lines)
    if debug_lines:
        _draw_current_strip_debug(target, segments, camera_x=camera_x, sample_step=collision_step)
        _draw_debug_legend(target)
    return layout


class Stage3ComposerVisualLayer(pygame.sprite.Sprite):
    terrain_visual_only = True

    def __init__(self, layout: Stage3ComposerLayout) -> None:
        super().__init__()
        self.layout = layout
        self.world_x = float(layout.bounds.x)
        self.y = 0.0
        self.side = ""
        self.image = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(0, 0))
        self._last_camera_x: int | None = None

    def update(self, dt: float, camera: object) -> None:
        camera_x = int(round(float(getattr(camera, "x", 0.0))))
        if self._last_camera_x == camera_x:
            self.rect.topleft = (0, 0)
            return
        self._last_camera_x = camera_x
        self.image.fill((0, 0, 0, 0))
        draw_stage3_composer_layout(self.image, self.layout, camera_x=camera_x)
        self.rect.topleft = (0, 0)

    def is_off_left(self, camera: object) -> bool:
        return False


class Stage3ComposerCollisionBlock(pygame.sprite.Sprite):
    def __init__(self, run: Stage3CollisionRun, *, height: int = SCREEN_HEIGHT) -> None:
        super().__init__()
        self.world_x = float(run.x0)
        self.side = run.side
        self._surface_y = float(run.y)
        width = max(1, int(run.x1 - run.x0))
        if run.side == "top":
            y = 0
            block_h = max(1, min(height, int(run.y)))
        else:
            y = max(0, min(height - 1, int(run.y)))
            block_h = max(1, height - y)
        self.y = float(y)
        self.image = pygame.Surface((width, block_h), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(int(self.world_x), int(self.y)))

    @property
    def surface_y(self) -> float:
        return self._surface_y

    def update(self, dt: float, camera: object) -> None:
        to_screen_x = getattr(camera, "to_screen_x", None)
        sx = to_screen_x(self.world_x) if callable(to_screen_x) else self.world_x - float(getattr(camera, "x", 0.0))
        self.rect.topleft = (int(sx), int(self.y))

    def is_off_left(self, camera: object) -> bool:
        return self.world_x + self.rect.width < float(getattr(camera, "x", 0.0))


class Stage3ComposerCollisionRectBlock(pygame.sprite.Sprite):
    def __init__(self, rect: Stage3CollisionRect) -> None:
        super().__init__()
        self.world_x = float(rect.x)
        self.y = float(rect.y)
        self.side = rect.side
        self.image = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(rect.x, rect.y))

    def update(self, dt: float, camera: object) -> None:
        to_screen_x = getattr(camera, "to_screen_x", None)
        sx = to_screen_x(self.world_x) if callable(to_screen_x) else self.world_x - float(getattr(camera, "x", 0.0))
        self.rect.topleft = (int(sx), int(self.y))

    def is_off_left(self, camera: object) -> bool:
        return self.world_x + self.rect.width < float(getattr(camera, "x", 0.0))


def make_stage3_composer_terrain(
    segments: list[Any],
    *,
    sample_step: int = DEFAULT_SAMPLE_STEP,
    tolerance: int = DEFAULT_TOLERANCE,
    collision_step: int = DEFAULT_COLLISION_STEP,
    collision_tolerance: int = DEFAULT_COLLISION_TOLERANCE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[pygame.sprite.Sprite]:
    pieces = load_stage3_composer_pieces()
    layout = build_stage3_composer_layout(
        segments,
        pieces,
        sample_step=sample_step,
        tolerance=tolerance,
        collision_step=collision_step,
        collision_tolerance=collision_tolerance,
        overlap=overlap,
    )
    sprites: list[pygame.sprite.Sprite] = [Stage3ComposerVisualLayer(layout)]
    sprites.extend(Stage3ComposerCollisionBlock(run) for run in layout.collision_runs)
    sprites.extend(Stage3ComposerCollisionRectBlock(rect) for rect in layout.collision_rects)
    return sprites
