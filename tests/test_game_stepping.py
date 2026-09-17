"""The normal loop and command stepping share scene, input and time behavior."""
from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from src.core.frame_clock import ticks_ms
from src.core.game import Game
from src.core.scene import Scene
from src.managers.input import InputManager


@pytest.fixture
def game(monkeypatch, tmp_path):
    import src.managers.settings as settings_module
    import src.managers.highscore as highscore_module

    monkeypatch.setattr(settings_module, "_SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(highscore_module, "_HIGHSCORE_PATH", tmp_path / "highscore.json")
    instance = Game()
    instance.input = InputManager(instance.settings, physical_input=False)
    pygame.event.clear()
    yield instance
    instance.close()


class ProbeScene(Scene):
    def __init__(self, game, log, name="probe"):
        super().__init__(game)
        self.log = log
        self.name = name
        self.next_scene = None
        self.updates = []
        self.draw_times = []

    def on_enter(self):
        self.log.append((self.name, "enter"))

    def on_exit(self):
        self.log.append((self.name, "exit"))

    def handle_event(self, event):
        self.log.append((self.name, "event", event.type))

    def update(self, dt):
        self.log.append((self.name, "update"))
        self.updates.append(dt)
        if self.next_scene is not None:
            self.game.change_scene(self.next_scene)
            self.next_scene = None

    def draw(self, screen):
        self.log.append((self.name, "draw"))
        self.draw_times.append(ticks_ms())
        screen.fill("white")


def test_start_is_lazy_idempotent_and_reaches_normal_title(game):
    game.start()
    initial = game._next_scene
    assert type(initial).__name__ == "DisclaimerScene"
    assert game._scene is None
    assert game.elapsed_time == 0
    game.start()
    assert game._next_scene is initial

    accept = pygame.event.Event(pygame.KEYDOWN, key=game.settings.get_key("ui_accept"))
    assert game.step(1 / 60, [accept], allow_debug=False)
    assert game._scene is initial
    for _ in range(45):
        game.step(1 / 60, [], allow_debug=False)
    assert type(game._scene).__name__ == "TitleScene"
    assert game._fade_timer > 0


def test_pending_transition_and_resume_preserve_lifecycle_order(game):
    log = []
    first = ProbeScene(game, log, "first")
    second = ProbeScene(game, log, "second")
    first.next_scene = second
    game.change_scene(first)
    game.step(0.1, [], allow_debug=False)
    assert game._scene is first
    assert game._next_scene is second
    assert log == [("first", "enter"), ("first", "update"), ("first", "draw")]

    log.clear()
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z)
    game.step(0.1, [event], allow_debug=False)
    assert log == [
        ("first", "exit"), ("second", "enter"),
        ("second", "event", pygame.KEYDOWN), ("second", "update"), ("second", "draw"),
    ]
    game.change_scene(first, reinit=False)
    log.clear()
    game.step(0.1, [], allow_debug=False)
    assert log == [("second", "exit"), ("first", "update"), ("first", "draw")]
    assert game._next_reinit is True
    assert game._fade_timer == 0
    assert first.updates == [0.1, 0.1]


def test_explicit_events_ignore_os_queue_and_keep_press_release_edges(game):
    scene = ProbeScene(game, [])
    game.change_scene(scene)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x))
    game.step(0.1, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z)], False)
    assert not game.input.is_pressed(pygame.K_x)
    assert game.input.is_just_pressed(pygame.K_z)
    game.step(0.1, [], False)
    assert game.input.is_pressed(pygame.K_z)
    assert not game.input.is_just_pressed(pygame.K_z)
    game.step(0.1, [pygame.event.Event(pygame.KEYUP, key=pygame.K_z)], False)
    assert not game.input.is_pressed(pygame.K_z)
    assert game.input.is_just_released(pygame.K_z)


def test_step_clock_ignores_wall_time_and_restores_external_preview_clock(game, monkeypatch):
    scene = ProbeScene(game, [])
    game.change_scene(scene)
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 999_999)
    game.step(0.25, [], False)
    assert ticks_ms() == 999_999
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 1_999_999)
    game.step(0.25, [], False)
    assert scene.draw_times == [250, 500]
    assert game.elapsed_time == 0.5
    assert ticks_ms() == 1_999_999


def test_quit_does_not_advance_and_close_saves_once_without_exiting(game, monkeypatch):
    scene = ProbeScene(game, [])
    game.change_scene(scene)
    game.step(0.1, [], False)
    saved = []
    monkeypatch.setattr(game.settings, "save", lambda: saved.append(True))
    assert not game.step(0.1, [pygame.event.Event(pygame.QUIT)], False)
    assert scene.updates == [0.1]
    assert game.elapsed_time == 0.1
    assert not game.step(0.1, [], False)
    assert saved == []
    game.close()
    game.close()
    assert saved == [True]
    assert not pygame.get_init()
    assert not game.step(0.1, [], False)


@pytest.mark.parametrize("dt", [-0.1, float("nan"), float("inf")])
def test_invalid_delta_does_not_enter_or_advance_scene(game, dt):
    with pytest.raises(ValueError, match="finite and non-negative"):
        game.step(dt, [])
    assert game.elapsed_time == 0
    assert game._scene is game._next_scene is None


def test_normal_run_reads_events_after_pre_update_and_uses_shared_step(game, monkeypatch):
    scene = ProbeScene(game, [])
    game.change_scene(scene)
    game.clock = SimpleNamespace(tick=lambda fps: 16)
    pre_update = game.input.pre_update
    calls = []

    def inject():
        pre_update()
        calls.append(True)
        if len(calls) == 2:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(game.input, "pre_update", inject)
    game.run()
    assert scene.updates == [0.016]
    assert scene.draw_times == [16]
    assert game._closed


def test_command_input_never_reads_physical_keys_including_repeat(monkeypatch):
    def forbidden():
        raise AssertionError("command input consulted the physical keyboard")

    monkeypatch.setattr(pygame.key, "get_pressed", forbidden)
    inp = InputManager(physical_input=False)
    assert not inp.is_pressed(pygame.K_z)
    assert not inp.is_held_with_repeat(pygame.K_z)
    inp.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
    inp.update(0.1)
    assert inp.is_held_with_repeat(pygame.K_z)
    inp.pre_update()
    assert not inp.is_held_with_repeat(pygame.K_z)
    inp.pre_update()
    assert inp.is_held_with_repeat(pygame.K_z)
    inp.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_z))
    assert not inp.is_held_with_repeat(pygame.K_z)


def test_default_input_still_accepts_physical_key_state(monkeypatch):
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: {pygame.K_z: True})
    assert InputManager().is_pressed(pygame.K_z)


def test_data_override_precedes_frozen_and_cached_default(monkeypatch, tmp_path):
    from src.core import user_data

    isolated = tmp_path / "isolated"
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(isolated))
    monkeypatch.setattr(user_data, "_cached_dir", tmp_path / "old-default")
    monkeypatch.setattr(user_data.sys, "frozen", True, raising=False)
    assert user_data.user_data_dir() == isolated
    assert isolated.is_dir()
    assert not (tmp_path / "old-default").exists()


@pytest.mark.parametrize("path", ["", "relative-profile"])
def test_relative_data_override_fails_instead_of_using_normal_profile(monkeypatch, path):
    from src.core import user_data

    monkeypatch.setenv("FLU_USER_DATA_DIR", path)
    with pytest.raises(ValueError, match="absolute path"):
        user_data.user_data_dir()


def test_profiles_resolve_on_construction_and_remain_bound_to_each_instance(monkeypatch, tmp_path):
    from src.core import user_data
    from src.managers import highscore, settings
    from src.managers.playlog import PlayLogger

    default = tmp_path / "default"
    monkeypatch.setattr(user_data, "_cached_dir", default)
    monkeypatch.setattr(settings, "_SETTINGS_PATH", None)
    monkeypatch.setattr(highscore, "_HIGHSCORE_PATH", None)
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(first))
    first_settings, first_scores, first_log = settings.SettingsManager(), highscore.HighScoreManager(), PlayLogger()
    first_settings.set("bgm_volume", 0.25)
    first_log.begin_run()
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(second))
    second_settings, second_scores = settings.SettingsManager(), highscore.HighScoreManager()
    second_settings.set("bgm_volume", 0.75)
    second_settings.save()
    second_scores.add("second", 20, 1)

    # Old managers must retain their destination after another session begins.
    first_settings.save()
    first_scores.add("first", 10, 1)
    first_log.end_run(cleared=False, score=10, kill_count=0)
    assert json.loads((first / "settings.json").read_text(encoding="utf-8"))["bgm_volume"] == 0.25
    assert json.loads((second / "settings.json").read_text(encoding="utf-8"))["bgm_volume"] == 0.75
    assert json.loads((first / "highscore.json").read_text(encoding="utf-8"))[0]["name"] == "first"
    assert json.loads((second / "highscore.json").read_text(encoding="utf-8"))[0]["name"] == "second"
    assert list((first / "playlogs").glob("*.jsonl"))
    assert not (second / "playlogs").exists()
    monkeypatch.delenv("FLU_USER_DATA_DIR")
    assert user_data.user_data_dir() == default


@pytest.mark.parametrize("key", [pygame.K_d, pygame.K_c, pygame.K_v])
def test_command_mode_disables_title_debug_jumps(game, key):
    from src.scenes.title import TitleScene

    title = TitleScene(game)
    game.change_scene(title)
    game.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=key)], False)
    assert game._scene is title
    assert game._next_scene is None


def test_command_mode_disables_global_and_battle_debug_paths(game, monkeypatch):
    from src.scenes.game_scene import GameScene

    calls = []
    scene = GameScene(game, stage_id=1)
    game.change_scene(scene)
    monkeypatch.setattr(scene, "_debug_apply_time_scale", lambda dt: calls.append("scale") or dt)
    monkeypatch.setattr(scene, "_debug_handle_input", lambda: calls.append("battle") or False)
    keys = [pygame.K_LCTRL, pygame.K_4, pygame.K_F1, pygame.K_F4, pygame.K_F7]
    game.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=k) for k in keys], False)
    assert calls == []
    assert game._next_scene is None
    assert not scene._debug_invincible
    assert scene.player.weapon.main_level == 0

    game.step(1 / 60, [pygame.event.Event(pygame.KEYUP, key=k) for k in keys], True)
    assert calls == ["scale", "battle"]


def test_terrain_texture_is_stable_across_process_hash_seeds():
    code = """
import hashlib, random
import pygame
from src.entities.terrain import Terrain
before = random.getstate()
digest = hashlib.sha256()
for kind in ('wall', 'rock', 'debris'):
    terrain = Terrain(120, 30, 80, 100, kind, destructible=True)
    assert terrain.rect == pygame.Rect(120, 30, 80, 100)
    digest.update(pygame.image.tobytes(terrain.image, 'RGBA'))
assert random.getstate() == before
print(digest.hexdigest())
"""
    outputs = []
    for hash_seed in ("1", "42"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYGAME_HIDE_SUPPORT_PROMPT="1")
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, check=True,
        )
        outputs.append(result.stdout.strip())
    assert outputs[0] == outputs[1]
    assert len(outputs[0]) == 64
