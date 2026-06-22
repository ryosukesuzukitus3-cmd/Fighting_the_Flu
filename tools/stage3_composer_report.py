"""Generate a Stage3 composer review report.

The report captures the same world positions in three ways:
- normal runtime GameScene
- runtime GameScene with collidable terrain overlay
- composer preview with current-strip and composer collision guides
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH  # noqa: E402
from src.core.game import Game  # noqa: E402
from src.entities.stage3_composer_terrain import (  # noqa: E402
    load_stage3_composer_pieces,
    render_stage3_composer_surface,
)
from src.entities.terrain_query import iter_collidable_terrain  # noqa: E402
from src.scenes.game_scene import GameScene  # noqa: E402
try:  # noqa: E402
    from stage3_alpha_mask_common import DEFAULT_MASK_DIR
except ModuleNotFoundError:  # noqa: E402
    from tools.stage3_alpha_mask_common import DEFAULT_MASK_DIR

DEFAULT_STAGE = ROOT / "data" / "stages" / "stage3.json"
DEFAULT_RECTS = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_OUT = ROOT / "captures" / "stage3_composer_report"
DEFAULT_VIEW_X = (0, 2200, 4400, 6600, 8800, 10800)
BACKGROUND_PATH = ROOT / "assets" / "graphic" / "stage3_labor_fortress_bg.png"


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _stage3_layout(stage_path: Path) -> dict[str, Any]:
    data = json.loads(stage_path.read_text(encoding="utf-8"))
    layouts = data.get("terrain_layout", [])
    if not layouts:
        raise ValueError(f"{stage_path} does not contain terrain_layout")
    layout = layouts[0]
    if layout.get("type") not in {"AuthoredTerrain", "TerrainPath", "TerrainStrip"}:
        raise ValueError("Stage3 composer report expects continuous terrain layout")
    return layout


def _stage3_segments(stage_path: Path) -> list[Any]:
    from src.entities.terrain import make_terrain_segments_from_event

    layout = _stage3_layout(stage_path)
    start_x = float(layout.get("start_offset", 0))
    return make_terrain_segments_from_event(layout, start_x, default_seed=303)


def _composer_options(stage_path: Path) -> dict[str, int]:
    layout = _stage3_layout(stage_path)
    return {
        "sample_step": int(layout.get("composer_sample_step", 48)),
        "tolerance": int(layout.get("composer_tolerance", 26)),
        "collision_step": int(layout.get("composer_collision_step", 8)),
        "collision_tolerance": int(layout.get("composer_collision_tolerance", 10)),
        "overlap": int(layout.get("composer_overlap", 0)),
    }


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


def _draw_label(target: pygame.Surface, text: str, *, y: int = 14) -> None:
    font = pygame.font.SysFont("consolas", 18) or pygame.font.Font(None, 18)
    label = font.render(text, True, (224, 236, 232))
    bg = pygame.Rect(16, y, label.get_width() + 14, label.get_height() + 8)
    fill = pygame.Surface(bg.size, pygame.SRCALPHA)
    fill.fill((0, 8, 10, 176))
    target.blit(fill, bg.topleft)
    target.blit(label, (bg.x + 7, bg.y + 4))


def _draw_collision_overlay(target: pygame.Surface, terrain: pygame.sprite.Group, *, camera_x: float) -> None:
    overlay = pygame.Surface(target.get_size(), pygame.SRCALPHA)
    screen = target.get_rect()
    for ter in iter_collidable_terrain(terrain):
        rect = ter.rect.clip(screen)
        if rect.width <= 0 or rect.height <= 0:
            continue
        side = getattr(ter, "side", "")
        color = (255, 228, 86) if side == "top" else (92, 255, 176) if side == "bottom" else (255, 140, 96)
        fill = (*color, 24 if side else 36)
        line = (*color, 190)
        pygame.draw.rect(overlay, fill, rect)
        pygame.draw.rect(overlay, line, rect, 1)
        surface_y = getattr(ter, "surface_y", None)
        if surface_y is not None and side in {"top", "bottom"}:
            y = int(round(float(surface_y)))
            pygame.draw.line(overlay, (*color, 230), (rect.left, y), (rect.right, y), 2)
    target.blit(overlay, (0, 0))
    _draw_label(target, f"runtime collision overlay  x={int(camera_x)}")


def _update_runtime_scene(scene: GameScene, camera_x: float) -> None:
    scene.camera.x = float(camera_x)
    scene.camera.scroll_speed = 0.0
    scene._stage_scroll_speed = 0.0
    scene._stage_banner_timer = 0.0
    if getattr(scene, "_debug_panel", None) is not None:
        scene._debug_panel._open = False

    scene.spawner.update(0.0, scene.camera)
    for ter in list(scene.terrain):
        ter.update(0.0, scene.camera)
    for enemy in list(scene.enemies):
        enemy.update(0.0, scene.camera)
    for item in list(scene.items):
        item.update(0.0, scene.camera)


def _runtime_captures(camera_xs: list[float], out_dir: Path) -> dict[float, tuple[Path, Path]]:
    game = Game()
    scene = GameScene(game, stage_id=3)
    game._scene = scene
    scene.on_enter()
    scene._debug_draw_overlay = lambda screen: None  # type: ignore[method-assign]

    captures: dict[float, tuple[Path, Path]] = {}
    for camera_x in sorted(camera_xs):
        _update_runtime_scene(scene, camera_x)
        scene.draw(game.screen)
        normal = game.screen.copy()
        _draw_label(normal, f"runtime normal  x={int(camera_x)}")
        normal_path = out_dir / f"x{int(camera_x):05d}_runtime.png"
        pygame.image.save(normal, str(normal_path))

        collision = normal.copy()
        _draw_collision_overlay(collision, scene.terrain, camera_x=camera_x)
        collision_path = out_dir / f"x{int(camera_x):05d}_collision.png"
        pygame.image.save(collision, str(collision_path))
        captures[camera_x] = (normal_path, collision_path)
    return captures


def _composer_captures(
    camera_xs: list[float],
    out_dir: Path,
    *,
    stage_path: Path,
    rects_path: Path,
    mask_dir: Path,
) -> dict[float, Path]:
    segments = _stage3_segments(stage_path)
    composer_options = _composer_options(stage_path)
    pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
    captures: dict[float, Path] = {}
    for camera_x in sorted(camera_xs):
        surface = _load_backdrop(SCREEN_WIDTH, SCREEN_HEIGHT)
        render_stage3_composer_surface(
            surface,
            segments,
            pieces,
            camera_x=camera_x,
            debug_lines=True,
            **composer_options,
        )
        _draw_label(surface, f"composer preview  x={int(camera_x)}")
        path = out_dir / f"x{int(camera_x):05d}_composer.png"
        pygame.image.save(surface, str(path))
        captures[camera_x] = path
    return captures


def _image_src(path: Path, *, embed_images: bool) -> str:
    if not embed_images:
        return html.escape(path.name)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _write_index(
    out_dir: Path,
    camera_xs: list[float],
    runtime: dict[float, tuple[Path, Path]],
    composer: dict[float, Path],
    *,
    embed_images: bool,
) -> Path:
    rows: list[str] = []
    for camera_x in sorted(camera_xs):
        normal_path, collision_path = runtime[camera_x]
        composer_path = composer[camera_x]
        normal_src = _image_src(normal_path, embed_images=embed_images)
        collision_src = _image_src(collision_path, embed_images=embed_images)
        composer_src = _image_src(composer_path, embed_images=embed_images)
        rows.append(
            f"""
      <section class="shot">
        <h2>x={int(camera_x)}</h2>
        <figure><figcaption>runtime normal</figcaption><img src="{normal_src}" alt="runtime normal x={int(camera_x)}"></figure>
        <figure><figcaption>runtime collision</figcaption><img src="{collision_src}" alt="runtime collision x={int(camera_x)}"></figure>
        <figure><figcaption>composer preview</figcaption><img src="{composer_src}" alt="composer preview x={int(camera_x)}"></figure>
      </section>
"""
        )
    index = out_dir / ("index_embedded.html" if embed_images else "index.html")
    index.write_text(
        f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>Stage3 Composer Review</title>
  <style>
    body {{
      margin: 24px;
      background: #0b1012;
      color: #e4ece9;
      font-family: Consolas, "Yu Gothic", monospace;
    }}
    h1, h2 {{
      font-weight: 600;
    }}
    .shot {{
      display: grid;
      grid-template-columns: repeat(3, minmax(260px, 1fr));
      gap: 14px;
      margin: 0 0 30px;
      align-items: start;
    }}
    .shot h2 {{
      grid-column: 1 / -1;
      margin: 0;
    }}
    figure {{
      margin: 0;
    }}
    figcaption {{
      margin: 0 0 6px;
      color: #a9c4c1;
      font-size: 14px;
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      background: #050708;
      border: 1px solid #26383a;
    }}
  </style>
</head>
<body>
  <h1>Stage3 Composer Review</h1>
  {''.join(rows)}
</body>
</html>
""",
        encoding="utf-8",
    )
    return index


def _open_file(path: Path) -> bool:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        print(f"[stage3-composer-report] open failed: {exc}")
        return False
    return True


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage3 composer review captures")
    parser.add_argument("--stage-json", default=str(DEFAULT_STAGE), help="Stage JSON path")
    parser.add_argument("--rects", default=str(ROOT / "tools" / "stage3_terrain_rects.json"), help="Rect JSON path")
    parser.add_argument("--mask-dir", default=str(DEFAULT_MASK_DIR), help="Manual alpha mask directory")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory")
    parser.add_argument("--x", type=float, action="append", default=[], help="Camera X to capture; can be repeated")
    parser.add_argument("--embed-images", action="store_true", help="Embed PNGs into the generated HTML")
    open_group = parser.add_mutually_exclusive_group()
    open_group.add_argument(
        "--open",
        dest="open_preview",
        action="store_true",
        default=True,
        help="Open generated HTML preview (default)",
    )
    open_group.add_argument(
        "--no-open",
        dest="open_preview",
        action="store_false",
        help="Do not open generated HTML preview",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        pygame.init()
        pygame.font.init()
        out_dir = _resolve(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        camera_xs = sorted(set(args.x or list(DEFAULT_VIEW_X)))
        runtime = _runtime_captures(camera_xs, out_dir)
        composer = _composer_captures(
            camera_xs,
            out_dir,
            stage_path=_resolve(args.stage_json),
            rects_path=_resolve(args.rects),
            mask_dir=_resolve(args.mask_dir),
        )
        index = _write_index(out_dir, camera_xs, runtime, composer, embed_images=args.embed_images)
        for camera_x in camera_xs:
            normal, collision = runtime[camera_x]
            print(normal)
            print(collision)
            print(composer[camera_x])
        print(index)
        if args.open_preview and _open_file(index):
            print(f"opened: {index}")
        return 0
    except Exception as exc:
        print(f"[stage3-composer-report] error: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
