"""Post-boss walking accepts the same upgrade action as normal combat."""
from __future__ import annotations

import pygame
import pytest

from src.core.game import Game
from src.entities.enemies.boss import Boss
from src.entities.items.weapon_item import WeaponItem
from src.managers.input import InputManager
from src.scenes.game_scene import GameScene
from src.scenes.stageclear import StageClearScene

DT = 1 / 60


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    instance = Game()
    instance.start_new_run()
    instance.input = InputManager(instance.settings, physical_input=False)
    # The first pickup opens automatically and would hide a broken manual key.
    instance.shared.upgrade_tutorial_shown = True
    yield instance
    instance.close()


def key_event(game, kind, action):
    return pygame.event.Event(kind, key=game.settings.get_key(action))


def tap(game, action):
    game.step(DT, [key_event(game, pygame.KEYDOWN, action)], allow_debug=False)
    game.step(DT, [key_event(game, pygame.KEYUP, action)], allow_debug=False)


def make_scene(game, stage=1):
    scene = GameScene(game, stage_id=stage)
    game.change_scene(scene)
    game.step(DT, [], allow_debug=False)
    scene.spawner.skip_all_events()
    for group in (scene.enemies, scene.enemy_bullets, scene.items, scene.terrain):
        group.empty()
    scene.camera.scroll_speed = scene._stage_scroll_speed = 0
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene.player._entering = False
    scene.player.sx, scene.player.sy = 120.0, 285.0
    scene.player.rect.topleft = (120, 285)
    return scene


def defeat_boss(scene):
    """Prepare a defeat, then let the real post-boss state machine own it."""
    scene._boss = Boss(scene.game, scene._stage_id)
    scene._boss_intro_state = "fighting"
    scene._on_boss_killed()
    # These cases isolate stock already earned before the boss from its drops.
    scene.items.empty()


def finish_defeat_dialogue(game, scene):
    for _ in range(240):
        if scene._defeat_dialogue_delay <= 0:
            break
        game.step(DT, [], allow_debug=False)
    assert scene._defeat_dialogue_delay <= 0
    for _ in scene._defeat_dialogue_pages:
        if not scene._defeat_dialogue_active:
            break
        tap(game, "ui_accept")
    assert not scene._defeat_dialogue_active


def test_post_boss_upgrade_freezes_walk_then_carries_both_choices(game):
    scene = make_scene(game)
    scene.items.add(WeaponItem(scene.camera.to_world_x(scene.player.rect.centerx),
                               scene.player.rect.centery))
    game.step(DT, [], allow_debug=False)
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 1

    # Control: the same physical action works before the boss is defeated.
    tap(game, "weapon_select")
    assert scene._upgrading
    tap(game, "ui_back")
    assert not scene._upgrading

    defeat_boss(scene)
    finish_defeat_dialogue(game, scene)
    timer = scene._post_boss_timer
    position = scene.player.rect.topleft
    tap(game, "weapon_select")
    assert scene._upgrading, "The clear-area upgrade key must remain usable."
    assert scene._post_boss_timer == timer

    # Movement and the automatic departure timer must stop while choosing.
    game.step(DT, [key_event(game, pygame.KEYDOWN, "move_right")], allow_debug=False)
    for _ in range(6):
        game.step(DT, [], allow_debug=False)
    game.step(DT, [key_event(game, pygame.KEYUP, "move_right")], allow_debug=False)
    assert scene.player.rect.topleft == position
    assert scene._post_boss_timer == timer
    assert game._next_scene is None
    # Right also navigates this menu; restore the first choice with normal input.
    tap(game, "move_left")

    # Default choices are main weapon and companion durability, then confirm.
    for _ in range(3):
        tap(game, "ui_accept")
    assert not scene._upgrading
    assert scene.player.weapon.main_level == 1
    assert scene._companion.lv_hp == 1
    assert scene.player.weapon.weapon_stock == scene._companion.stock == 0

    game.step(DT, [key_event(game, pygame.KEYDOWN, "move_right")], allow_debug=False)
    for _ in range(180):
        if game._next_scene is not None:
            break
        game.step(DT, [], allow_debug=False)
    assert isinstance(game._next_scene, StageClearScene)
    assert game.shared.carry_weapon == scene.player.weapon.snapshot()
    assert game.shared.carry_companion == scene._companion.snapshot()
    game.step(DT, [key_event(game, pygame.KEYUP, "move_right")], allow_debug=False)
    assert isinstance(game._scene, StageClearScene)
    assert game._scene._next_stage_id == 2
    assert game._scene._weapon["main_level"] == 1


def test_post_boss_upgrade_accepts_companion_stock_without_player_stock(game):
    scene = make_scene(game)
    scene._companion.stock = 1
    defeat_boss(scene)
    finish_defeat_dialogue(game, scene)
    tap(game, "weapon_select")
    assert scene._upgrading
    assert scene._upg_zone == "bottom"
    assert scene.player.weapon.weapon_stock == 0
    tap(game, "ui_accept")
    tap(game, "ui_accept")
    assert not scene._upgrading
    assert scene._companion.stock == 0 and scene._companion.lv_hp == 1
    assert scene.player.weapon.main_level == 0


@pytest.mark.parametrize("phase", ["paused", "dialogue_delay", "dialogue", "final"])
def test_upgrade_action_stays_blocked_outside_post_boss_walking(game, phase):
    scene = make_scene(game, stage=4 if phase == "final" else 1)
    scene.player.weapon.weapon_stock = 1
    defeat_boss(scene)
    # Prepare each suspended phase; actual input still goes through Game.step.
    if phase == "dialogue":
        scene._defeat_dialogue_delay = 0
        scene._defeat_dialogue_active = True
    elif phase != "dialogue_delay":
        scene._defeat_dialogue_delay = 0
        scene._defeat_dialogue_active = False
    if phase == "paused":
        tap(game, "pause")
        assert scene._paused
    assert phase != "final" or scene._post_boss_next_id is None
    tap(game, "weapon_select")
    assert not scene._upgrading
    assert scene.player.weapon.weapon_stock == 1
    assert scene.player.weapon.main_level == 0
    if phase == "dialogue":
        assert scene._defeat_dialogue_active and scene._defeat_dialogue_index == 0
