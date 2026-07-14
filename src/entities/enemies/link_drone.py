from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player


_STATS = enemy_stats("EnemyLinkDrone")


class EnemyLinkDrone(Enemy):
    """Stage 3 target-priority enemy: advances through a fortress with tri-shots."""

    def __init__(self, game: "Game", world_x: float, world_y: float,
                 enemy_bullets: pygame.sprite.Group | None = None,
                 player: "Player | None" = None, *, enhanced: bool = False) -> None:
        hp = _STATS.enhanced_hp if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp, speed, enhanced=enhanced)
        self._game, self._enemy_bullets, self._player = game, enemy_bullets, player
        self._timer = 0.65
        self.image = self._sprite()
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    @staticmethod
    def _sprite() -> pygame.Surface:
        img = pygame.Surface((42, 42), pygame.SRCALPHA)
        pygame.draw.circle(img, (25, 80, 100), (21, 21), 18)
        pygame.draw.circle(img, (70, 235, 255), (21, 21), 14, 3)
        pygame.draw.circle(img, (230, 255, 255), (21, 21), 5)
        return img

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        self._timer -= dt
        if self._timer <= 0 and self._enemy_bullets is not None and self._player is not None:
            sx, sy = self.rect.center
            dx, dy = self._player.sx - sx, self._player.sy - sy
            d = math.hypot(dx, dy) or 1.0
            for off in (-36.0, 0.0, 36.0):
                a = math.atan2(dy, dx) + math.radians(off)
                from src.entities.bullets.enemy_bullet import EnemyBullet
                self._enemy_bullets.add(EnemyBullet(sx, sy, math.cos(a) * 245, math.sin(a) * 245,
                                                     radius=5, color=(85, 235, 255)))
            self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.35)
            self._timer = 1.35
