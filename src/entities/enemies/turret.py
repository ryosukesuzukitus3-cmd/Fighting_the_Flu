"""砲台タイプの雑魚敵。地形に固定（speed=0）され、自機を狙い撃ちする。

カメラスクロールに乗って地形と一体で左へ流れる（自走しない）。
EnemyPachemon の狙い撃ちロジックを踏襲し、発射時に SE_ENEMY_SHOT（dummy）を鳴らす。
"""
from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera
    from src.entities.player import Player

_BASE_HP       = 6
_ENH_HP        = 12
_SHOOT_INTERVAL = 1.8
_ENH_INTERVAL   = 1.1
_BULLET_SPEED   = 230.0
_SIZE           = 40


class EnemyTurret(Enemy):
    """地形固定の狙い撃ち砲台。"""

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
        hp = _ENH_HP if enhanced else _BASE_HP
        # speed=0 → 自走せずカメラスクロールで地形と一体に流れる
        super().__init__(world_x, world_y, hp=hp, speed=0.0, enhanced=enhanced)
        self._game           = game
        self._enemy_bullets  = enemy_bullets
        self._player         = player
        self._shoot_interval = _ENH_INTERVAL if enhanced else _SHOOT_INTERVAL
        self._shoot_timer    = self._shoot_interval * 0.5
        self.image = self._make_sprite()
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    @staticmethod
    def _make_sprite() -> pygame.Surface:
        s = _SIZE
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        # 台座
        pygame.draw.rect(surf, (60, 64, 74), (4, s // 2, s - 8, s // 2 - 2), border_radius=4)
        # ドーム
        pygame.draw.circle(surf, (96, 100, 112), (s // 2, s // 2), s // 3)
        pygame.draw.circle(surf, (150, 156, 172), (s // 2, s // 2), s // 3, 2)
        # 砲身（左向き）
        pygame.draw.rect(surf, (40, 42, 50), (0, s // 2 - 4, s // 2, 8), border_radius=2)
        return surf

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)   # speed=0 のためスクロール追従のみ
        if self._enemy_bullets is not None and self._player is not None:
            self._shoot_timer -= dt
            if self._shoot_timer <= 0:
                self._fire()
                self._shoot_timer = self._shoot_interval

    def _fire(self) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet
        sx, sy = self.rect.centerx, self.rect.centery
        dx = self._player.sx - sx
        dy = self._player.sy - sy
        d  = math.hypot(dx, dy) or 1
        self._enemy_bullets.add(
            EnemyBullet(sx, sy, (dx / d) * _BULLET_SPEED, (dy / d) * _BULLET_SPEED)
        )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.6)
