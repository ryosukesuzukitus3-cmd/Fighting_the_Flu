"""Compose Stage3 terrain preview from the runtime composer model.

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
import subprocess
import sys
from pathlib import Path
from typing import Any

import pygame

from src.entities.stage3_composer_terrain import (
    load_stage3_composer_pieces,
    render_stage3_composer_surface,
)
from stage3_alpha_mask_common import DEFAULT_MASK_DIR

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_OUT = ROOT / "captures" / "stage3_terrain_composer"
DEFAULT_VIEW_X = (0, 2200, 4400, 6600, 8800, 10800)
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _stage3_segments(stage_path: Path) -> list[Any]:
    from src.entities.terrain import make_terrain_segments_from_event

    data = json.loads(stage_path.read_text(encoding="utf-8"))
    layouts = data.get("terrain_layout", [])
    if not layouts:
        raise ValueError(f"{stage_path} does not contain terrain_layout")
    layout = layouts[0]
    if layout.get("type") not in {"AuthoredTerrain", "TerrainPath", "TerrainStrip"}:
        raise ValueError("stage3 terrain composer expects continuous terrain layout")
    start_x = float(layout.get("start_offset", 0))
    return make_terrain_segments_from_event(layout, start_x, default_seed=303)


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
    pieces: dict[str, list[Any]],
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
    render_stage3_composer_surface(
        surface,
        segments,
        pieces,
        camera_x=camera_x,
        sample_step=sample_step,
        tolerance=tolerance,
        collision_step=collision_step,
        collision_tolerance=collision_tolerance,
        overlap=overlap,
        debug_lines=debug_lines,
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
    parser.add_argument("--overlap", type=int, default=0, help="Atlas piece overlap to hide seams")
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
        pieces = load_stage3_composer_pieces(
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
