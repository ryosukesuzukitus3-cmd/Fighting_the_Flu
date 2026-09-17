"""Narrative presentation must not invent a kill or consume frozen attacks."""
from __future__ import annotations

import pygame
import pytest

from src.core.game import Game
from src.entities.bullets.enemy_bullet import EnemyBullet
from src.entities.enemies.boss import Boss
from src.managers.input import InputManager
from src.scenes.game_scene import GameScene
from src.story.script import BOSS_MID, FINAL_SEQ


@pytest.fixture
def final_scene(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    game = Game()
    game.input = InputManager(game.settings, physical_input=False)
    scene = GameScene(game, stage_id=4)
    game.change_scene(scene)
    game.step(1 / 60, [], False)
    scene.terrain.empty()
    scene.enemies.empty()
    scene.items.empty()
    scene._companion = None
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene._boss_intro_state = "fighting"
    scene.player._entering = False
    scene.player.weapon.laser_level = 3
    boss = scene._boss = Boss(game, stage_id=4)
    boss._transform_form2()
    boss._transform_form3()
    boss._state = "fight"
    boss.sx, boss.sy = 620, 260
    boss.rect.center = (620, 260)
    boss.hp = int(boss.max_hp * 0.29)
    scene._final._final_phase = 1
    scene._final._f3_act1_mid_shown = True
    scene._final._regen_timer = 1
    yield scene
    game.close()


def test_fakeout_shows_collapse_before_dialogue_without_changing_combat_state(final_scene):
    scene = final_scene
    boss, director = scene._boss, scene._final
    scene.laser.state, scene.laser._gauge = "firing", 0.6
    scene.enemy_bullets.add(EnemyBullet(200, 200, -30, 0))
    state = (boss.hp, boss.rect.copy(), boss._time, scene.player.hp, scene._stage_elapsed)
    director.update_combat(0)
    assert director.reaction_active and not director.dialogue_active
    assert not scene.enemy_bullets  # The existing fakeout clears enemy attacks.
    assert not scene._accepts_combat_input
    scene.game.step(0.69, [], False)
    assert director.reaction_active and not director.dialogue_active

    # Even a confirm on the transition frame cannot skip the opening line.
    enter = scene.game.settings.get_key("ui_accept")
    scene.game.step(0.02, [pygame.event.Event(pygame.KEYDOWN, key=enter)], False)
    assert not director.reaction_active and director.dialogue_active
    assert director._final_dialogue_idx == 0
    assert director._final_dialogue_pages == FINAL_SEQ["fakeout"]
    assert director.draw_boss_reaction(scene.game.screen)
    assert (boss.hp, boss.rect, boss._time, scene.player.hp, scene._stage_elapsed) == state
    assert scene.laser.state == "firing" and scene.laser._gauge == 0.6
    assert not scene._post_boss

    scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYUP, key=enter)], False)
    scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=enter)], False)
    assert director._final_dialogue_idx == 1
    assert not director.draw_boss_reaction(scene.game.screen)
    assert boss.hp == state[0]
    for _ in FINAL_SEQ["fakeout"][1:]:
        scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYUP, key=enter)], False)
        scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=enter)], False)
    assert director.seq == "sengen"
    assert director._final_dialogue_pages == FINAL_SEQ["sengen"]


def test_large_hit_does_not_start_fakeout_under_midfight_dialogue(final_scene):
    scene = final_scene
    scene._final._f3_act1_mid_shown = False
    scene._final.update_combat(0)
    assert scene._cutin_active
    assert not scene._final.reaction_active
    assert not scene._final.dialogue_active
    enter = scene.game.settings.get_key("ui_accept")
    for _ in BOSS_MID["4f3mid"]:
        scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYUP, key=enter)], False)
        scene.game.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=enter)], False)
    assert not scene._cutin_active
    scene.game.step(1 / 60, [], False)
    assert scene._final.reaction_active


def test_dialogue_suppresses_frozen_light_but_preserves_attack_state(final_scene, monkeypatch):
    scene = final_scene
    scene._start_combat_cutin(BOSS_MID["4f3mid"])
    scene.laser.state, scene.laser._gauge = "firing", 0.6
    scene.laser._timer = 0.5
    bullet = EnemyBullet(220, 200, -30, 0, lifetime=3)
    scene.enemy_bullets.add(bullet)
    scene._boss.hit_flash_timer = 0.08
    scene._laser_flash_timer = 0.08
    scene._form2_flash_timer = 0.5
    scene._boss_kill_flash_timer = 1.2
    scene._boss_break_flash_timer = 0.34
    laser_draws = []
    monkeypatch.setattr(scene.laser, "draw", lambda *args: laser_draws.append(True))
    monkeypatch.setattr(scene.bg, "draw", lambda screen, x: screen.fill((10, 20, 30)))
    monkeypatch.setattr(scene, "_draw_boss_gimmick", lambda screen: None)

    scene.draw(scene.game.screen)
    assert not laser_draws
    # Full-screen and boss-hit white flashes cannot cover the frozen scene.
    assert scene.game.screen.get_at((0, 150))[:3] == (10, 20, 30)
    center = (scene._boss.image.get_width() // 2, scene._boss.image.get_height() // 2)
    assert scene.game.screen.get_at(scene._boss.rect.center)[:3] == scene._boss.image.get_at(center)[:3]
    before = (bullet.rect.copy(), bullet.lifetime, scene._boss.hp, scene._stage_elapsed)
    scene.game.step(0.1, [], False)
    assert (bullet.rect, bullet.lifetime, scene._boss.hp, scene._stage_elapsed) == before
    assert (scene.laser.state, scene.laser._gauge, scene.laser._timer) == ("firing", 0.6, 0.5)
    assert not laser_draws
    scene._cutin_active = False
    scene.draw(scene.game.screen)
    assert laser_draws == [True]
