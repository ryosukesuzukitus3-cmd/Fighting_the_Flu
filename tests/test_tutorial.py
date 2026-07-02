"""対話型チュートリアル（準備運動）の liveness テスト。

FakeInput でフレームを送り、offer→move→shoot→dummy→fight→result→outro を
通って on_complete に到達すること（例外なし）を検査する。中身の演出ではなく
「最後まで進むか」を守る（[[project_dev_constraints_and_verification]] の方針）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from tools.headless import build_game_scene  # noqa: E402  (SDL ダミー設定込み)
import pygame  # noqa: E402

from src.scenes.tutorial_scene import TutorialScene  # noqa: E402


class _FakeInput:
    """常に「ENTER・射撃・左上移動」を押し続ける疑似入力。

    - ENTER/Z: 台詞送り・選択決定（毎フレーム just_pressed 扱い）
    - 射撃: 撃つステップ・実戦で発射
    - 左上移動: 移動ステップのゲート（水平＋垂直）を満たす
    """

    def __init__(self) -> None:
        self.fire = False
        self.move: set[str] = set()
        self.enter = False

    def is_just_pressed(self, key: int) -> bool:
        return self.enter if key in (pygame.K_RETURN, pygame.K_z) else False

    def is_action_pressed(self, action: str) -> bool:
        if action == "fire":
            return self.fire
        return action in self.move

    def is_pressed(self, key: int) -> bool:
        return False


@pytest.fixture(scope="module")
def game():
    g, _ = build_game_scene(1)
    yield g
    pygame.quit()


def _drive(game, with_offer: bool):
    game.input = _FakeInput()
    done = {"v": False}
    scene = TutorialScene(game, on_complete=lambda: done.__setitem__("v", True),
                          with_offer=with_offer)
    game._scene = scene
    scene.on_enter()
    inp = game.input
    phases: set[str] = set()
    for _ in range(6000):   # 上限100秒相当（通常は十数秒で完了）
        inp.enter = True
        inp.fire = True
        inp.move = {"move_left", "move_up"}
        scene.update(1 / 60.0)
        scene.draw(game.screen)
        phases.add(scene._phase)
        if done["v"]:
            break
    return done["v"], phases


def test_tutorial_campaign_offer_completes(game):
    done, phases = _drive(game, with_offer=True)
    assert done, "campaign tutorial did not reach on_complete"
    assert {"move", "shoot", "dummy", "fight", "result", "outro"} <= phases


def test_tutorial_replay_completes(game):
    done, phases = _drive(game, with_offer=False)
    assert done, "replay tutorial did not reach on_complete"
