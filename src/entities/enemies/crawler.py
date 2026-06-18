from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player

_STATS = enemy_stats("EnemyCrawler")
_FOOT_OFFSET = 18.0
_BULLET_SPEED = 230.0
_BASE_INTERVAL = 1.75
_ENH_INTERVAL = 1.15


class EnemyCrawler(Enemy):
    """地形表面を這いながら自機を狙い撃つ敵。"""

    def __init__(
        self,
        game: "Game",
        world_x: float,
        world_y: float,
        enemy_bullets: pygame.sprite.Group | None = None,
        player: "Player | None" = None,
        terrain: pygame.sprite.Group | None = None,
        *,
        surface: str = "bottom",
        enhanced: bool = False,
    ) -> None:
        hp = _STATS.enhanced_hp if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        self._terrain = terrain
        self._surface = "top" if surface == "top" else "bottom"
        self._shoot_interval = _ENH_INTERVAL if enhanced else _BASE_INTERVAL
        self._shoot_timer = self._shoot_interval * 0.55
        self._lost_surface_timer = 0.0
        self.image = self._make_sprite(self._surface)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    @staticmethod
    def _make_sprite(surface: str) -> pygame.Surface:
        w, h = 42, 30
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        body = pygame.Rect(5, 8, 32, 16)
        pygame.draw.rect(surf, (58, 82, 88), body, border_radius=5)
        pygame.draw.rect(surf, (128, 190, 180), body, 2, border_radius=5)
        pygame.draw.circle(surf, (38, 46, 50), (11, 25), 4)
        pygame.draw.circle(surf, (38, 46, 50), (31, 25), 4)
        pygame.draw.rect(surf, (34, 38, 44), (0, 13, 13, 5), border_radius=2)
        pygame.draw.circle(surf, (170, 255, 210), (30, 14), 3)
        if surface == "top":
            surf = pygame.transform.flip(surf, False, True)
        return surf

    def _surface_y_at(self, world_x: float) -> float | None:
        if self._terrain is None:
            return None
        candidates: list[float] = []
        for ter in self._terrain:
            left = float(getattr(ter, "world_x", 0.0))
            right = left + ter.rect.width
            if not (left <= world_x <= right):
                continue
            # 走行レールは通路を成す連続地形（side を持つ TerrainStrip）だけ。
            # side を持たない単体 Terrain（血栓ゲート/砲台土台などの障害物）は
            # 通路の中ほどに置かれるため、これに吸着すると天井クローラーが
            # 通路へ落下するなど動きが破綻する。レール候補から除外する。
            side = getattr(ter, "side", "")
            if self._surface == "bottom" and side == "bottom":
                candidates.append(float(getattr(ter, "surface_y", ter.rect.top)))
            elif self._surface == "top" and side == "top":
                candidates.append(float(getattr(ter, "surface_y", ter.rect.bottom)))
        if not candidates:
            return None
        return min(candidates) if self._surface == "bottom" else max(candidates)

    def _move(self, dt: float) -> None:
        self.world_x -= self.speed * dt
        sy = self._surface_y_at(self.world_x)
        if sy is None:
            self._lost_surface_timer += dt
            drift = 45.0 if self._surface == "top" else -45.0
            self.world_y += drift * dt
            return
        self._lost_surface_timer = 0.0
        target_y = sy - _FOOT_OFFSET if self._surface == "bottom" else sy + _FOOT_OFFSET
        self.world_y += (target_y - self.world_y) * min(1.0, dt * 16.0)

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        if self._enemy_bullets is not None and self._player is not None:
            self._shoot_timer -= dt
            if self._shoot_timer <= 0:
                self._fire()
                self._shoot_timer = self._shoot_interval

    def _fire(self) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet

        sx, sy = self.rect.center
        tx, ty = self._player.rect.center
        dx = tx - sx
        dy = ty - sy
        d = math.hypot(dx, dy) or 1.0
        self._enemy_bullets.add(
            EnemyBullet(sx, sy, (dx / d) * _BULLET_SPEED, (dy / d) * _BULLET_SPEED)
        )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.55)
