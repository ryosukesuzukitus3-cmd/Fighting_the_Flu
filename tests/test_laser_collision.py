"""Laser damage follows visible pixels while retaining its size and strength."""
from __future__ import annotations

import pygame
import pytest

from src.core.game import Game
from src.entities.bullets.enemy_bullet import EnemyBullet
from src.entities.bullets.laser_fx import (
    LaserBeamSprite, ZUNDA_PALETTE, zunda_beam_frames,
)
from src.managers.input import InputManager
from src.scenes.game_scene import GameScene

DT = 1 / 60


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("FLU_USER_DATA_DIR", str(tmp_path))
    instance = Game()
    instance.input = InputManager(instance.settings, physical_input=False)
    yield instance
    instance.close()


def prepare_scene(game, position):
    """Isolated arena, normal player and damage processing, no invulnerability."""
    scene = GameScene(game, stage_id=2)
    game.change_scene(scene)
    game.step(DT, [], False)
    scene.spawner.skip_all_events()
    for group in (scene.terrain, scene.enemies, scene.items, scene.enemy_bullets):
        group.empty()
    scene._companion = None
    scene.camera.scroll_speed = scene._stage_scroll_speed = 0
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene.player._entering = False
    scene.player._invincible_timer = 0
    scene.player.sx, scene.player.sy = position
    scene.player.rect.topleft = position
    return scene


def real_beam(game, *, warning_only=False, damage=12):
    beam = LaserBeamSprite(
        322.5, 300, 645, 286, palette=ZUNDA_PALETTE, lifetime=1.3,
        damage=damage, warning_only=warning_only,
        frames=zunda_beam_frames(game.resources), frame_mode="progress",
        taper_time=0.48,
    )
    beam.update(0.25)
    return beam


@pytest.mark.parametrize("position", [(175, 414), (175, 135), (600, 285)])
def test_transparent_particle_cannon_padding_does_not_damage_player(game, position):
    scene = prepare_scene(game, position)
    beam = real_beam(game)
    scene.enemy_bullets.add(beam)
    # These targets intersect the old rectangular collider, but only empty RGBA.
    assert beam.rect.colliderect(scene.player.hit_rect)
    overlap = beam.rect.clip(scene.player.hit_rect).move(-beam.rect.x, -beam.rect.y)
    assert not beam.image.subsurface(overlap).get_bounding_rect(min_alpha=1)
    game.step(DT, [], False)
    assert scene.player.hp == 100
    assert not beam.collides_with_rect(scene.player.hit_rect)
    assert beam.rect.size == (645, 286)


@pytest.mark.parametrize("warning_only", [False, True])
@pytest.mark.parametrize("damage", [12, 16])
def test_visible_cannon_core_keeps_damage_and_warning_rules(game, warning_only, damage):
    scene = prepare_scene(game, (175, 285))
    beam = real_beam(game, warning_only=warning_only, damage=damage)
    scene.enemy_bullets.add(beam)
    game.step(DT, [], False)
    assert beam.collides_with_rect(scene.player.hit_rect)
    assert scene.player.hp == (100 if warning_only else 100 - damage)
    assert beam.damage == damage
    assert beam.alive()  # A damaging continuous beam is not consumed on contact.
    assert beam.rect.size == (645, 286)


def test_normal_enemy_bullet_keeps_its_rectangular_collision(game):
    scene = prepare_scene(game, (175, 285))
    bullet = EnemyBullet(*scene.player.hit_rect.center, 0, 0, damage=7, radius=10)
    scene.enemy_bullets.add(bullet)
    game.step(DT, [], False)
    assert scene.player.hp == 93
    assert not bullet.alive()


def test_mask_tracks_animated_frames_and_keeps_faint_glow():
    first = pygame.Surface((80, 20), pygame.SRCALPHA)
    second = first.copy()
    first.fill((80, 255, 120, 1), (5, 5, 10, 10))
    second.fill((80, 255, 120, 255), (60, 5, 10, 10))
    beam = LaserBeamSprite(
        40, 10, 80, 20, palette=ZUNDA_PALETTE, lifetime=2, fade_in=0,
        frames=[first, second], frame_fps=1, warning_only=False,
    )
    left, right = pygame.Rect(5, 5, 10, 10), pygame.Rect(60, 5, 10, 10)
    assert beam.collides_with_rect(left)  # Alpha 1 still counts as visible.
    assert not beam.collides_with_rect(right)
    beam.update(1)
    assert not beam.collides_with_rect(left)
    assert beam.collides_with_rect(right)


def test_mask_excludes_transparent_holes_inside_image_bounds():
    frame = pygame.Surface((80, 20), pygame.SRCALPHA)
    frame.fill((80, 255, 120, 255))
    frame.fill((0, 0, 0, 0), (30, 5, 20, 10))
    beam = LaserBeamSprite(
        40, 10, 80, 20, palette=ZUNDA_PALETTE, lifetime=2, fade_in=0,
        frames=[frame], warning_only=False,
    )
    assert not beam.collides_with_rect(pygame.Rect(32, 6, 16, 8))
    assert beam.collides_with_rect(pygame.Rect(28, 6, 6, 8))


def test_fully_transparent_fade_frame_cannot_damage():
    frame = pygame.Surface((80, 20), pygame.SRCALPHA)
    frame.fill((80, 255, 120, 255))
    beam = LaserBeamSprite(
        40, 10, 80, 20, palette=ZUNDA_PALETTE, lifetime=2,
        fade_in=0.5, frames=[frame], warning_only=False,
    )
    target = pygame.Rect(30, 5, 20, 10)
    assert not beam.collides_with_rect(target)
    beam.update(0.25)
    assert beam.collides_with_rect(target)
