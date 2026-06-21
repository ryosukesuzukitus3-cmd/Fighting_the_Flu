"""任意のゲーム状態をヘッドレスで再現し、画面を PNG として保存する汎用ツール。

実際の GameScene をダミードライバ（SDL_VIDEODRIVER=dummy）で駆動するので、
本物のプレイ画面・UI・ボス演出・弾幕がそのまま撮れる。生成した PNG は
そのまま画像として確認できる（Claude が開発中に見た目を自己検証する用途）。

シーンの構築・1フレーム進行・ボス戦への早送りは tools/headless.py に集約
（capture / gameplay_clip / スモークテストで共有する SSOT）。

使い方:
  # ステージ1 を 90 フレーム進めて1枚
  python tools/capture.py --stage 1 --frames 90

  # ステージ4 のボス戦・第3形態（投了王サワグチ）を撮る
  python tools/capture.py --stage 4 --boss --form 3 --frames 60

  # 武器フル強化で弾を撃たせて 5 枚連番
  python tools/capture.py --stage 2 --main 5 --laser 6 --homing 7 \
      --shots 5 --interval 8

  # 出力先を指定
  python tools/capture.py --stage 1 --out captures/stage1_intro

操作キーの保持は --hold で指定（既定は fire）。
  名前: fire / laser / up / down / left / right
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

from src.core.game import Game  # noqa: E402
from src.core.registries import stage_ids  # noqa: E402

# --cutscene の名前 → (script.py の定数名, テーマ)
_CUTSCENES = {
    "prologue":   ("PROLOGUE",                   "dark"),
    "interlude1": ("INTERLUDE_STAGE1_CLEAR",     "dark"),
    "blackhole":  ("INTERLUDE_STAGE3_BLACKHOLE", "blackhole"),
    "epilogue":   ("EPILOGUE",                   "window"),
}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", type=int, default=1, help="ステージID（既定1）")
    p.add_argument("--frames", type=int, default=60, help="最初の撮影までに進めるフレーム数（既定60）")
    p.add_argument("--shots", type=int, default=1, help="保存する枚数（既定1）")
    p.add_argument("--interval", type=int, default=12, help="連番撮影のフレーム間隔（既定12）")
    p.add_argument("--dt", type=float, default=1.0 / 60.0, help="1フレームの経過秒（既定 1/60）")

    p.add_argument("--boss", action="store_true", help="ボス戦へ即移行（演出をスキップして戦闘状態に）")
    p.add_argument("--form", type=int, choices=(1, 2, 3), default=1, help="ボスのフォーム（ステージ4のみ有効）")

    p.add_argument("--main", type=int, default=0, help="メインウェポンLv 0-5")
    p.add_argument("--laser", type=int, default=0, help="レーザーLv 0-6")
    p.add_argument("--homing", type=int, default=0, help="ホーミングLv 0-7")
    p.add_argument("--speed", type=int, default=0, help="スピードLv 0-5")
    p.add_argument("--magnet", type=int, default=0, help="マグネットLv 0-3")
    p.add_argument("--barrier", action="store_true", help="バリア付与")

    p.add_argument("--invincible", action=argparse.BooleanOptionalAction, default=True,
                   help="無敵＋HP維持で撮影中の死亡・点滅を防ぐ（既定 ON、--no-invincible で解除）")
    p.add_argument("--hold", default="fire",
                   help="毎フレーム押し続けるキー（カンマ区切り）: fire,laser,up,down,left,right")
    p.add_argument("--cutscene", choices=sorted(_CUTSCENES),
                   help="全画面カットシーン/モノローグを撮る（GameSceneの代わり）")
    p.add_argument("--page", type=int, default=0, help="--cutscene 時に表示するページ番号（既定0）")
    p.add_argument("--out", default="captures/shot", help="出力先プレフィックス（既定 captures/shot）")
    return p.parse_args(argv)


def _capture_cutscene(args: argparse.Namespace) -> int:
    """全画面カットシーン（CutsceneScene）を指定ページで撮影する。"""
    from src.scenes.cutscene_scene import CutsceneScene
    import src.story.script as script

    const, theme = _CUTSCENES[args.cutscene]
    pages = getattr(script, const)

    game = Game()
    scene = CutsceneScene(game, pages, on_complete=lambda: None, theme=theme)
    game._scene = scene
    scene.on_enter()
    scene._fade_in_t = 0.0  # 入場フェードを飛ばして本文を見えるようにする

    page_idx = max(0, min(args.page, len(scene._pages) - 1))
    scene._page = page_idx
    scene._enter_page()

    inp = game.input
    for _ in range(max(1, args.frames)):
        inp.pre_update()
        inp.update(args.dt)
        scene._chars = float(scene._total_chars())  # 全文を表示済みにする
        scene.update(args.dt)
        scene.draw(game.screen)

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out = out.with_suffix(".png")
    pygame.image.save(game.screen, str(out))
    print(out)
    pygame.quit()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.cutscene:
        return _capture_cutscene(args)

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

    # 最初の撮影まで warmup
    for _ in range(max(0, args.frames)):
        step_frame(scene, dt=args.dt, hold=hold, invincible=args.invincible)

    out_prefix = Path(args.out)
    if not out_prefix.is_absolute():
        out_prefix = ROOT / out_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    for i in range(max(1, args.shots)):
        if i > 0:
            for _ in range(max(1, args.interval)):
                step_frame(scene, dt=args.dt, hold=hold, invincible=args.invincible)
        if args.shots == 1:
            out = out_prefix.with_suffix(".png")
        else:
            out = out_prefix.with_name(f"{out_prefix.name}_{i:02d}.png")
        pygame.image.save(game.screen, str(out))
        saved.append(out)

    for path in saved:
        print(path)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
