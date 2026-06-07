from __future__ import annotations
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_WIDTH

if TYPE_CHECKING:
    from src.core.camera import Camera


class Bullet(pygame.sprite.Sprite):
    def __init__(
        self,
        world_x: float,
        world_y: float,
        vx: float,
        vy: float,
        damage: int = 1,
    ) -> None:
        super().__init__()
        self.world_x = world_x
        self.world_y = world_y
        self.vx = vx
        self.vy = vy
        self.damage = damage

        # サブクラスで上書きする
        self.image = pygame.Surface((8, 4))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))

    def update(self, dt: float, camera: Camera) -> None:
        self.world_x += self.vx * dt
        self.world_y += self.vy * dt
        sx = camera.to_screen_x(self.world_x)
        self.rect.center = (int(sx), int(self.world_y))

    def is_off_screen(self, camera: Camera) -> bool:
        sx = camera.to_screen_x(self.world_x)
        return sx > SCREEN_WIDTH + 50 or sx < -50
