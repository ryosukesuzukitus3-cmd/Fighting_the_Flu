"""承認欲求ブラックホール（Stage3→4）の liveness テスト。

全ページを送っても例外を出さず、崩落（fall）フェーズを通って on_complete
まで到達すること、シェイクのバッファ描画が破綻しないことを守る。演出の
「正しさ」ではなく「最後まで生きて進むか」を検査する。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from tools.headless import build_game_scene  # noqa: E402  (SDL ダミー設定込み)
import pygame  # noqa: E402

from src.scenes.blackhole_scene import BlackholeScene  # noqa: E402
from src.story.script import story_beat  # noqa: E402


@pytest.fixture(scope="module")
def game():
    g, _ = build_game_scene(1)
    yield g
    pygame.quit()


def test_blackhole_runs_through_all_pages(game):
    pages = list(story_beat("3->4").pages)
    done = {"v": False}
    scene = BlackholeScene(game, pages, on_complete=lambda: done.__setitem__("v", True))
    game._scene = scene
    scene.on_enter()

    total = len(pages)
    phases: set[str] = set()
    frame = 0
    for _ in range(total * 30 + 400):
        frame += 1
        if frame % 24 == 0 and scene._page < total - 1:
            scene._page += 1
            scene._enter_page()
        scene.update(1 / 60.0)
        scene.draw(game.screen)
        phases.add(scene._phase)
        if scene._page == total - 1 and scene._is_text_complete():
            scene._begin_finish()
        if done["v"]:
            break

    assert done["v"], "blackhole scene did not reach on_complete"
    assert "fall" in phases, "崩落（fall）フェーズを通っていない"
