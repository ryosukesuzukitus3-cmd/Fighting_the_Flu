from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy
from src.core.constants import SCREEN_HEIGHT
from src.core.registries import enemy_stats

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera
    from src.entities.player import Player

_ZIGZAG_SPEED_X = 130.0
_ZIGZAG_SPEED_Y = 160.0
_ZIGZAG_RANGE   = 120.0  # Y方向の折り返し幅
_SHOOT_INTERVAL = 2.2    # 射撃間隔（秒）
_BULLET_SPEED   = 215.0

_BASE_INTERVAL = 2.2
_ENH_INTERVAL  = 1.3
_SPREAD_BASE   = (-0.18, 0.0, 0.18)
_SPREAD_ENH    = (-0.28, -0.10, 0.10, 0.28)
_STATS         = enemy_stats("EnemyPachemon")


class EnemyPachemon(Enemy):
    """ジグザグ移動+狙い撃ちの中強度敵。"""

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
        hp    = _STATS.enhanced_hp    if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._shoot_interval = _ENH_INTERVAL if enhanced else _BASE_INTERVAL
        raw        = game.resources.image("graphic/enemy_パチえもん.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))

        self._game          = game
        self._origin_y      = world_y
        self._vy            = _ZIGZAG_SPEED_Y
        self._enemy_bullets = enemy_bullets
        self._player        = player
        self._shoot_timer   = self._shoot_interval * 0.6  # 初回は少し早め
        self._shot_index    = 0
        self._init_glow()

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        if self._enemy_bullets is not None and self._player is not None:
            self._shoot_timer -= dt
            if self._shoot_timer <= 0:
                self._fire()
                self._shoot_timer = self._shoot_interval

    def _fire(self) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet
        sx = self.rect.centerx
        sy = self.rect.centery
        dx = self._player.sx - sx
        dy = self._player.sy - sy
        d  = math.hypot(dx, dy) or 1
        base = math.atan2(dy, dx)
        self._shot_index += 1
        if self._shot_index % 2 == 0:
            offsets = _SPREAD_ENH if self.enhanced else _SPREAD_BASE
        else:
            offsets = (0.0,)
        for off in offsets:
            a = base + off
            self._enemy_bullets.add(
                EnemyBullet(
                    sx,
                    sy,
                    math.cos(a) * _BULLET_SPEED,
                    math.sin(a) * _BULLET_SPEED,
                    radius=5,
                    color=(255, 95, 205) if off else (255, 70, 70),
                )
            )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.6)

    def _move(self, dt: float) -> None:
        self.world_x -= self.speed * dt
        self.world_y += self._vy * dt

        top    = max(60.0, self._origin_y - _ZIGZAG_RANGE)
        bottom = min(float(SCREEN_HEIGHT - 60), self._origin_y + _ZIGZAG_RANGE)
        if self.world_y >= bottom:
            self._vy = -abs(self._vy)
        elif self.world_y <= top:
            self._vy = abs(self._vy)
