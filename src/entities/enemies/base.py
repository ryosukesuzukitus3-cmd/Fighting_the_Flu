from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.camera import Camera

_GLOW_FRAMES = 12
_GLOW_FPS    = 6.0   # グロウアニメ速度 (frames/秒)


class Enemy(pygame.sprite.Sprite):
    def __init__(
        self,
        world_x: float,
        world_y: float,
        hp: int,
        speed: float,
        *,
        enhanced: bool = False,
    ) -> None:
        super().__init__()
        self.world_x  = world_x
        self.world_y  = world_y
        self.hp       = hp
        self.speed    = speed  # 左向き移動速度 px/秒
        self.enhanced = enhanced
        self.hit_flash_timer: float = 0.0

        self._glow_time:   float = 0.0
        self._glow_frames: list  = []
        self._flash_base_image: pygame.Surface | None = None

        # サブクラスで上書きする
        self.image = pygame.Surface((40, 40))
        self.image.fill((200, 50, 50))
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))

    def _init_glow(self) -> None:
        """強化個体の赤グロウフレームを事前生成。サブクラス __init__ 末尾で呼ぶ。"""
        self._flash_base_image = self.image
        if not self.enhanced:
            return
        bw, bh   = self.image.get_width(), self.image.get_height()
        pad      = 9
        gw, gh   = bw + pad * 2, bh + pad * 2
        base_img = self.image
        self._glow_frames = []
        for i in range(_GLOW_FRAMES):
            t    = 2 * math.pi * i / _GLOW_FRAMES
            a    = int(110 + 90 * math.sin(t))
            surf = pygame.Surface((gw, gh), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (255, 30, 30, a), (0, 0, gw, gh))
            pygame.draw.ellipse(surf, (255, 90, 90, min(255, a + 50) // 2),
                                (pad // 2, pad // 2, bw + pad, bh + pad))
            surf.blit(base_img, (pad, pad))
            self._glow_frames.append(surf)
        cx, cy     = self.rect.center
        self.image = self._glow_frames[0]
        self.rect  = self.image.get_rect(center=(cx, cy))

    def _move(self, dt: float) -> None:
        self.world_x -= self.speed * dt

    def _place_on_screen(self, sx: float, dt: float) -> None:
        if self.hit_flash_timer > 0:
            self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)
        if self.enhanced and self._glow_frames:
            self._glow_time += dt
            fi         = int(self._glow_time * _GLOW_FPS) % _GLOW_FRAMES
            base_image = self._glow_frames[fi]
        else:
            base_image = self._flash_base_image or self.image
            self._flash_base_image = base_image
        if self.hit_flash_timer > 0:
            img = base_image.copy()
            img.fill((175, 175, 175), special_flags=pygame.BLEND_RGB_ADD)
            self.image = img
        else:
            self.image = base_image
        self.rect = self.image.get_rect(center=(int(sx), int(self.world_y)))

    def update(self, dt: float, camera: Camera) -> None:
        self._move(dt)
        self._place_on_screen(camera.to_screen_x(self.world_x), dt)

    def take_damage(self, amount: int) -> bool:
        """ダメージを受ける。死亡したら True を返す"""
        self.hit_flash_timer = 0.08
        self.hp -= amount
        return self.hp <= 0

    def is_off_left(self, camera: Camera) -> bool:
        return camera.is_off_left(self.world_x, self.rect.width)
