"""スモーク / ソークテスト：各ステージを実際にヘッドレスで走らせ、
「クラッシュ・非有限座標を出さずに動き続けるか」だけを検査する。

狙いは“正しさ”ではなく“生きてるか（liveness）”。ボスを作り変えても
バランスを変えても通る、仕様変更に最も強い種類のチェック。コードレビューや
スクリーンショットでは見抜けない「ボス出現で即クラッシュ」「形態遷移で例外」
といった、実際に走らせないと分からないバグ階級を自動で捕まえる
（＝離席中に PR をマージしても踏み抜きにくくする保険）。

assert するのは:
  - update/draw が例外を投げないこと
  - 自機・カメラの座標が有限（NaN/inf でない）こと
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

# headless の import で SDL ダミー設定と sys.path が済む。
from tools.headless import HOLD_KEYS, build_game_scene, skip_to_fight, step_frame  # noqa: E402
import pygame  # noqa: E402

from src.core.registries import stage_ids  # noqa: E402
from src.scenes.game_scene import GameScene  # noqa: E402

STAGES = stage_ids()
NORMAL_FRAMES = 180   # 3秒 @60fps（クラッシュは spawn/遷移直後に出やすい）
BOSS_FRAMES = 180
FIRE = (HOLD_KEYS["fire"],)


@pytest.fixture(scope="module")
def game():
    """Game は重い（pygame.init / リソース）ので module で1回だけ作り、各テストで
    GameScene を作り直して使い回す。"""
    g, _ = build_game_scene(STAGES[0])
    yield g
    pygame.quit()


def _fresh_scene(game, stage_id: int) -> GameScene:
    scene = GameScene(game, stage_id=stage_id)
    game._scene = scene
    scene.on_enter()
    return scene


def _assert_finite(scene: GameScene) -> None:
    p = scene.player
    assert math.isfinite(p.sx) and math.isfinite(p.sy), "player position is non-finite"
    assert math.isfinite(scene.camera.x), "camera.x is non-finite"


@pytest.mark.parametrize("stage_id", STAGES)
def test_stage_normal_play_runs_without_crash(game, stage_id):
    """通常進行（自機が撃ちながら前進）を数秒回しても例外・非有限が出ない。"""
    scene = _fresh_scene(game, stage_id)
    for _ in range(NORMAL_FRAMES):
        step_frame(scene, hold=FIRE, invincible=True)
        _assert_finite(scene)


@pytest.mark.parametrize("stage_id", STAGES)
def test_stage_boss_fight_runs_without_crash(game, stage_id):
    """各ステージのボス戦に入り、数秒戦闘を回しても例外・非有限が出ない。
    自機は撃たない（hold=()）のでボスは生存し、攻撃・ギミック描画の経路を踏む。"""
    scene = _fresh_scene(game, stage_id)
    assert skip_to_fight(scene, stage_id, hold=()), \
        f"stage {stage_id}: boss が fighting 状態に到達しなかった"
    for _ in range(BOSS_FRAMES):
        step_frame(scene, hold=(), invincible=True)
        _assert_finite(scene)


@pytest.mark.parametrize("form", [2, 3])
def test_stage4_boss_forms_run_without_crash(game, form):
    """ステージ4の第2/第3形態（投了王サワグチ）の update/draw 経路を保護する。
    最終決戦演出（FinalBattleDirector）やボスギミック描画の回帰を捕まえる。"""
    scene = _fresh_scene(game, 4)
    assert skip_to_fight(scene, 4, form=form, hold=()), \
        f"stage4 boss form {form}: fighting 状態に到達しなかった"
    for _ in range(BOSS_FRAMES):
        step_frame(scene, hold=(), invincible=True)
        _assert_finite(scene)
