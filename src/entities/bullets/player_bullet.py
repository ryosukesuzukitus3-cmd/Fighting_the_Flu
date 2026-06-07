from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.entities.bullet import Bullet

if TYPE_CHECKING:
    from src.core.camera import Camera

_SPEED        = 600.0   # px/秒
_HOMING_SPEED = 350.0
_TURN_RATE    = 1.8     # 方向補正の強さ（1秒あたりの補間率）
_HOMING_TIME  = 1.2     # ホーミング有効時間（秒）


def _angle_velocity(speed: float, angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return speed * math.cos(rad), -speed * math.sin(rad)


class NormalBullet(Bullet):
    def __init__(self, world_x: float, world_y: float) -> None:
        vx, vy = _angle_velocity(_SPEED, 0)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=1)
        self.image = pygame.Surface((14, 5), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (255, 240, 80), (0, 0, 14, 5), border_radius=2)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))


class WideBullet(Bullet):
    def __init__(self, world_x: float, world_y: float, angle: float = 0) -> None:
        vx, vy = _angle_velocity(_SPEED * 0.9, angle)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=1)
        self.image = pygame.Surface((12, 4), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (100, 200, 255), (0, 0, 12, 4), border_radius=2)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))


class PierceBullet(Bullet):
    _base_image: pygame.Surface | None = None  # クラス共有キャッシュ

    def __init__(self, world_x: float, world_y: float, angle: float = 0, game=None) -> None:
        vx, vy = _angle_velocity(_SPEED * 0.85, angle)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=2)

        if game is not None and PierceBullet._base_image is None:
            raw = game.resources.image("graphic/bullet.png")
            PierceBullet._base_image = pygame.transform.smoothscale(raw, (28, 11))

        if PierceBullet._base_image is not None:
            orig = PierceBullet._base_image
        else:
            orig = pygame.Surface((16, 6), pygame.SRCALPHA)
            pygame.draw.rect(orig, (180, 80, 255), (0, 0, 16, 6), border_radius=3)

        self.image = pygame.transform.rotate(orig, angle) if angle != 0 else orig
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))


class LaserBullet(Bullet):
    def __init__(self, world_x: float, world_y: float) -> None:
        super().__init__(world_x, world_y, vx=_SPEED * 1.5, vy=0.0, damage=2)
        self.image = pygame.Surface((30, 5), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (80, 255, 255), (0, 0, 30, 5), border_radius=2)
        # コア（白いハイライト）
        pygame.draw.rect(self.image, (200, 255, 255), (2, 1, 26, 3), border_radius=1)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))


class KaronaruBullet(Bullet):
    """カロナール先輩の微解熱弾。damage=1 の緑直進弾。"""

    def __init__(self, world_x: float, world_y: float) -> None:
        vx, vy = _angle_velocity(_SPEED * 0.72, 0)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=1)
        self.image = pygame.Surface((9, 4), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (100, 230, 130), (0, 0, 9, 4), border_radius=2)
        pygame.draw.rect(self.image, (200, 255, 210), (1, 1, 6, 2), border_radius=1)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))


class KaronaruMaxBullet(Bullet):
    """カロナール先輩・薬効最大の解熱貫通弾。damage=3 の白金高速弾。"""

    def __init__(self, world_x: float, world_y: float) -> None:
        vx, vy = _angle_velocity(_SPEED * 1.1, 0)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=3)
        self.image = pygame.Surface((22, 8), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (255, 240, 180), (0, 0, 22, 8), border_radius=3)
        pygame.draw.rect(self.image, (255, 255, 255), (2, 2, 18, 4), border_radius=2)
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))


_TOKIN_SIZE = (26, 20)   # ゲーム内弾サイズ（画像が横長270×207のため横基準）


class HomingBullet(Bullet):
    _base_image: pygame.Surface | None = None  # クラス共有キャッシュ

    def __init__(
        self,
        world_x: float,
        world_y: float,
        enemies: pygame.sprite.Group,
        game=None,
        boss=None,
        init_angle: float = 0.0,   # 初期発射角度（度、上方向が正）
    ) -> None:
        rad = math.radians(init_angle)
        vx  = _HOMING_SPEED * math.cos(rad)
        vy  = -_HOMING_SPEED * math.sin(rad)
        super().__init__(world_x, world_y, vx=vx, vy=vy, damage=4)
        self._enemies     = enemies
        self._boss        = boss
        self._homing_left = _HOMING_TIME

        # と金画像をロード（初回のみ）
        if game is not None and HomingBullet._base_image is None:
            raw = game.resources.image("graphic/bullet_tokin_nobg.png")
            HomingBullet._base_image = pygame.transform.smoothscale(raw, _TOKIN_SIZE)

        if HomingBullet._base_image is not None:
            self._orig_image = HomingBullet._base_image
        else:
            # フォールバック: 従来のオレンジ円
            surf = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 120, 30), (6, 6), 6)
            self._orig_image = surf

        self.image = self._orig_image
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))

    def update(self, dt: float, camera: "Camera") -> None:
        if self._homing_left > 0:
            self._homing_left -= dt

            # ターゲット候補: 雑魚敵 + ボス（生存中）
            candidates: list = list(self._enemies.sprites())
            if self._boss is not None:
                candidates.append(self._boss)

            if candidates:
                # スクリーン座標で距離・方向を統一計算
                # （world座標とスクリーン座標の混在を避けるため rect.center を使用）
                my_x, my_y = self.rect.center
                nearest = min(
                    candidates,
                    key=lambda e: math.hypot(
                        e.rect.centerx - my_x, e.rect.centery - my_y
                    ),
                )
                dx = nearest.rect.centerx - my_x
                dy = nearest.rect.centery - my_y
                d  = math.hypot(dx, dy)
                if d > 0:
                    target_vx = (dx / d) * _HOMING_SPEED
                    target_vy = (dy / d) * _HOMING_SPEED
                    t = min(1.0, _TURN_RATE * dt)
                    self.vx += (target_vx - self.vx) * t
                    self.vy += (target_vy - self.vy) * t

        # 速度を常に _HOMING_SPEED に正規化（homing終了後の低速・残留を防ぐ）
        current_speed = math.hypot(self.vx, self.vy)
        if current_speed > 0:
            self.vx = (self.vx / current_speed) * _HOMING_SPEED
            self.vy = (self.vy / current_speed) * _HOMING_SPEED

        # 進行方向に合わせて画像を回転
        angle = math.degrees(math.atan2(-self.vy, self.vx))
        self.image = pygame.transform.rotate(self._orig_image, angle)
        old_center = self.rect.center
        self.rect  = self.image.get_rect(center=old_center)

        super().update(dt, camera)
