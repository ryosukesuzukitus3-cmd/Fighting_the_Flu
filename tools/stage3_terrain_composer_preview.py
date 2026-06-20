"""Compose Stage3 terrain preview from hand-cut atlas pieces.

This is intentionally a preview tool, not the in-game renderer. It uses the
current Stage3 collision strip as a guide, then lays atlas pieces at their
native sizes so we can tune the visual composition before wiring it into play.

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
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_OUT = ROOT / "captures" / "stage3_terrain_composer"
DEFAULT_VIEW_X = (0, 2200, 4400, 6600, 8800, 10800)
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"


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


def _is_background_pixel(surface: pygame.Surface, x: int, y: int, threshold: int) -> bool:
    r, g, b, a = surface.get_at((x, y))
    return a > 0 and max(r, g, b) <= threshold


def _crop_piece(sheet: pygame.Surface, rect: pygame.Rect, *, threshold: int) -> pygame.Surface:
    crop = pygame.Surface(rect.size, pygame.SRCALPHA)
    crop.blit(sheet, (0, 0), rect)
    w, h = crop.get_size()
    if w <= 0 or h <= 0:
        return crop

    seen = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        idx = y * w + x
        if not seen[idx] and _is_background_pixel(crop, x, y, threshold):
            seen[idx] = 1
            queue.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while queue:
        x, y = queue.popleft()
        r, g, b, _a = crop.get_at((x, y))
        crop.set_at((x, y), (r, g, b, 0))
        if x > 0:
            push(x - 1, y)
        if x < w - 1:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y < h - 1:
            push(x, y + 1)
    return crop


def _load_pieces(rects_path: Path, *, threshold: int) -> dict[str, list[Piece]]:
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
            image = _crop_piece(sheet, rect, threshold=threshold)
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
) -> None:
    if clip is None:
        target.blit(image, pos)
        return
    old_clip = target.get_clip()
    target.set_clip(clip.clip(target.get_rect()))
    target.blit(image, pos)
    target.set_clip(old_clip)


def _draw_body_fill(
    target: pygame.Surface,
    pieces: dict[str, list[Piece]],
    run: SurfaceRun,
    *,
    height: int,
    rng: random.Random,
    overlap: int,
) -> None:
    block_groups = [name for name in ("block_tall", "block_square", "block_wide") if pieces.get(name)]
    if not block_groups:
        return

    x = run.x0 - 16
    clip = pygame.Rect(run.x0, 0, run.x1 - run.x0, height)
    while x < run.x1 + 16:
        remaining_w = run.x1 - x
        if remaining_w > 240 and pieces.get("block_wide"):
            group = "block_wide"
        elif pieces.get("block_tall") and rng.random() < 0.48:
            group = "block_tall"
        else:
            group = rng.choice(block_groups)
        piece = _choice(rng, pieces[group])
        image = piece.image
        iw, ih = image.get_size()

        if run.side == "bottom":
            y = run.y + 26
            while y < height + ih:
                _clip_blit(target, image, (x, y), clip=clip)
                y += max(28, ih - overlap)
        else:
            flipped = pygame.transform.flip(image, False, True)
            y = run.y - 26 - ih
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
        _clip_blit(target, image, (x, y), clip=clip)
        x += max(40, image.get_width() - overlap)


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


def _draw_collision_lines(
    target: pygame.Surface,
    segments: list[Any],
    *,
    camera_x: float,
    width: int,
) -> None:
    for side, color in (("top", (255, 130, 92)), ("bottom", (92, 220, 255))):
        points: list[tuple[int, int]] = []
        for x in range(0, width + 1, 8):
            y = _surface_y_at(segments, camera_x + x, side)
            if y is None:
                if len(points) > 1:
                    pygame.draw.lines(target, color, False, points, 2)
                points = []
            else:
                points.append((x, y))
        if len(points) > 1:
            pygame.draw.lines(target, color, False, points, 2)


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
    overlap: int,
    debug_lines: bool,
) -> pygame.Surface:
    surface = _load_backdrop(width, height)

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
            rng = random.Random(_stable_seed(int(camera_x), run.x0, run.x1, run.y, 1 if side == "top" else 2))
            _draw_body_fill(surface, pieces, run, height=height, rng=rng, overlap=overlap)
        for run in runs:
            rng = random.Random(_stable_seed(int(camera_x), run.x0, run.x1, run.y, 11 if side == "top" else 12))
            _draw_cap(surface, pieces, run, height=height, rng=rng, overlap=overlap)
            _draw_props(surface, pieces, run, rng=rng, height=height)

    if debug_lines:
        _draw_collision_lines(surface, segments, camera_x=camera_x, width=width)
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
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output path prefix")
    parser.add_argument("--x", type=float, action="append", default=[], help="Camera X to render; can be repeated")
    parser.add_argument("--width", type=int, default=800, help="Preview width")
    parser.add_argument("--height", type=int, default=600, help="Preview height")
    parser.add_argument("--sample-step", type=int, default=48, help="Collision surface sample step")
    parser.add_argument("--tolerance", type=int, default=26, help="Y tolerance for merging visual runs")
    parser.add_argument("--overlap", type=int, default=18, help="Atlas piece overlap to hide seams")
    parser.add_argument(
        "--background-threshold",
        type=int,
        default=30,
        help="Dark border-connected pixels at or below this value become transparent",
    )
    parser.add_argument("--debug-lines", action="store_true", help="Draw collision surface guide lines")
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
        out = _resolve(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)

        segments = _stage3_segments(stage_path)
        pieces = _load_pieces(rects_path, threshold=max(0, min(255, args.background_threshold)))
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
