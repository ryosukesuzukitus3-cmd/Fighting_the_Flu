"""ビジュアル回帰: 既知のゲーム状態を決定論的に撮影し、baseline と差分を出す。

このゲームは粒子・スポーンで random を多用し、HUD/会話の点滅は壁時計
（pygame.time.get_ticks）に依存する。再現性を確保するため本ツールは
  - グローバル random をシード固定（local な random.Random(...) は元々安定seed）
  - pygame.time.get_ticks を固定値へ差し替え（点滅位相を固定）
する。これで同一コードなら再描画しても差分ゼロになる。

差分はピクセル比較で「変わった所」をヒートマップ化し、baseline|current|diff の
自己完結HTMLにまとめる。pass/fail ゲートではなく、人間がスマホで「何が変わったか」を
見るための“気づき”ツール（離席レビュー用）。撮影は tools/headless.py の共有
ハーネスを使う（capture/clip と同じ駆動ロジック）。

  # baseline を現在のコードから生成（意図した見た目変更を確定したあとに実行）
  python tools/visual_regression.py --update

  # 現在のコードを baseline と比較してHTMLレポート生成
  python tools/visual_regression.py
"""
from __future__ import annotations

import argparse
import base64
import io
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ヘッドレス設定（SDL ダミー）は headless の import 時に済む。
from tools.headless import (  # noqa: E402
    HOLD_KEYS,
    apply_weapon,
    build_game_scene,
    skip_to_fight,
    step_frame,
)

import pygame  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

SEED = 12345
BASELINE_DIR = ROOT / "tests" / "baselines"
DEFAULT_HTML = ROOT / ".html" / "visual_regression.html"
DIFF_THRESHOLD = 16    # チャンネル差がこれ未満は「変化なし」とみなす（AAノイズ吸収）
CHANGED_RATIO = 0.001  # 変化ピクセルがこの割合を超えたら CHANGED 表示

# SSOT: 撮影する状態の行列。name -> 撮影スペック。
# frames は撮影前に進めるフレーム数。boss=True でボス戦へ早送り。
SHOTS: dict[str, dict] = {
    "stage1_intro":   dict(stage=1, frames=2),
    "stage1_play":    dict(stage=1, frames=150, hold=("fire",), main=3),
    "stage2_play":    dict(stage=2, frames=150, hold=("fire",), main=3),
    "stage2_boss":    dict(stage=2, boss=True, frames=60),
    "stage3_boss":    dict(stage=3, boss=True, frames=60),
    "stage4_boss_f1": dict(stage=4, boss=True, form=1, frames=60),
    "stage4_boss_f2": dict(stage=4, boss=True, form=2, frames=60),
    "stage4_boss_f3": dict(stage=4, boss=True, form=3, frames=60),
}


def _freeze_clock() -> None:
    """壁時計依存の点滅（HUD/会話）を固定位相にして決定論化する。"""
    pygame.time.get_ticks = lambda: 0  # type: ignore[assignment]


def render_shot(spec: dict) -> Image.Image:
    """1状態を決定論的に描画して PIL Image で返す。"""
    random.seed(SEED)
    _freeze_clock()

    game, scene = build_game_scene(spec["stage"])
    apply_weapon(
        scene,
        main=spec.get("main", 0), laser=spec.get("laser", 0),
        homing=spec.get("homing", 0), speed=spec.get("speed", 0),
        magnet=spec.get("magnet", 0), barrier=spec.get("barrier", False),
    )
    hold = [HOLD_KEYS[n] for n in spec.get("hold", ())]

    if spec.get("boss"):
        skip_to_fight(scene, spec["stage"], form=spec.get("form", 1), hold=hold)

    for _ in range(spec.get("frames", 60)):
        step_frame(scene, hold=hold, invincible=True)

    to_bytes = getattr(pygame.image, "tobytes", pygame.image.tostring)
    raw = to_bytes(game.screen, "RGB")
    img = Image.frombytes("RGB", game.screen.get_size(), raw)
    pygame.quit()
    return img


def _change_ratio(base: Image.Image, cur: Image.Image) -> float:
    if base.size != cur.size:
        return 1.0
    diff = ImageChops.difference(base.convert("RGB"), cur.convert("RGB"))
    gray = diff.convert("L")
    total = base.size[0] * base.size[1]
    changed = sum(c for v, c in enumerate(gray.histogram()) if v > DIFF_THRESHOLD)
    return changed / total if total else 0.0


def _heatmap(base: Image.Image, cur: Image.Image) -> Image.Image:
    if base.size != cur.size:
        return cur.convert("RGB")
    diff = ImageChops.difference(base.convert("RGB"), cur.convert("RGB"))
    return diff.point(lambda p: min(255, p * 6))  # 視認性のため増幅


def _montage(panels: list[Image.Image], panel_w: int = 360) -> Image.Image:
    scaled = []
    for im in panels:
        w, h = im.size
        scaled.append(im.convert("RGB").resize((panel_w, max(1, int(h * panel_w / w)))))
    ph = scaled[0].size[1]
    out = Image.new("RGB", (panel_w * len(scaled), ph), (0, 0, 0))
    for i, im in enumerate(scaled):
        out.paste(im, (i * panel_w, 0))
    return out


def _b64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _cmd_update() -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    for name, spec in SHOTS.items():
        img = render_shot(spec)
        path = BASELINE_DIR / f"{name}.png"
        img.save(path)
        print(f"baseline saved: {path.relative_to(ROOT)}  ({img.size[0]}x{img.size[1]})")
    print(f"\n{len(SHOTS)} baselines updated.")
    return 0


def _cmd_compare(out_path: Path) -> int:
    rows = []
    missing = []
    for name, spec in SHOTS.items():
        cur = render_shot(spec)
        base_path = BASELINE_DIR / f"{name}.png"
        if not base_path.exists():
            missing.append(name)
            rows.append((name, None, _montage([cur, cur, Image.new("RGB", cur.size, (0, 0, 0))])))
            continue
        base = Image.open(base_path)
        ratio = _change_ratio(base, cur)
        heat = _heatmap(base, cur)
        rows.append((name, ratio, _montage([base, cur, heat])))

    rows.sort(key=lambda r: (-1.0 if r[1] is None else r[1]), reverse=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "<!doctype html><meta charset='utf-8'>",
        "<title>Visual Regression</title>",
        "<style>body{background:#111;color:#ddd;font-family:sans-serif;margin:16px}"
        "h1{font-size:18px}.shot{margin:18px 0;border-top:1px solid #333;padding-top:10px}"
        ".tag{font-weight:bold}.chg{color:#ff7b7b}.ok{color:#7bff9b}.miss{color:#ffd27b}"
        ".hdr{color:#888;font-size:12px}img{width:100%;max-width:1080px;display:block}</style>",
        "<h1>Visual Regression（左: baseline / 中: current / 右: diff）</h1>",
        "<p class='hdr'>決定論描画（random固定＋clock固定）。pass/fail ではなく目視レビュー用。</p>",
    ]
    changed = 0
    for name, ratio, montage in rows:
        if ratio is None:
            label = "<span class='miss'>NO BASELINE（--update が必要）</span>"
        elif ratio > CHANGED_RATIO:
            changed += 1
            label = f"<span class='chg'>CHANGED {ratio*100:.2f}%</span>"
        else:
            label = f"<span class='ok'>unchanged {ratio*100:.3f}%</span>"
        parts.append(
            f"<div class='shot'><div class='tag'>{name} — {label}</div>"
            f"<div class='hdr'>baseline | current | diff</div>"
            f"<img src='data:image/png;base64,{_b64_png(montage)}'></div>"
        )
    out_path.write_text("\n".join(parts), encoding="utf-8")

    print("\n=== visual regression ===")
    for name, ratio, _ in rows:
        if ratio is None:
            print(f"  MISSING    {name}  (run --update)")
        elif ratio > CHANGED_RATIO:
            print(f"  CHANGED    {name}  {ratio*100:.2f}%")
        else:
            print(f"  unchanged  {name}  {ratio*100:.3f}%")
    print(f"\nreport: {out_path}")
    print(f"changed: {changed} / {len(SHOTS)}  (missing: {len(missing)})")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--update", action="store_true", help="現在のコードから baseline を再生成する")
    p.add_argument("--out", default=str(DEFAULT_HTML), help="比較レポートHTMLの出力先")
    args = p.parse_args(argv)

    if args.update:
        return _cmd_update()
    return _cmd_compare(Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
