from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game

_APPROACH_SPEED = 80.0
_CHARGE_SPEED   = 520.0
_APPROACH_TIME  = 1.2   # 秒：突進開始までの助走時間

_BASE_HP      = 5
_ENH_HP       = 14
_ENH_APPROACH = 100.0
_ENH_CHARGE   = 650.0


class EnemyBroly(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float,
                 target_y: float | None = None, *, enhanced: bool = False) -> None:
        hp       = _ENH_HP       if enhanced else _BASE_HP
        approach = _ENH_APPROACH if enhanced else _APPROACH_SPEED
        super().__init__(world_x, world_y, hp=hp, speed=approach, enhanced=enhanced)
        self._charge_speed = _ENH_CHARGE if enhanced else _CHARGE_SPEED
        raw        = game.resources.image("graphic/enemy_ブロリー.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._target_y: float = target_y if target_y is not None else world_y
        self._state: str = "approach"
        self._timer: float = 0.0
        self._vy:    float = 0.0
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._timer += dt
        if self._state == "approach":
            self.world_x -= self.speed * dt
            if self._timer >= _APPROACH_TIME:
                self._state = "charge"
                dy = self._target_y - self.world_y
                d  = abs(dy) if abs(dy) > 1 else 1
                self._vy = (dy / d) * 180.0
        else:
            self.world_x -= self._charge_speed * dt
            self.world_y += self._vy * dt
