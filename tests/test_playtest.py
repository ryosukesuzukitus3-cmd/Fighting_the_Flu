"""The optional GUI input bridge must drive real input consumers and release keys."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pygame
import pytest

from src.entities.player import Player
from src.managers.input import InputManager
from src.managers.settings import SettingsManager
from src.scenes.title import TitleScene
from tools.playtest import Controller


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    import src.managers.settings as settings_module

    monkeypatch.setattr(settings_module, "_SETTINGS_PATH", tmp_path / "settings.json")
    pygame.init()
    pygame.display.set_mode((32, 32))
    pygame.event.clear()
    inp = InputManager(SettingsManager())
    replies = []
    controller = Controller(emit=replies.append)
    posted = []

    def frame(now):
        inp.pre_update()
        controller.tick(now)
        events = pygame.event.get()
        posted.extend(events)
        for event in events:
            inp.handle_event(event)
        inp.update(0.1)
        return events

    yield controller, inp, replies, posted, frame
    pygame.quit()


def game_stub(inp):
    sprite = pygame.Surface((50, 60), pygame.SRCALPHA)
    sprite.fill("white")
    scenes = []
    game = SimpleNamespace(
        input=inp,
        settings=inp._settings,
        resources=SimpleNamespace(
            image=lambda name: sprite,
            pixelfont=lambda size: pygame.font.Font(None, size),
        ),
        sound=SimpleNamespace(
            play_se=lambda *args, **kwargs: None,
            play_bgm_if_new=lambda *args, **kwargs: None,
        ),
        change_scene=scenes.append,
    )
    return game, scenes


@pytest.mark.parametrize("key", ["enter", "space"])
def test_confirm_key_starts_game_through_real_title_input(bridge, key):
    controller, inp, _, _, frame = bridge
    game, scenes = game_stub(inp)
    title = TitleScene(game)
    title.on_enter()
    controller.submit(json.dumps({"press": [key], "seconds": 0.15}))
    frame(0.0)
    title.update(0.1)
    assert [type(scene).__name__ for scene in scenes] == ["PrologueScene"]
    frame(0.2)
    assert not inp.is_pressed(pygame.K_RETURN)
    assert not inp.is_pressed(pygame.K_SPACE)


@pytest.mark.parametrize("key", ["f", "d", "c", "v"])
def test_custom_title_confirm_uses_only_configured_key(bridge, key):
    controller, inp, _, _, frame = bridge
    game, scenes = game_stub(inp)
    assert game.settings.set_key_binding("ui_accept", pygame.key.key_code(key))
    title = TitleScene(game)
    title.on_enter()
    controller.submit('{"press":["enter","space"],"seconds":0.15}')
    frame(0.0)
    title.update(0.1)
    assert scenes == []
    frame(0.2)

    controller.submit(json.dumps({"press": [key], "seconds": 0.15}))
    frame(0.3)
    title.update(0.1)
    assert [type(scene).__name__ for scene in scenes] == ["PrologueScene"]


def test_movement_and_shooting_hold_and_release_independently(bridge):
    controller, inp, _, _, frame = bridge
    game, _ = game_stub(inp)
    player = Player(game)
    player._entering = False
    player.sx, player.sy = 120.0, 200.0
    controller.submit('{"press":["right","z","space"],"seconds":1.0}')
    frame(0.0)
    player.update(0.1)
    assert player.sx > 120.0
    assert player.shoot_requested and player.fire_held and player.laser_fire_held

    controller.submit('{"release":["right"]}')
    frame(0.2)
    previous_x = player.sx
    player.update(0.1)
    assert player.sx == previous_x
    assert player.fire_held and player.laser_fire_held

    frame(1.1)
    player.update(0.1)
    assert not player.fire_held and not player.laser_fire_held
    assert not player.shoot_requested
    assert controller.held_keys() == []


def test_repeated_press_extends_hold_without_retriggering_keydown(bridge):
    controller, inp, _, posted, frame = bridge
    controller.submit('{"press":["z"],"seconds":1.0}')
    frame(0.0)
    controller.submit('{"press":["z"],"seconds":2.0}')
    frame(0.5)
    frame(1.1)
    assert inp.is_pressed(pygame.K_z)
    assert sum(event.type == pygame.KEYDOWN for event in posted) == 1
    frame(2.6)
    assert not inp.is_pressed(pygame.K_z)


def test_queued_press_and_release_are_observable_in_separate_frames(bridge):
    controller, inp, _, _, frame = bridge
    controller.submit('{"press":["return"],"seconds":1.0}')
    controller.submit('{"release":["return"]}')
    frame(0.0)
    assert inp.is_just_pressed(pygame.K_RETURN)
    assert inp.is_pressed(pygame.K_RETURN)
    frame(0.1)
    assert inp.is_just_released(pygame.K_RETURN)
    assert not inp.is_pressed(pygame.K_RETURN)


@pytest.mark.parametrize("ending", [None, '{"quit":true}'])
def test_disconnect_or_quit_releases_keys_before_normal_exit(bridge, ending):
    controller, inp, _, _, frame = bridge
    controller.submit('{"press":["z","right"],"seconds":5.0}')
    frame(0.0)
    controller.submit(ending)
    events = frame(0.1)
    assert not inp.is_pressed(pygame.K_z)
    assert not inp.is_pressed(pygame.K_RIGHT)
    assert events[-1].type == pygame.QUIT
    assert {event.key for event in events if event.type == pygame.KEYUP} == {
        pygame.K_z, pygame.K_RIGHT,
    }


@pytest.mark.parametrize("seconds", [0, -1, 5.1, True, "1", float("nan"), float("inf")])
def test_invalid_duration_does_not_press_any_key(bridge, seconds):
    controller, inp, replies, _, frame = bridge
    controller.submit(json.dumps({"press": ["z"], "seconds": seconds}))
    events = frame(0.0)
    assert not inp.is_pressed(pygame.K_z)
    assert not any(event.type == pygame.KEYDOWN for event in events)
    assert replies


@pytest.mark.parametrize("line", [
    'not json',
    '[]',
    '{"press":["z","nonexistent-key"],"seconds":1}',
    '{"capture":"../../outside"}',
])
def test_bad_command_is_atomic_and_next_command_still_works(bridge, line):
    controller, inp, replies, _, frame = bridge
    controller.submit(line)
    events = frame(0.0)
    assert not any(event.type == pygame.KEYDOWN for event in events)
    assert replies
    controller.submit('{"press":["z"],"seconds":1}')
    frame(0.1)
    assert inp.is_pressed(pygame.K_z)
