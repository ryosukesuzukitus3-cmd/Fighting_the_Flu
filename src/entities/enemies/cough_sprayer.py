from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING

import pygame

from src.core.constants import SCREEN_HEIGHT
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player

_STATS = enemy_stats("EnemyCoughSprayer")
_BASE_INTERVAL = 1.55
_ENH_INTERVAL = 1.05
_BULLET_SPEED = 185.0
_FAN_BASE = (-0.26, 0.0, 0.26)
_FAN_ENH = (-0.38, -0.14, 0.14, 0.38)


class EnemyCoughSprayer(Enemy):
    """蛇行しながら咳のような扇状弾を吐く雑魚敵。"""

    def __init__(
        self,
        game: "Game",
        world_x: float,
        world_y: float,
        enemy_bullets: pygame.sprite.Group | None = None,
        player: "Player | None" = None,
        *,
        enhanced: bool = False,
    ) -> None:
        hp = _STATS.enhanced_hp if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        self._origin_y = world_y
        self._time = random.uniform(0.0, math.tau)
        self._shoot_interval = _ENH_INTERVAL if enhanced else _BASE_INTERVAL
        self._shoot_timer = self._shoot_interval * 0.45

        raw = game.resources.image("graphic/enemy_cough_sprayer.png")
        self.image = pygame.transform.scale(raw, raw.get_size())
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._time += dt
        self.world_x -= self.speed * dt
        wave = math.sin(self._time * 2.2) * 38.0 + math.sin(self._time * 5.1) * 10.0
        self.world_y = max(46.0, min(float(SCREEN_HEIGHT - 46), self._origin_y + wave))

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        if self._enemy_bullets is None or self._player is None:
            return
        self._shoot_timer -= dt
        if self._shoot_timer <= 0.0:
            self._fire_fan()
            self._shoot_timer = self._shoot_interval

    def _fire_fan(self) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet

        sx, sy = self.rect.center
        dx = self._player.sx - sx
        dy = self._player.sy - sy
        base = math.atan2(dy, dx)
        offsets = _FAN_ENH if self.enhanced else _FAN_BASE
        for off in offsets:
            a = base + off
            self._enemy_bullets.add(
                EnemyBullet(
                    sx,
                    sy,
                    math.cos(a) * _BULLET_SPEED,
                    math.sin(a) * _BULLET_SPEED,
                    radius=4,
                    color=(115, 245, 210),
                )
            )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.46)
