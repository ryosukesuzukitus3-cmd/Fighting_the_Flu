"""ヘッドレスで GameScene を駆動する共有ハーネス。

実際の `Game` / `GameScene` を SDL ダミードライバ上で構築し、
1フレームずつ手動で進める（入力保持つき）。capture（PNG撮影）・
gameplay_clip（GIF）・スモークテストが、この「シーンの作り方・進め方」を
唯一のソースとして共有する（SSOT。複数箇所に駆動ロジックを散らさない）。

pygame import より前に SDL/UTF-8 を設定する必要があるため、本モジュールを
最初に import すればヘッドレス設定が済む。
"""
from __future__ import annotations

import os

# pygame import より前にヘッドレス設定を済ませる
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYTHONUTF8", "1")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src.core.game import Game  # noqa: E402
from src.scenes.game_scene import GameScene  # noqa: E402

# 保持キー名 → pygame キー定数
HOLD_KEYS = {
    "fire":  pygame.K_z,
    "laser": pygame.K_SPACE,
    "up":    pygame.K_UP,
    "down":  pygame.K_DOWN,
    "left":  pygame.K_LEFT,
    "right": pygame.K_RIGHT,
}

DEFAULT_DT = 1.0 / 60.0
MAX_INTRO_FRAMES = 3000   # ボス演出スキップの安全上限


def hold_keys_from_names(names: str) -> list[int]:
    """カンマ区切りのキー名（"fire,up"）を pygame キー定数のリストへ。"""
    keys: list[int] = []
    for name in (n.strip() for n in names.split(",") if n.strip()):
        if name not in HOLD_KEYS:
            raise SystemExit(f"unknown hold key: {name!r} (choices: {', '.join(HOLD_KEYS)})")
        keys.append(HOLD_KEYS[name])
    return keys


def build_game_scene(stage_id: int) -> tuple[Game, GameScene]:
    """ヘッドレスな Game と、on_enter 済みの GameScene を構築する。"""
    game = Game()
    scene = GameScene(game, stage_id=stage_id)
    game._scene = scene
    scene.on_enter()
    return game, scene


def apply_weapon(
    scene: GameScene,
    *,
    main: int = 0,
    laser: int = 0,
    homing: int = 0,
    speed: int = 0,
    magnet: int = 0,
    barrier: bool = False,
) -> None:
    """自機のウェポンレベルを各上限でクランプして設定する（撮影/動画用）。"""
    w = scene.player.weapon
    w.main_level   = max(0, min(main, len(w._MAIN_LEVELS) - 1))
    w.laser_level  = max(0, min(laser, 6))
    w.homing_level = max(0, min(homing, 7))
    w.speed_level  = max(0, min(speed, 5))
    w.magnet_level = max(0, min(magnet, 3))
    w.has_barrier  = barrier


def step_frame(
    scene: GameScene,
    *,
    dt: float = DEFAULT_DT,
    hold: list[int] | tuple[int, ...] = (),
    invincible: bool = True,
    advance_dialogue: bool = True,
) -> None:
    """Game.run() の1フレーム分（入力→update→draw）を最小構成で再現する。"""
    inp = scene.game.input
    inp.pre_update()
    for key in hold:
        inp._pressed.add(key)
    # ボス会話は RETURN 待ちなので毎フレーム送って読み飛ばす。
    # is_held_with_repeat は _pressed も参照するため両方に入れる。
    if advance_dialogue and getattr(scene, "_boss_intro_state", "") == "boss_dialogue":
        inp._pressed.add(pygame.K_RETURN)
        inp._just_pressed.add(pygame.K_RETURN)
    inp.update(dt)

    if invincible:
        scene.player.hp = scene.player.max_hp
        scene.player._invincible_timer = 0.0
        scene.player._blink_visible = True

    scene.update(dt)
    scene.draw(scene.game.screen)


def skip_to_fight(
    scene: GameScene,
    stage_id: int,
    *,
    form: int = 1,
    dt: float = DEFAULT_DT,
    hold: list[int] | tuple[int, ...] = (),
    invincible: bool = True,
    max_frames: int = MAX_INTRO_FRAMES,
) -> bool:
    """ボス演出（alert→入場→セリフ→バナー）を進めて fighting 状態まで早送りする。

    fighting に到達できたら True。form>=2/3 を指定すると（ステージ4のみ意味を持つ）
    フォーム変形まで適用する。
    """
    scene._queue_boss_spawn(stage_id)
    reached = False
    for _ in range(max_frames):
        if scene._boss_intro_state == "fighting":
            reached = True
            break
        step_frame(scene, dt=dt, hold=hold, invincible=invincible)

    boss = scene._boss
    if boss is not None and form >= 2 and hasattr(boss, "_transform_form2"):
        boss._transform_form2()
    if boss is not None and form >= 3 and hasattr(boss, "_transform_form3"):
        boss._transform_form3()
    return reached
