from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy
from src.core.camera import Camera
from src.core.constants import SCREEN_HEIGHT
from src.core.registries import enemy_stats

if TYPE_CHECKING:
    from src.core.game import Game

_WAVE_AMP  = 70.0   # 振れ幅 px
_WAVE_FREQ = 1.2    # Hz
_FEINT_INTERVAL = 0.95
_FEINT_MAX_OFFSET = 46.0

_STATS = enemy_stats("EnemyTakeshi")


class EnemyTakeshi(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp    = _STATS.enhanced_hp    if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        raw        = game.resources.image("graphic/enemy_タケシ.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._origin_y = world_y
        self._time: float = random.uniform(0.0, math.tau)
        self._feint_timer = _FEINT_INTERVAL * random.uniform(0.45, 0.9)
        self._feint_offset = 0.0
        self._feint_target = 0.0
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._time += dt
        self._feint_timer -= dt
        if self._feint_timer <= 0.0:
            direction = 1.0 if math.sin(self._time * 2.8) >= 0 else -1.0
            amp = _FEINT_MAX_OFFSET * (1.2 if self.enhanced else 1.0)
            self._feint_target = direction * random.uniform(amp * 0.45, amp)
            self._feint_timer = _FEINT_INTERVAL * random.uniform(0.75, 1.15)

        self._feint_offset += (self._feint_target - self._feint_offset) * min(1.0, dt * 5.0)
        self._feint_target *= max(0.0, 1.0 - dt * 1.8)
        self.world_x -= self.speed * dt

        amp = _WAVE_AMP * (1.12 if self.enhanced else 1.0)
        wave = amp * math.sin(2 * math.pi * _WAVE_FREQ * self._time)
        wobble = 12.0 * math.sin(self._time * 5.0)
        self.world_y = max(
            44.0,
            min(float(SCREEN_HEIGHT - 44), self._origin_y + wave + wobble + self._feint_offset),
        )
