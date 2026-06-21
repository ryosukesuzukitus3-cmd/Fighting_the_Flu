from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_HEIGHT
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy
from src.entities.terrain_query import iter_collidable_terrain

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player

_STATS = enemy_stats("EnemyCrawler")
_FOOT_OFFSET = 18.0
_BULLET_SPEED = 230.0
_BASE_INTERVAL = 1.75
_ENH_INTERVAL = 1.15

# 登坂チューニング
_GROUND_TOL = 14.0        # 障害物が壁面に接地しているとみなす許容(px)
_CLIMB_SPEED = 150.0      # 登坂中の縦移動上限(px/s)
_CLIMB_X_FACTOR = 0.4     # 登坂中の水平前進係数(<1で斜めに駆け上がる)
_DESCEND_EASE = 16.0      # 平坦・下りでの追従の速さ
_STEP_TOL = 4.0           # 登り判定の閾値(px)
_CLIMB_CAP_MARGIN = 8.0   # 通路中央からさらに残す余白(px)


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

    def _wall_surface_y(self, world_x: float, surface: str) -> float | None:
        """走行レール（side を持つ TerrainStrip）の壁面 y。gap は None。

        side を持たない単体 Terrain（血栓ゲート/砲台土台などの障害物）は
        レール候補から除外する（PR #38 と同じ規約）。
        """
        if self._terrain is None:
            return None
        candidates: list[float] = []
        for ter in iter_collidable_terrain(self._terrain):
            side = getattr(ter, "side", "")
            if not side:
                continue
            left = float(getattr(ter, "world_x", 0.0))
            if not (left <= world_x <= left + ter.rect.width):
                continue
            if surface == "bottom" and side == "bottom":
                candidates.append(float(getattr(ter, "surface_y", ter.rect.top)))
            elif surface == "top" and side == "top":
                candidates.append(float(getattr(ter, "surface_y", ter.rect.bottom)))
        if not candidates:
            return None
        return min(candidates) if surface == "bottom" else max(candidates)

    def _passage_mid(self, world_x: float) -> float:
        """通路中央の y（登坂の頭打ち基準）。片側欠落時は画面中央にフォールバック。"""
        top = self._wall_surface_y(world_x, "top")
        bot = self._wall_surface_y(world_x, "bottom")
        if top is None or bot is None:
            return SCREEN_HEIGHT / 2.0
        return (top + bot) / 2.0

    def _walk_surface_y(self, world_x: float) -> float | None:
        """クローラーが乗るべき y。レール面＋接地障害物を合成し通路中央で頭打ち。"""
        wall = self._wall_surface_y(world_x, self._surface)
        if wall is None:
            return None
        best = wall
        for ter in iter_collidable_terrain(self._terrain):
            if getattr(ter, "side", ""):     # レール（strip）は除外
                continue
            left = float(getattr(ter, "world_x", 0.0))
            if not (left <= world_x <= left + ter.rect.width):
                continue
            top = float(getattr(ter, "y", ter.rect.top))
            bot = top + ter.rect.height
            if self._surface == "bottom":
                # 床に接地し、床面より上へ立ち上がる障害物だけ乗る（上面=top）
                if bot >= wall - _GROUND_TOL and top < wall:
                    best = min(best, top)
            else:
                # 天井に接地し、天井面より下へ垂れ下がる障害物だけ乗る（下面=bot）
                if top <= wall + _GROUND_TOL and bot > wall:
                    best = max(best, bot)
        # 通路中央で頭打ち（反対側の壁に張り付かない）
        cap = self._passage_mid(world_x)
        if self._surface == "bottom":
            best = max(best, cap + _CLIMB_CAP_MARGIN)
        else:
            best = min(best, cap - _CLIMB_CAP_MARGIN)
        return best

    def _move(self, dt: float) -> None:
        desired_x = self.world_x - self.speed * dt
        tgt = self._walk_surface_y(desired_x)
        if tgt is None:
            self.world_x = desired_x
            self._lost_surface_timer += dt
            drift = 45.0 if self._surface == "top" else -45.0
            self.world_y += drift * dt
            return
        self._lost_surface_timer = 0.0
        target_center = tgt - _FOOT_OFFSET if self._surface == "bottom" else tgt + _FOOT_OFFSET
        dy = target_center - self.world_y
        if abs(dy) > _STEP_TOL:
            # 段差（障害物の面）。縦は登坂速度で頭打ち、水平を絞って斜めに上り下り。
            # 上り・下りを同じ速度域に揃え、裏面で一気に落ちる不自然さを防ぐ。
            step = max(-_CLIMB_SPEED * dt, min(_CLIMB_SPEED * dt, dy))
            self.world_y += step
            self.world_x -= self.speed * dt * _CLIMB_X_FACTOR
        else:
            # ほぼ平坦。通常前進しつつレール面へ滑らかに追従。
            self.world_x = desired_x
            self.world_y += dy * min(1.0, dt * _DESCEND_EASE)

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
