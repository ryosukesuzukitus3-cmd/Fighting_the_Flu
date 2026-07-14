from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player


_STATS = enemy_stats("EnemyShogiPawn")


class EnemyShogiPawn(Enemy):
    """Stage 4 pawn: advances in a declared file and promotes into one fast shot."""

    def __init__(self, game: "Game", world_x: float, world_y: float,
                 enemy_bullets: pygame.sprite.Group | None = None,
                 player: "Player | None" = None, *, enhanced: bool = False) -> None:
        hp = _STATS.enhanced_hp if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp, speed, enhanced=enhanced)
        self._game, self._enemy_bullets, self._player = game, enemy_bullets, player
        self._advance = 0.95
        self._fired = False
        self.image = self._sprite()
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    @staticmethod
    def _sprite() -> pygame.Surface:
        img = pygame.Surface((34, 42), pygame.SRCALPHA)
        pygame.draw.polygon(img, (235, 190, 80), ((17, 1), (32, 12), (28, 39), (6, 39), (2, 12)))
        pygame.draw.polygon(img, (90, 48, 22), ((17, 1), (32, 12), (28, 39), (6, 39), (2, 12)), 2)
        return img

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        self._advance -= dt
        if self._advance <= 0 and not self._fired and self._enemy_bullets is not None:
            from src.entities.bullets.enemy_bullet import EnemyBullet
            self._enemy_bullets.add(EnemyBullet(self.rect.centerx, self.rect.centery, -390, 0,
                                                 radius=7, color=(255, 175, 70)))
            self._fired = True
