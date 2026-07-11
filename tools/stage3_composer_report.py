"""Generate a stage composer review report.

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
    render_stage3_piece_surface,
)
from src.entities.terrain_query import iter_collidable_terrain  # noqa: E402
from src.scenes.game_scene import GameScene  # noqa: E402
from tools.stage_terrain_profiles import (  # noqa: E402
    DEFAULT_STAGE_ID,
    STAGE_TERRAIN_PROFILES,
    StageTerrainProfile,
    resolve_stage_terrain_profile,
    stage_id_from_json,
)

DEFAULT_PROFILE = STAGE_TERRAIN_PROFILES[DEFAULT_STAGE_ID]
DEFAULT_STAGE = DEFAULT_PROFILE.stage_json
DEFAULT_RECTS = DEFAULT_PROFILE.rects
DEFAULT_MASK_DIR = DEFAULT_PROFILE.mask_dir
DEFAULT_OUT = ROOT / "captures" / "stage3_composer_report"
DEFAULT_VIEW_X = DEFAULT_PROFILE.preview_camera_xs
BACKGROUND_PATH = DEFAULT_PROFILE.background


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _stage_layout(stage_path: Path) -> dict[str, Any]:
    data = json.loads(stage_path.read_text(encoding="utf-8"))
    layouts = data.get("terrain_layout", [])
    if not layouts:
        raise ValueError(f"{stage_path} does not contain terrain_layout")
    layout = layouts[0]
    if layout.get("type") not in {"AuthoredTerrain", "TerrainPath", "TerrainStrip", "TerrainPieces"}:
        raise ValueError("stage composer report expects a supported terrain layout")
    return layout


_stage3_layout = _stage_layout


def _stage_segments(stage_path: Path) -> list[Any]:
    from src.entities.terrain import make_terrain_segments_from_event

    layout = _stage_layout(stage_path)
    if layout.get("type") == "TerrainPieces":
        raise ValueError("TerrainPieces does not have continuous terrain segments")
    start_x = float(layout.get("start_offset", 0))
    return make_terrain_segments_from_event(
        layout,
        start_x,
        default_seed=stage_id_from_json(stage_path),
    )


_stage3_segments = _stage_segments


def _profile_from_args(args: argparse.Namespace) -> StageTerrainProfile:
    return resolve_stage_terrain_profile(
        stage_id=args.stage,
        stage_json=_resolve(args.stage_json) if args.stage_json else None,
    )


def _profile_path(primary: Path, fallback: Path | None) -> Path:
    return primary if primary.exists() or fallback is None else fallback


def _require_runtime_stage_path(stage_path: Path, profile: StageTerrainProfile) -> None:
    if stage_path.resolve() != profile.stage_json.resolve():
        raise ValueError(
            "stage-composer-report compares against runtime canonical data; "
            "use the selected profile stage JSON or stage-terrain-composer for custom JSON"
        )


def _composer_paths(
    args: argparse.Namespace,
    profile: StageTerrainProfile,
    layout: dict[str, Any],
) -> tuple[Path, Path, Path]:
    rects_path = (
        _resolve(args.rects)
        if args.rects
        else _resolve(layout["composer_rects"])
        if layout.get("composer_rects")
        else _profile_path(profile.rects, profile.fallback_rects)
    )
    mask_dir = (
        _resolve(args.mask_dir)
        if args.mask_dir
        else _resolve(layout["composer_mask_dir"])
        if layout.get("composer_mask_dir")
        else _profile_path(profile.mask_dir, profile.fallback_mask_dir)
    )
    background_path = (
        _resolve(args.background)
        if args.background
        else _resolve(layout["composer_background"])
        if layout.get("composer_background")
        else profile.background
    )
    return rects_path, mask_dir, background_path


def _composer_options(stage_path: Path) -> dict[str, int]:
    layout = _stage_layout(stage_path)
    return {
        "sample_step": int(layout.get("composer_sample_step", 48)),
        "tolerance": int(layout.get("composer_tolerance", 26)),
        "collision_step": int(layout.get("composer_collision_step", 8)),
        "collision_tolerance": int(layout.get("composer_collision_tolerance", 10)),
        "overlap": int(layout.get("composer_overlap", 0)),
    }


def _load_backdrop(width: int, height: int, background_path: Path = BACKGROUND_PATH) -> pygame.Surface:
    surface = pygame.Surface((width, height))
    surface.fill((6, 14, 17))
    try:
        raw = pygame.image.load(str(background_path))
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


def _runtime_captures(
    camera_xs: list[float],
    out_dir: Path,
    *,
    stage_id: int = DEFAULT_STAGE_ID,
) -> dict[float, tuple[Path, Path]]:
    game = Game()
    scene = GameScene(game, stage_id=stage_id)
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
    background_path: Path = BACKGROUND_PATH,
) -> dict[float, Path]:
    layout = _stage_layout(stage_path)
    segments = None if layout.get("type") == "TerrainPieces" else _stage_segments(stage_path)
    composer_options = _composer_options(stage_path)
    pieces = load_stage3_composer_pieces(rects_path, mask_dir=mask_dir)
    captures: dict[float, Path] = {}
    for camera_x in sorted(camera_xs):
        surface = _load_backdrop(SCREEN_WIDTH, SCREEN_HEIGHT, background_path)
        if layout.get("type") == "TerrainPieces":
            render_stage3_piece_surface(
                surface,
                layout,
                pieces,
                camera_x=camera_x,
                start_x=int(layout.get("x", layout.get("world_x", 0))),
                collision_step=composer_options["collision_step"],
                collision_tolerance=composer_options["collision_tolerance"],
                debug_lines=True,
            )
        else:
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
    label: str = "Stage3",
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
  <title>{html.escape(label)} Composer Review</title>
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
  <h1>{html.escape(label)} Composer Review</h1>
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
        print(f"[stage-composer-report] open failed: {exc}")
        return False
    return True


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stage-composer-report",
        description="Generate stage composer review captures",
    )
    parser.add_argument("--stage", type=int, choices=sorted(STAGE_TERRAIN_PROFILES), default=None, help="stage profile (default: 3; inferred from --stage-json)")
    parser.add_argument("--stage-json", default=None, help="Stage JSON path (defaults to selected stage)")
    parser.add_argument("--rects", default=None, help="Rect JSON path (explicit > stage layout > profile)")
    parser.add_argument("--mask-dir", default=None, help="Manual alpha mask directory (explicit > stage layout > profile)")
    parser.add_argument("--background", default=None, help="Background image path (explicit > stage layout > profile)")
    parser.add_argument("--out", default=None, help="Output directory (defaults to selected stage)")
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
        profile = _profile_from_args(args)
        stage_path = _resolve(args.stage_json) if args.stage_json else profile.stage_json
        _require_runtime_stage_path(stage_path, profile)
        layout = _stage_layout(stage_path)
        rects_path, mask_dir, background_path = _composer_paths(args, profile, layout)
        out_dir = _resolve(args.out) if args.out else ROOT / "captures" / f"stage{profile.stage_id}_composer_report"
        out_dir.mkdir(parents=True, exist_ok=True)
        camera_xs = sorted(set(args.x or list(profile.preview_camera_xs)))
        runtime = _runtime_captures(camera_xs, out_dir, stage_id=profile.stage_id)
        composer = _composer_captures(
            camera_xs,
            out_dir,
            stage_path=stage_path,
            rects_path=rects_path,
            mask_dir=mask_dir,
            background_path=background_path,
        )
        index = _write_index(
            out_dir,
            camera_xs,
            runtime,
            composer,
            embed_images=args.embed_images,
            label=profile.label,
        )
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
        print(f"[stage-composer-report] error: {exc}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
