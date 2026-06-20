"""Preview Stage3 terrain source rects.

Rect definitions live in JSON so they can be edited while checking pixel
coordinates in Paint or another image editor.

Examples:
  python tools/stage3_rect_preview.py
  python tools/stage3_rect_preview.py --group block_wide --group block_square
  python tools/stage3_rect_preview.py --out captures/stage3_rect_check
  python tools/stage3_rect_preview.py --open
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "tools" / "stage3_terrain_rects.json"
DEFAULT_OUT = ROOT / "captures" / "stage3_rect_preview"
PALETTE = (
    (255, 91, 91),
    (255, 190, 64),
    (64, 210, 255),
    (145, 255, 115),
    (210, 120, 255),
    (255, 138, 218),
    (120, 190, 255),
)


@dataclass(frozen=True)
class RectSpec:
    x: int
    y: int
    w: int
    h: int
    label: str = ""


@dataclass(frozen=True)
class RectGroup:
    name: str
    color: tuple[int, int, int]
    rects: tuple[RectSpec, ...]


def _resolve(path: str | Path, *, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def _rect_from_json(raw: Any, *, index: int, group: str) -> RectSpec:
    if isinstance(raw, dict):
        try:
            x = int(raw["x"])
            y = int(raw["y"])
            w = int(raw["w"])
            h = int(raw["h"])
        except KeyError as exc:
            raise ValueError(f"{group}[{index}] missing key: {exc.args[0]}") from exc
        return RectSpec(x, y, w, h, str(raw.get("label", "")))
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        x, y, w, h = (int(v) for v in raw[:4])
        label = str(raw[4]) if len(raw) >= 5 else ""
        return RectSpec(x, y, w, h, label)
    raise ValueError(f"{group}[{index}] must be {{x,y,w,h}} or [x,y,w,h]")


def _load_config(path: Path) -> tuple[Path, dict[str, RectGroup]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sheet = _resolve(data.get("sheet", "assets/graphic/stage3_fortress_terrain_sheet.png"))
    groups_raw = data.get("groups")
    if not isinstance(groups_raw, dict):
        raise ValueError("config must contain object key: groups")

    groups: dict[str, RectGroup] = {}
    for i, (name, value) in enumerate(groups_raw.items()):
        if isinstance(value, dict):
            rects_raw = value.get("rects", [])
            color_raw = value.get("color", PALETTE[i % len(PALETTE)])
        else:
            rects_raw = value
            color_raw = PALETTE[i % len(PALETTE)]
        if not isinstance(rects_raw, list):
            raise ValueError(f"{name}.rects must be a list")
        if not isinstance(color_raw, (list, tuple)) or len(color_raw) < 3:
            raise ValueError(f"{name}.color must be [r,g,b]")
        color = tuple(max(0, min(255, int(v))) for v in color_raw[:3])
        rects = tuple(_rect_from_json(raw, index=j, group=name) for j, raw in enumerate(rects_raw))
        groups[name] = RectGroup(name=name, color=color, rects=rects)
    return sheet, groups


def _selected_groups(groups: dict[str, RectGroup], requested: list[str]) -> list[RectGroup]:
    if not requested:
        return list(groups.values())
    names: list[str] = []
    for arg in requested:
        names.extend(part.strip() for part in arg.split(",") if part.strip())
    missing = [name for name in names if name not in groups]
    if missing:
        available = ", ".join(groups)
        raise ValueError(f"unknown group(s): {', '.join(missing)}; available: {available}")
    return [groups[name] for name in names]


def _validate_rects(sheet: pygame.Surface, groups: list[RectGroup]) -> None:
    bounds = pygame.Rect(0, 0, *sheet.get_size())
    errors: list[str] = []
    for group in groups:
        for i, rect in enumerate(group.rects, 1):
            if rect.w <= 0 or rect.h <= 0:
                errors.append(f"{group.name} #{i}: w/h must be positive")
                continue
            r = pygame.Rect(rect.x, rect.y, rect.w, rect.h)
            if not bounds.contains(r):
                errors.append(f"{group.name} #{i}: out of sheet bounds {tuple(r)}")
    if errors:
        raise ValueError("\n".join(errors))


def _font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont("consolas", size) or pygame.font.Font(None, size)


def _draw_label(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    color: tuple[int, int, int],
    font: pygame.font.Font,
) -> None:
    label = font.render(text, True, color)
    bg = pygame.Rect(pos[0], pos[1], label.get_width() + 6, label.get_height() + 4)
    pygame.draw.rect(surface, (8, 10, 13), bg)
    surface.blit(label, (pos[0] + 3, pos[1] + 2))


def _draw_grid(surface: pygame.Surface, step: int, font: pygame.font.Font) -> None:
    if step <= 0:
        return
    w, h = surface.get_size()
    for x in range(0, w, step):
        pygame.draw.line(surface, (60, 72, 84), (x, 0), (x, h), 1)
        _draw_label(surface, str(x), (x + 2, 2), (176, 190, 202), font)
    for y in range(0, h, step):
        pygame.draw.line(surface, (60, 72, 84), (0, y), (w, y), 1)
        _draw_label(surface, str(y), (2, y + 2), (176, 190, 202), font)


def _render_overlay(
    sheet: pygame.Surface,
    groups: list[RectGroup],
    out: Path,
    *,
    grid_step: int,
) -> Path:
    overlay = sheet.copy()
    small = _font(14)
    _draw_grid(overlay, grid_step, small)
    for group in groups:
        for i, rect in enumerate(group.rects, 1):
            r = pygame.Rect(rect.x, rect.y, rect.w, rect.h)
            pygame.draw.rect(overlay, group.color, r, 3)
            label = rect.label or f"{group.name}:{i}"
            _draw_label(overlay, label, (rect.x + 3, rect.y + 3), group.color, small)
    path = out.with_name(f"{out.name}_overlay.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(overlay, str(path))
    return path


def _render_group_sheet(
    sheet: pygame.Surface,
    group: RectGroup,
    out: Path,
    *,
    cell_w: int,
    cell_h: int,
    cols: int,
    max_preview_h: int,
) -> Path:
    margin = 16
    header_h = 38
    rows = max(1, (len(group.rects) + cols - 1) // cols)
    surface = pygame.Surface((margin * 2 + cols * cell_w, margin * 2 + header_h + rows * cell_h))
    surface.fill((18, 20, 24))
    font = _font(18)
    small = _font(14)
    title = font.render(f"{group.name} ({len(group.rects)} rects)", True, group.color)
    surface.blit(title, (margin, margin))

    for i, rect in enumerate(group.rects):
        col = i % cols
        row = i // cols
        cx = margin + col * cell_w
        cy = margin + header_h + row * cell_h
        crop = sheet.subsurface(pygame.Rect(rect.x, rect.y, rect.w, rect.h)).copy()
        scale = min((cell_w - 20) / rect.w, max_preview_h / rect.h, 1.5)
        preview_w = max(1, int(rect.w * scale))
        preview_h = max(1, int(rect.h * scale))
        crop = pygame.transform.smoothscale(crop, (preview_w, preview_h))
        frame = pygame.Rect(cx, cy, cell_w - 10, cell_h - 12)
        pygame.draw.rect(surface, (34, 38, 44), frame)
        pygame.draw.rect(surface, group.color, frame, 1)
        surface.blit(crop, (cx + 8, cy + 8))
        label = rect.label or f"#{i + 1}"
        lines = (f"{label} x{rect.x} y{rect.y}", f"{rect.w} x {rect.h}")
        for j, line in enumerate(lines):
            color = (226, 226, 226) if j == 0 else (180, 184, 190)
            text = small.render(line, True, color)
            surface.blit(text, (cx + 8, cy + max_preview_h + 20 + j * 18))

    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in group.name)
    path = out.with_name(f"{out.name}_{safe_name}.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))
    return path


def _write_index(paths: list[Path], out: Path) -> Path:
    path = out.with_name(f"{out.name}_index.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    cards = []
    for image_path in paths:
        src = html.escape(image_path.name, quote=True)
        caption = html.escape(image_path.stem)
        cards.append(f'<section><h2>{caption}</h2><img src="{src}" alt="{caption}"></section>')
    body = "\n".join(cards)
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stage3 Rect Preview</title>
  <style>
    body {{
      margin: 24px;
      background: #111418;
      color: #e6e8eb;
      font-family: Consolas, monospace;
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
      border: 1px solid #3a424c;
      background: #0b0d10;
    }}
  </style>
</head>
<body>
  <h1>Stage3 Rect Preview</h1>
  {body}
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _should_open_preview(open_arg: bool | None) -> bool:
    if open_arg is not None:
        return open_arg
    return os.name == "nt" and sys.stdout.isatty() and not os.environ.get("CI")


def _open_file(path: Path) -> bool:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"[stage3-rect-preview] open failed: {exc}")
        return False
    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="rect定義JSON")
    p.add_argument("--sheet", default=None, help="素材画像。未指定ならconfigのsheet")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="出力ファイルprefix")
    p.add_argument("--group", action="append", default=[], help="出力するグループ名。複数指定/カンマ区切り可")
    p.add_argument("--grid-step", type=int, default=100, help="overlayに描く座標グリッド間隔。0で無効")
    p.add_argument("--cell-w", type=int, default=240, help="グループ一覧の1セル幅")
    p.add_argument("--cell-h", type=int, default=190, help="グループ一覧の1セル高さ")
    p.add_argument("--cols", type=int, default=4, help="グループ一覧の列数")
    p.add_argument("--max-preview-h", type=int, default=120, help="グループ一覧内の切り出し表示最大高さ")
    p.add_argument("--open", dest="open_preview", action="store_true", help="open the generated HTML preview")
    p.add_argument("--no-open", dest="open_preview", action="store_false", help="do not open the generated HTML preview")
    p.set_defaults(open_preview=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pygame.init()
    pygame.font.init()
    try:
        config = _resolve(args.config)
        sheet_path, groups = _load_config(config)
        if args.sheet:
            sheet_path = _resolve(args.sheet)
        sheet = pygame.image.load(str(sheet_path))
        selected = _selected_groups(groups, args.group)
        _validate_rects(sheet, selected)
        out = _resolve(args.out)
        paths = [_render_overlay(sheet, selected, out, grid_step=args.grid_step)]
        paths.extend(
            _render_group_sheet(
                sheet,
                group,
                out,
                cell_w=args.cell_w,
                cell_h=args.cell_h,
                cols=args.cols,
                max_preview_h=args.max_preview_h,
            )
            for group in selected
        )
        index_path = _write_index(paths, out)
    except (OSError, json.JSONDecodeError, pygame.error, ValueError) as exc:
        print(f"[stage3-rect-preview] error: {exc}")
        return 2

    for path in paths:
        print(path)
    print(index_path)
    if _should_open_preview(args.open_preview) and _open_file(index_path):
        print(f"opened: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
