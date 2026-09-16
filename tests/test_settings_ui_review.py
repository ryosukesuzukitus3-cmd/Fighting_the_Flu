"""Settings remain reachable and safe with customized menu keys."""
import json
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import pytest
from src.core.game import Game
from src.managers import settings as settings_module
from src.scenes.settings_scene import SettingsScene
from src.scenes.title import TitleScene


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, '_SETTINGS_PATH', tmp_path / 'settings.json')
    game = Game()
    scene = SettingsScene(game, TitleScene(game))
    scene.on_enter()
    yield game, scene
    pygame.quit()


def press(game, scene, key):
    game.input.pre_update()
    event = pygame.event.Event(pygame.KEYDOWN, key=key)
    game.input.handle_event(event)
    scene.handle_event(event)
    game.input.update(0.016)
    scene.update(0.016)
    game.input.handle_event(pygame.event.Event(pygame.KEYUP, key=key))


def test_every_setting_is_reachable_without_scrolling(setup):
    game, scene = setup
    reached = []
    for _ in range(3):
        group = scene._groups[scene._category]
        for _ in group:
            assert not scene._category_focus
            reached.append(scene._items[scene._cursor][1])
            press(game, scene, pygame.K_DOWN)
        assert scene._category_focus
        press(game, scene, pygame.K_RIGHT)
        press(game, scene, pygame.K_RETURN)
    assert reached == [key for _, key, _ in scene._items]


def test_tab_as_confirm_keeps_all_categories_accessible(setup):
    game, scene = setup
    assert game.settings.set_key_binding('ui_accept', pygame.K_TAB)
    press(game, scene, pygame.K_UP)
    press(game, scene, pygame.K_RIGHT)
    assert scene._category == 1 and scene._category_focus
    press(game, scene, pygame.K_TAB)
    assert scene._category == 1 and not scene._category_focus
    press(game, scene, pygame.K_TAB)
    assert scene._rebinding == 'move_up'


def test_tab_as_back_leaves_settings_instead_of_switching_category(setup):
    game, scene = setup
    assert game.settings.set_key_binding('ui_back', pygame.K_TAB)
    press(game, scene, pygame.K_TAB)
    assert game._next_scene is scene._back_scene
    assert scene._category == 0


def test_reset_requires_deliberate_confirmation_and_keeps_audio(setup):
    game, scene = setup
    game.settings.set_key_binding('fire', pygame.K_f)
    game.settings.set('bgm_volume', 0.35)
    press(game, scene, pygame.K_TAB)
    press(game, scene, pygame.K_TAB)
    for _ in range(3):
        press(game, scene, pygame.K_DOWN)
    press(game, scene, pygame.K_RETURN)
    assert scene._confirm_reset and scene._reset_cursor == 1
    assert game.settings.get_key('fire') == pygame.K_f
    press(game, scene, pygame.K_RETURN)
    assert not scene._confirm_reset
    assert game.settings.get_key('fire') == pygame.K_f
    press(game, scene, pygame.K_RETURN)
    press(game, scene, pygame.K_LEFT)
    press(game, scene, pygame.K_RETURN)
    assert game.settings.get_key('fire') == pygame.K_z
    assert game.settings.get('bgm_volume') == 0.35


def test_rebinding_to_back_key_does_not_leave_settings(setup):
    game, scene = setup
    scene._rebinding = 'fire'
    press(game, scene, pygame.K_x)
    assert scene._rebinding is None
    assert game.settings.get_key('fire') == pygame.K_x
    assert game._next_scene is None


def test_escape_cannot_become_confirm_and_legacy_conflict_is_repaired(setup):
    game, _ = setup
    assert not game.settings.set_key_binding('ui_accept', pygame.K_ESCAPE)
    settings_module._SETTINGS_PATH.write_text(json.dumps({'key_bindings': {'ui_accept': 'K_ESCAPE'}}), encoding='utf-8')
    restored = settings_module.SettingsManager()
    assert restored.get_key('ui_accept') == pygame.K_RETURN
