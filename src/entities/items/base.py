from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.entities.player import Player

_DRIFT_SPEED = 40.0  # 世界座標での左移動速度 px/秒
_LIFETIME    = 12.0  # 秒


class Item(pygame.sprite.Sprite):
    color = (200, 200, 200)
    label = "?"

    def __init__(self, world_x: float, world_y: float) -> None:
        super().__init__()
        self.world_x  = world_x
        self.world_y  = world_y
        self._age: float = 0.0

        self.image = pygame.Surface((22, 22), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (11, 11), 11)
        font = pygame.font.SysFont("ms gothic", 11, bold=True) or pygame.font.SysFont(None, 11, bold=True)
        text = font.render(self.label, True, (20, 20, 20))
        self.image.blit(text, (11 - text.get_width() // 2, 11 - text.get_height() // 2))
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))

    def update(self, dt: float, camera: Camera) -> None:
        # magnetizing フラグが立っているとき、左ドリフトを停止
        # (game_scene 側がプレイヤー方向に移動させる)
        if not getattr(self, "_magnetizing", False):
            self.world_x -= _DRIFT_SPEED * dt
        self._age += dt
        sx = camera.to_screen_x(self.world_x)
        self.rect.center = (int(sx), int(self.world_y))
        if self._age >= _LIFETIME or camera.is_off_left(self.world_x, self.rect.width):
            self.kill()

    def apply(self, player: Player) -> None:
        """プレイヤーに効果を適用する（サブクラスで実装）"""
