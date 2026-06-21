"""ゲームプレイをヘッドレスで進めて、アニメーション GIF に書き出すツール。

離席中でも PR をスマホで判断できるよう、「起動して遊ぶ」代わりに数秒の
プレイ動画(GIF)を生成して PR に添付する用途。シーンの構築・進行は
tools/headless.py の共有ハーネスを使う（capture と同じ駆動ロジック）。

GIF 化に Pillow を使う（`pip install -e ".[dev]"` で入る）。

使い方:
  # ステージ1 を撮ってGIF化（既定: 40コマ・4フレーム間隔・0.6倍）
  python tools/gameplay_clip.py --stage 1 --out captures/stage1.gif

  # ステージ4 ボス第3形態のクリップ
  python tools/gameplay_clip.py --stage 4 --boss --form 3 --out captures/s4boss.gif

操作キーの保持は --hold（既定 fire）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ヘッドレス設定（SDL ダミー）は headless の import 時に済む。
from tools.headless import (  # noqa: E402
    apply_weapon,
    build_game_scene,
    hold_keys_from_names,
    skip_to_fight,
    step_frame,
)

import pygame  # noqa: E402

from src.core.registries import stage_ids  # noqa: E402


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", type=int, default=1, help="ステージID（既定1）")
    p.add_argument("--frames", type=int, default=60, help="撮影開始までの warmup フレーム数（既定60）")
    p.add_argument("--shots", type=int, default=40, help="GIF のコマ数（既定40）")
    p.add_argument("--interval", type=int, default=4, help="GIF 1コマあたりのゲームフレーム数（既定4）")
    p.add_argument("--dt", type=float, default=1.0 / 60.0, help="1フレームの経過秒（既定 1/60）")
    p.add_argument("--scale", type=float, default=0.6, help="出力倍率（既定0.6＝480x360）")
    p.add_argument("--loop", type=int, default=0, help="GIFループ回数（0=無限、既定0）")

    p.add_argument("--boss", action="store_true", help="ボス戦へ即移行")
    p.add_argument("--form", type=int, choices=(1, 2, 3), default=1, help="ボスのフォーム（ステージ4のみ）")

    p.add_argument("--main", type=int, default=0, help="メインウェポンLv 0-5")
    p.add_argument("--laser", type=int, default=0, help="レーザーLv 0-6")
    p.add_argument("--homing", type=int, default=0, help="ホーミングLv 0-7")
    p.add_argument("--speed", type=int, default=0, help="スピードLv 0-5")
    p.add_argument("--magnet", type=int, default=0, help="マグネットLv 0-3")
    p.add_argument("--barrier", action="store_true", help="バリア付与")

    p.add_argument("--invincible", action=argparse.BooleanOptionalAction, default=True,
                   help="無敵＋HP維持で死亡・点滅を防ぐ（既定 ON）")
    p.add_argument("--hold", default="fire",
                   help="毎フレーム押し続けるキー（カンマ区切り）: fire,laser,up,down,left,right")
    p.add_argument("--out", default="captures/clip.gif", help="出力GIFパス（既定 captures/clip.gif）")
    return p.parse_args(argv)


def _surface_to_pil(surface: pygame.Surface, scale: float):
    from PIL import Image
    raw = pygame.image.tostring(surface, "RGB")
    img = Image.frombytes("RGB", surface.get_size(), raw)
    if scale and scale != 1.0:
        w, h = img.size
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return img


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        import PIL  # noqa: F401
    except ModuleNotFoundError:
        print("Pillow が必要です: pip install -e \".[dev]\"  (または pip install Pillow)",
              file=sys.stderr)
        return 2

    valid = set(stage_ids())
    if args.stage not in valid and args.stage != 99:
        print(f"unknown stage {args.stage} (available: {sorted(valid)})", file=sys.stderr)
        return 2

    hold = hold_keys_from_names(args.hold)

    game, scene = build_game_scene(args.stage)
    apply_weapon(scene, main=args.main, laser=args.laser, homing=args.homing,
                 speed=args.speed, magnet=args.magnet, barrier=args.barrier)

    if args.boss:
        if not skip_to_fight(scene, args.stage, form=args.form, dt=args.dt,
                             hold=hold, invincible=args.invincible):
            print("warning: boss intro did not reach 'fighting' within frame cap", file=sys.stderr)

    for _ in range(max(0, args.frames)):
        step_frame(scene, dt=args.dt, hold=hold, invincible=args.invincible)

    frames = []
    for i in range(max(1, args.shots)):
        if i > 0:
            for _ in range(max(1, args.interval)):
                step_frame(scene, dt=args.dt, hold=hold, invincible=args.invincible)
        frames.append(_surface_to_pil(game.screen, args.scale))

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out = out.with_suffix(".gif")

    # 実時間に近い再生速度: 1コマ = interval ゲームフレーム分の経過。
    duration_ms = max(20, int(args.interval * args.dt * 1000))
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=args.loop,
        optimize=True,
    )
    print(out)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
