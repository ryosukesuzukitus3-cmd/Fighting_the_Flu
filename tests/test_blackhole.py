"""Blackhole rescue timing, readable farewell, and real-input scene liveness."""
from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from src.managers.input import InputManager
from src.managers.resource import ResourceManager
from src.managers.settings import SettingsManager
from src.scenes.blackhole_scene import BlackholeScene, _CENTER
from src.story.lines import page
from src.story.script import story_beat
from src.story.speakers import KARONARU, SAWAGUCHI


@pytest.fixture
def game(monkeypatch, tmp_path):
    import src.managers.settings as settings_module
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(settings_module, "_SETTINGS_PATH", tmp_path / "settings.json")
    pygame.init()
    settings = SettingsManager()
    yield SimpleNamespace(
        screen=pygame.display.set_mode((800, 600)), resources=ResourceManager(),
        settings=settings, input=InputManager(settings, physical_input=False), sound=Mock(),
    )
    pygame.quit()


def _frame(scene, events=(), dt=1 / 60):
    inp = scene.game.input
    inp.pre_update()
    for event in events:
        inp.handle_event(event)
    inp.update(dt)
    scene.update(dt)


def _key(game, action, kind):
    return pygame.event.Event(kind, key=game.settings.get_key(action))


def _scene(game, pages=None):
    done = Mock()
    scene = BlackholeScene(game, list(story_beat("3->4").pages) if pages is None else pages, done)
    scene.on_enter()
    return scene, done


def _seek_cue(scene, cue):
    scene._page = next(i for i, pg in enumerate(scene._pages) if cue in pg.fx)
    scene._enter_page()


@pytest.mark.parametrize("method", ["normal", "held", "rapid"])
def test_blackhole_runs_through_all_pages_using_configured_input(game, method):
    game.settings.set_key_binding("ui_accept", pygame.K_q)
    scene, done = _scene(game)
    phases = set()
    pages = set()
    pressed = False
    previous_positions = (scene._player_pos, scene._karonaru_pos)
    for frame in range(15000):
        if method == "held":
            should_press = True
        elif method == "rapid":
            should_press = frame % 2 == 0
        else:
            # Read the complete line, then tap once. No private page mutation.
            should_press = scene._is_text_complete() and frame % 20 == 0
        events = []
        if should_press != pressed:
            events.append(_key(game, "ui_accept", pygame.KEYDOWN if should_press else pygame.KEYUP))
            pressed = should_press
        _frame(scene, events)
        for old, new in zip(previous_positions, (scene._player_pos, scene._karonaru_pos)):
            assert math.dist(old, new) < 12, "rapid advance must not teleport either actor"
        previous_positions = (scene._player_pos, scene._karonaru_pos)
        if scene._page not in pages:
            scene.draw(game.screen)
        phases.add(scene._phase)
        pages.add(scene._page)
        if done.called:
            break
    assert len(pages) == len(scene._pages)
    assert {"charge", "push", "fall", "farewell", "gone", "silence"} <= phases
    done.assert_called_once_with()
    for _ in range(120):
        _frame(scene)
    done.assert_called_once_with()


def test_reading_time_cannot_consume_the_last_words(game):
    scene, _ = _scene(game)
    for cue in ("bh_fall", "bh_hold", "bh_farewell"):
        _seek_cue(scene, cue)
        _frame(scene, dt=120.0)
        scene.draw(game.screen)
        assert scene._karonaru_alpha >= 190
        assert scene._karonaru_scale >= 0.58
        assert math.dist(scene._karonaru_pos, _CENTER) > 80
        assert not scene._quiet
    _seek_cue(scene, "bh_gone")
    _frame(scene, dt=1.1)
    assert scene._karonaru_alpha == 0
    assert scene._karonaru_pos == _CENTER


def test_farewell_cues_survive_inserted_dialogue_pages(game):
    original = list(story_beat("3->4").pages)
    expanded = []
    expected = []
    phase = "balance"
    for pg in original:
        if "bh_fall" in pg.fx:
            phase = "fall"
        elif "bh_hold" in pg.fx:
            phase = "hold"
        elif "bh_farewell" in pg.fx:
            phase = "farewell"
        elif "bh_gone" in pg.fx:
            phase = "gone"
        elif "bh_silence" in pg.fx:
            phase = "silence"
        expanded.extend([pg] + [page(SAWAGUCHI, "追加の台詞。")] * 5)
        expected.extend([phase] * 6)
    scene = BlackholeScene(game, expanded, Mock())
    start = next(i for i, pg in enumerate(expanded) if "bh_fall" in pg.fx)
    for i in range(start, len(expanded)):
        scene._page = i
        assert scene._phase_for_page() == expected[i]


def test_rescue_push_moves_the_two_actors_apart_before_falling(game):
    scene, _ = _scene(game)
    _seek_cue(scene, "bh_resolve")
    _frame(scene, dt=1.0)
    before = (scene._player_pos, scene._karonaru_pos)
    assert before[1][0] > before[0][0]
    _seek_cue(scene, "bh_push")
    _frame(scene, dt=0.9)
    assert scene._player_pos[0] < before[0][0] - 100
    assert scene._karonaru_pos[0] > before[1][0]
    assert scene._karonaru_alpha == 255


def test_loss_stops_music_typing_shake_and_background_motion(game):
    scene, _ = _scene(game)
    _seek_cue(scene, "bh_farewell")
    _frame(scene, dt=2.0)
    game.sound.reset_mock()
    _seek_cue(scene, "bh_gone")
    for _ in range(90):
        _frame(scene)
    _seek_cue(scene, "bh_silence")
    _frame(scene, dt=2.0)
    scene.draw(game.screen)
    quiet_sky = pygame.image.tobytes(game.screen.subsurface((0, 0, 800, 342)), "RGB")
    _frame(scene, dt=3.0)
    scene.draw(game.screen)
    assert pygame.image.tobytes(game.screen.subsurface((0, 0, 800, 342)), "RGB") == quiet_sky
    game.sound.stop_bgm.assert_called_once_with(fadeout_ms=850)
    game.sound.play_se_alias.assert_not_called()
    assert scene._shake_offset() == (0, 0)
    assert scene._karonaru_alpha == 0


@pytest.mark.parametrize("cue", ["bh_balance", "bh_push", "bh_gone"])
def test_skip_completes_once_even_during_required_motion(game, cue):
    game.settings.set_key_binding("ui_back", pygame.K_w)
    scene, done = _scene(game)
    _seek_cue(scene, cue)
    _frame(scene, [_key(game, "ui_back", pygame.KEYDOWN)])
    assert scene._fade_out
    for _ in range(240):
        _frame(scene)
    done.assert_called_once_with()


@pytest.mark.parametrize("pages", [[], [page(KARONARU, "")]])
def test_empty_content_does_not_crash_or_leave_scene_stuck(game, pages):
    scene, done = _scene(game, pages)
    _frame(scene, [_key(game, "ui_accept", pygame.KEYDOWN)])
    for _ in range(180):
        _frame(scene)
        scene.draw(game.screen)
    done.assert_called_once_with()


def test_full_pressure_launches_hero_outside_frame_and_does_not_replay(game):
    scene, _ = _scene(game)
    _seek_cue(scene, "bh_resolve")
    _frame(scene, dt=1.0)
    _seek_cue(scene, "bh_charge")
    _frame(scene, dt=1.3)
    scene.draw(game.screen)
    assert scene._rescue_fx.get_bounding_rect().width > 0
    _seek_cue(scene, "bh_push")
    _frame(scene, dt=.25)
    scene.draw(game.screen)
    assert scene._rescue_fx.get_bounding_rect().width > 150
    _frame(scene, dt=1.1)
    assert scene._player_pos[0] + scene._player.image.get_width() / 2 < 0
    assert scene._karonaru_pos[0] > 400
    # Reading the next ordinary line must not reset the blast clock.
    age = scene._rescue_age
    scene._page += 1
    scene._enter_page()
    assert scene._rescue_age == age
    _frame(scene, dt=2)
    scene.draw(game.screen)
    assert scene._rescue_fx.get_bounding_rect().width == 0
    for cue in ("bh_fall", "bh_hold", "bh_farewell"):
        _seek_cue(scene, cue)
        _frame(scene, dt=3)
        assert scene._player_pos[0] < 0
