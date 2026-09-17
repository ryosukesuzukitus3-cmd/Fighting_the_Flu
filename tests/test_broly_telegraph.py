"""A visible Broly warning must leave room for ordinary vertical movement."""
from __future__ import annotations

import pygame
import pytest

from src.core.game import Game
from src.entities.bullets.laser_fx import LaserBeamSprite
from src.entities.enemies.broly import EnemyBroly
from src.managers.input import InputManager
from src.scenes.game_scene import GameScene

DT = 1 / 60


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    instance = Game()
    yield instance
    instance.close()


def simulate_dodge(game, direction, enhanced=True, snapshot=None):
    """Prepared open arena; use real scene updates, inputs, shots and damage.

    Wait twelve full frames after the warning appears, then hold one direction
    through the cannon's firing phase. No speed upgrade or invulnerability.
    """
    game.input = InputManager(game.settings, physical_input=False)
    scene = GameScene(game, stage_id=4)
    game.change_scene(scene)
    game.step(DT, [], False)
    scene.spawner.skip_all_events()
    scene.terrain.empty()
    scene.enemies.empty()
    scene.items.empty()
    scene.enemy_bullets.empty()
    scene._companion = None
    scene.camera.scroll_speed = scene._stage_scroll_speed = 0
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene.player._entering = False
    scene.player._invincible_timer = 0
    scene.player.sx, scene.player.sy = 120, 280
    scene.player.rect.topleft = (120, 280)
    assert scene.player.weapon.speed_level == 0
    enemy = EnemyBroly(game, 620, 280, enemy_bullets=scene.enemy_bullets,
                       player=scene.player, enhanced=enhanced)
    scene.enemies.add(enemy)
    for _ in range(120):
        game.step(DT, [], False)
        if enemy._state == "windup":
            break
    assert enemy._state == "windup"
    warning = next(b for b in scene.enemy_bullets
                   if isinstance(b, LaserBeamSprite) and b.warning_only)
    warning_rows = [warning.rect.centery]
    if snapshot:
        snapshot(game, "warning")
    result = {"direction": direction, "enhanced": enhanced,
              "reaction_frames": 12, "warning_y": warning.rect.centery,
              "hp_before": scene.player.hp, "trace": []}
    for frame in range(1, 200):
        events = []
        if frame == 13 and direction:
            events = [pygame.event.Event(pygame.KEYDOWN,
                      key=game.settings.get_key(f"move_{direction}"))]
        game.step(DT, events, False)
        if warning.alive():
            warning_rows.append(warning.rect.centery)
        beams = [b for b in scene.enemy_bullets
                 if isinstance(b, LaserBeamSprite) and not b.warning_only]
        if beams and "fire_frame" not in result:
            beam = beams[0]
            result.update(fire_frame=frame, beam_y=beam.rect.centery,
                          beam_height=beam.rect.height, damage=beam.damage,
                          player_y=scene.player.sy, player_hit_rect=list(scene.player.hit_rect),
                          beam_overlap=beam.rect.colliderect(scene.player.hit_rect),
                          hp_at_fire=scene.player.hp, charge_vy=enemy._vy)
            if snapshot:
                snapshot(game, "fire")
        result["trace"].append({"frame": frame, "state": enemy._state,
                                "enemy_y": enemy.world_y, "player_y": scene.player.sy,
                                "hp": scene.player.hp})
        if "fire_frame" in result and enemy._state == "charge":
            break
    assert "fire_frame" in result
    result["warning_rows"] = sorted(set(warning_rows))
    result["hp_after_fire"] = scene.player.hp
    return result


@pytest.mark.parametrize("enhanced", [False, True])
@pytest.mark.parametrize("direction", ["up", "down"])
def test_basic_speed_can_evade_after_twelve_reaction_frames(game, direction, enhanced):
    result = simulate_dodge(game, direction, enhanced)
    assert not result["beam_overlap"]
    assert result["hp_at_fire"] == result["hp_before"]
    assert result["hp_after_fire"] == result["hp_before"]
    assert result["warning_rows"] == [result["beam_y"]]
    assert result["beam_height"] == 286
    assert result["charge_vy"] == (-1 if direction == "up" else 1) * (215 if enhanced else 170)


@pytest.mark.parametrize("enhanced", [False, True])
def test_staying_in_the_warned_band_still_takes_cannon_damage(game, enhanced):
    result = simulate_dodge(game, None, enhanced)
    assert result["beam_overlap"]
    assert result["damage"] == (16 if enhanced else 12)
    assert result["hp_at_fire"] == result["hp_before"] - result["damage"]
