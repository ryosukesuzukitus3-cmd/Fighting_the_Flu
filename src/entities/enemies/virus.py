from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game

_STATS = enemy_stats("EnemyVirus")


class EnemyVirus(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp    = _STATS.enhanced_hp    if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        raw        = game.resources.image("graphic/enemy_virus.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.77), int(h * 0.77)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()
