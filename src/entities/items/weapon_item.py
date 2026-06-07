from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame
from src.entities.items.base import Item

if TYPE_CHECKING:
    from src.entities.player import Player
    from src.core.camera import Camera

_PULSE_FREQ = 3.5   # Hz
_GLOW_MAX   = 18    # グロウ半径px


class WeaponItem(Item):
    color = (255, 220, 40)
    label = "W"

    def update(self, dt: float, camera: "Camera") -> None:
        super().update(dt, camera)
        # 毎フレーム image を再生成してパルスグロウを描画
        t     = self._age
        pulse = 0.5 + 0.5 * math.sin(t * _PULSE_FREQ * math.pi * 2)
        glow_r = int(11 + _GLOW_MAX * pulse)
        size   = glow_r * 2 + 6
        img    = pygame.Surface((size, size), pygame.SRCALPHA)
        cx_    = size // 2

        # 外側グロウ（半透明オレンジ）
        glow_alpha = int(60 + 80 * pulse)
        glow_surf  = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 200, 0, glow_alpha), (cx_, cx_), glow_r)
        img.blit(glow_surf, (0, 0))

        # 本体円
        pygame.draw.circle(img, self.color, (cx_, cx_), 11)

        # ラベル
        font = pygame.font.SysFont("ms gothic", 11, bold=True)
        text = font.render(self.label, True, (20, 20, 20))
        img.blit(text, (cx_ - text.get_width() // 2, cx_ - text.get_height() // 2))

        old_center   = self.rect.center
        self.image   = img
        self.rect    = self.image.get_rect(center=old_center)

    def apply(self, player: Player) -> None:
        player.weapon.upgrade("weapon_main")
