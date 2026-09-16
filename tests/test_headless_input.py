"""Configured controls must reach real Player/InputManager consumers in tools."""
from types import SimpleNamespace

import pygame
import pytest

from src.entities.player import Player
from src.managers import settings as settings_module
from src.managers.input import InputManager
from tools.headless import hold_keys_from_names, step_frame


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "_SETTINGS_PATH", tmp_path / "settings.json")
    pygame.init()
    pygame.display.set_mode((32, 32))
    settings = settings_module.SettingsManager()
    image = pygame.Surface((50, 60), pygame.SRCALPHA)
    image.fill("white")
    game = SimpleNamespace(settings=settings, input=InputManager(settings),
                           screen=pygame.Surface((800, 600)),
                           resources=SimpleNamespace(image=lambda _: image))
    player = Player(game)
    player._entering = False
    player.sx, player.sy = 120.0, 200.0
    yield SimpleNamespace(game=game, player=player, update=player.update,
                          draw=lambda screen: None, _boss_intro_state="")
    pygame.quit()


def test_player_laser_follows_binding_and_ignores_old_default(scene):
    assert scene.game.settings.set_key_binding("laser", pygame.K_l)
    inp = scene.game.input
    inp.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scene.player.update(0.1)
    assert not scene.player.laser_fire_held
    inp.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
    inp.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l))
    scene.player.update(0.1)
    assert scene.player.laser_fire_held
    inp.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_l))
    scene.player.update(0.1)
    assert not scene.player.laser_fire_held


def test_headless_hold_resolves_actions_and_releases_previous_keys(scene):
    settings = scene.game.settings
    assert settings.set_key_binding("fire", pygame.K_f)
    assert settings.set_key_binding("laser", pygame.K_l)
    assert settings.set_key_binding("move_right", pygame.K_d)
    held = hold_keys_from_names("fire,laser,right", settings)
    assert held == [pygame.K_f, pygame.K_l, pygame.K_d]
    step_frame(scene, dt=0.1, hold=held, invincible=False)
    assert scene.player.sx > 120
    assert scene.player.fire_held and scene.player.laser_fire_held
    previous_x = scene.player.sx
    step_frame(scene, dt=0.1, hold=(), invincible=False)
    assert scene.player.sx == previous_x
    assert not scene.player.fire_held and not scene.player.laser_fire_held
    assert not scene.game.input._pressed


def test_headless_dialogue_advance_uses_configured_accept_and_releases_it(scene):
    assert scene.game.settings.set_key_binding("ui_accept", pygame.K_q)
    scene._boss_intro_state = "boss_dialogue"
    received = []
    scene.update = lambda dt: received.append(scene.game.input.is_action_just_pressed("ui_accept"))
    step_frame(scene)
    step_frame(scene)
    assert received == [True, True]
    assert pygame.K_RETURN not in scene.game.input._pressed
    step_frame(scene, advance_dialogue=False)
    assert received[-1] is False
    assert pygame.K_q not in scene.game.input._pressed
