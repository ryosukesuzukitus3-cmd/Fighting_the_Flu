from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game

_BASE_HP    = 1
_BASE_SPEED = 160.0
_ENH_HP     = 3
_ENH_SPEED  = 210.0


class EnemyVirus(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp    = _ENH_HP    if enhanced else _BASE_HP
        speed = _ENH_SPEED if enhanced else _BASE_SPEED
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        raw        = game.resources.image("graphic/enemy_virus.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.77), int(h * 0.77)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()
