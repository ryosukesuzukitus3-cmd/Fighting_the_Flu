from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.entities.bullets.enemy_bullet import EnemyBullet

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.enemies.boss import Boss
    from src.entities.player import Player

_DRONE_IMAGES = (
    "graphic/boss_matching_zero_drone_a.png",
    "graphic/boss_matching_zero_drone_b.png",
    "graphic/boss_matching_zero_drone_c.png",
)
_DRONE_OFFSETS = (
    (-205.0, -120.0),
    (118.0, 92.0),
    (-218.0, 122.0),
)
_DRONE_HP = 12
_DRONE_SCALE = 0.21
_SHOT_INTERVAL = 1.85
_SHOT_SPEED = 215.0


class MatchingZeroDrone(pygame.sprite.Sprite):
    """Boss-only shield drone for Matching Zero."""

    drops_enabled = False
    drop_chance = 0.0

    def __init__(
        self,
        game: "Game",
        boss: "Boss",
        index: int,
        enemy_bullets: pygame.sprite.Group | None = None,
        player: "Player | None" = None,
    ) -> None:
        super().__init__()
        self._game = game
        self._boss = boss
        self._index = index % len(_DRONE_IMAGES)
        self.requires_laser = self._index == 1
        self._enemy_bullets = enemy_bullets
        self._player = player
        self.hp = _DRONE_HP
        self.world_x = 0.0
        self.world_y = 0.0
        self._time = self._index * 0.73
        self._shoot_timer = 0.55 + self._index * 0.43
        self._flash_timer = 0.0

        raw = self._game.resources.image(_DRONE_IMAGES[self._index])
        w = max(24, int(raw.get_width() * _DRONE_SCALE))
        h = max(24, int(raw.get_height() * _DRONE_SCALE))
        self._base_image = pygame.transform.smoothscale(raw, (w, h))
        if self.requires_laser:
            self._base_image = self._make_laser_lock_image(self._base_image)
        self.image = self._base_image
        self.rect = self.image.get_rect(center=self._target_center())

    @staticmethod
    def _make_laser_lock_image(base: pygame.Surface) -> pygame.Surface:
        img = base.copy()
        w, h = img.get_size()
        lock = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.circle(lock, (175, 90, 255, 80), (w // 2, h // 2), min(w, h) // 2 - 3)
        pygame.draw.circle(lock, (230, 180, 255, 185), (w // 2, h // 2), min(w, h) // 2 - 4, 2)
        pygame.draw.line(lock, (245, 220, 255, 180), (w // 2, 5), (w // 2, h - 6), 2)
        img.blit(lock, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return img

    def update(self, dt: float, camera: "Camera") -> None:
        self._time += dt
        self._flash_timer = max(0.0, self._flash_timer - dt)
        self.rect.center = self._target_center()
        self.world_x = camera.to_world_x(self.rect.centerx)
        self.world_y = float(self.rect.centery)
        self._update_flash_image()
        self._tick_shot(dt)

    def _target_center(self) -> tuple[int, int]:
        bx, by = self._boss.rect.center
        ox, oy = _DRONE_OFFSETS[self._index]
        sx = bx + ox + math.sin(self._time * 1.6 + self._index) * 9.0
        sy = by + oy + math.cos(self._time * 2.1 + self._index * 0.6) * 11.0
        sx = max(46.0, min(SCREEN_WIDTH - 46.0, sx))
        sy = max(62.0, min(SCREEN_HEIGHT - 62.0, sy))
        return int(sx), int(sy)

    def _update_flash_image(self) -> None:
        if self._flash_timer <= 0.0:
            self.image = self._base_image
            return
        img = self._base_image.copy()
        img.fill((255, 255, 255, 85), special_flags=pygame.BLEND_RGBA_ADD)
        self.image = img

    def _tick_shot(self, dt: float) -> None:
        if self._enemy_bullets is None or self._player is None:
            return
        self._shoot_timer -= dt
        if self._shoot_timer > 0.0:
            return
        self._fire()
        self._shoot_timer = _SHOT_INTERVAL + self._index * 0.18

    def _fire(self) -> None:
        sx, sy = self.rect.center
        dx = self._player.sx - sx
        dy = self._player.sy - sy
        d = math.hypot(dx, dy) or 1.0
        self._enemy_bullets.add(
            EnemyBullet(
                sx,
                sy,
                (dx / d) * _SHOT_SPEED,
                (dy / d) * _SHOT_SPEED,
                radius=5,
                color=(70, 225, 255),
            )
        )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.38)

    def blocks_projectile_damage(self, bullet) -> bool:
        return self.requires_laser

    def take_damage(self, amount: int) -> bool:
        if self.requires_laser:
            self._flash_timer = 0.06
            return False
        return self._apply_damage(amount)

    def take_laser_damage(self, amount: int) -> bool:
        return self._apply_damage(amount)

    def _apply_damage(self, amount: int) -> bool:
        self.hp -= amount
        self._flash_timer = 0.08
        return self.hp <= 0

    def is_off_left(self, camera: "Camera") -> bool:
        return False
