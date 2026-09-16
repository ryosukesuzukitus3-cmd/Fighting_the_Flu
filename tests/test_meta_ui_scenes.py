from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.core.game import Game
from src.managers.settings import KEY_BINDING_DISPLAY_NAMES
from src.scenes.gameover import GameOverScene
from src.scenes.settings_scene import SettingsScene
from src.scenes.stageclear import StageClearScene
from src.scenes.title import TitleScene


def test_settings_scene_lists_and_rebinds_every_public_action() -> None:
    game = Game()
    scene = SettingsScene(game, TitleScene(game))
    scene.on_enter()

    actions = [key for kind, key, _ in scene._items if kind == "key"]
    assert actions == list(KEY_BINDING_DISPLAY_NAMES)

    scene._rebinding = "fire"
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    assert game.settings.key_display("fire") == "F"
    assert scene._rebinding is None

    scene.draw(game.screen)
    assert game.screen.get_at((400, 20)) != game.screen.get_at((400, 560))
    pygame.quit()


def test_stage_clear_result_uses_carried_run_state() -> None:
    game = Game()
    game.shared.score = 12345
    game.shared.kill_count = 67
    game.shared.carry_hp = 42
    game.shared.carry_weapon = {"main_level": 3}
    game.shared.lives = 2

    scene = StageClearScene(game, 2, 3)
    scene.on_enter()
    assert scene._score == 12345
    assert scene._kills == 67
    assert scene._remaining_hp == 42
    assert scene._weapon["main_level"] == 3
    scene.draw(game.screen)
    pygame.quit()


def test_game_over_uses_one_cursor_menu_for_all_choices() -> None:
    game = Game()
    game.shared.score = 0
    game.shared.lives = 2
    scene = GameOverScene(game)
    scene.on_enter()
    assert scene._options == ["continue", "retry", "title"]
    assert scene._cursor == 0
    scene.draw(game.screen)
    pygame.quit()
