from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from src.core.constants import SCREEN_WIDTH
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game
    from src.entities.player import Player

_CHARGE_SPEED   = 520.0
_APPROACH_TIME  = 0.9   # 秒：突進準備までの助走時間
_WINDUP_TIME    = 0.36  # 秒：警告ラインを出してから突進

_ENH_CHARGE   = 650.0
_STATS        = enemy_stats("EnemyBroly")


class EnemyBroly(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float,
                 target_y: float | None = None,
                 enemy_bullets: pygame.sprite.Group | None = None,
                 player: "Player | None" = None,
                 *, enhanced: bool = False) -> None:
        hp       = _STATS.enhanced_hp    if enhanced else _STATS.base_hp
        approach = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=approach, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        self._charge_speed = _ENH_CHARGE if enhanced else _CHARGE_SPEED
        raw        = game.resources.image("graphic/enemy_ブロリー.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._target_y: float = target_y if target_y is not None else world_y
        self._state: str = "approach"
        self._timer: float = 0.0
        self._vy:    float = 0.0
        self._warning_fired = False
        self._shock_fired = False
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._timer += dt
        if self._state == "approach":
            self.world_x -= self.speed * dt
            if self._player is not None:
                self._target_y = float(self._player.sy)
            self.world_y += (self._target_y - self.world_y) * min(1.0, dt * 2.2)
            if self._timer >= _APPROACH_TIME:
                self._state = "windup"
                self._timer = 0.0
                self._fire_warning()
        elif self._state == "windup":
            self.world_x -= self.speed * 0.22 * dt
            if self._player is not None:
                self._target_y = float(self._player.sy)
            self.world_y += (self._target_y - self.world_y) * min(1.0, dt * 6.5)
            if self._timer >= _WINDUP_TIME:
                self._state = "charge"
                self._timer = 0.0
                dy = self._target_y - self.world_y
                d = abs(dy) if abs(dy) > 1 else 1
                self._vy = (dy / d) * (215.0 if self.enhanced else 170.0)
                self._fire_shock()
        elif self._state == "charge":
            self.world_x -= self._charge_speed * dt
            self.world_y += self._vy * dt

    def _fire_warning(self) -> None:
        if self._enemy_bullets is None or self._warning_fired:
            return
        from src.entities.bullets.enemy_bullet import EnemyBullet

        self._warning_fired = True
        self._enemy_bullets.add(
            EnemyBullet(
                SCREEN_WIDTH / 2,
                self._target_y,
                0.0,
                0.0,
                size=(SCREEN_WIDTH + 40, 12),
                color=(255, 70, 70),
                lifetime=_WINDUP_TIME,
                terrain_passthrough=True,
                warning_only=True,
            )
        )

    def _fire_shock(self) -> None:
        if self._enemy_bullets is None or self._shock_fired:
            return
        from src.entities.bullets.enemy_bullet import EnemyBullet

        self._shock_fired = True
        sx, sy = self.rect.center
        for off in (-0.32, 0.32):
            self._enemy_bullets.add(
                EnemyBullet(
                    sx,
                    sy,
                    -math.cos(off) * 280.0,
                    math.sin(off) * 280.0,
                    radius=6,
                    color=(255, 170, 65),
                )
            )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.5)
