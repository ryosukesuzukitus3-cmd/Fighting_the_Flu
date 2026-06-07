from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy
from src.core.camera import Camera

if TYPE_CHECKING:
    from src.core.game import Game

_WAVE_AMP  = 70.0   # 振れ幅 px
_WAVE_FREQ = 1.2    # Hz

_BASE_HP    = 2
_BASE_SPEED = 110.0
_ENH_HP     = 6
_ENH_SPEED  = 145.0


class EnemyTakeshi(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp    = _ENH_HP    if enhanced else _BASE_HP
        speed = _ENH_SPEED if enhanced else _BASE_SPEED
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        raw        = game.resources.image("graphic/enemy_タケシ.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._origin_y = world_y
        self._time: float = 0.0
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._time    += dt
        self.world_x  -= self.speed * dt
        self.world_y   = self._origin_y + _WAVE_AMP * math.sin(2 * math.pi * _WAVE_FREQ * self._time)
