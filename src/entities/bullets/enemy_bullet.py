import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.balance import PLAYER_DMG_BULLET


class EnemyBullet(pygame.sprite.Sprite):
    """スクリーン座標で動作する敵の弾"""

    def __init__(self, sx: float, sy: float, vx: float, vy: float,
                 damage: int = PLAYER_DMG_BULLET) -> None:
        super().__init__()
        self.sx     = sx
        self.sy     = sy
        self.vx     = vx
        self.vy     = vy
        self.damage = damage

        self.image = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 60, 60), (5, 5), 5)
        self.rect = self.image.get_rect(center=(int(sx), int(sy)))

    def update(self, dt: float) -> None:
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self.rect.center = (int(self.sx), int(self.sy))

    def is_off_screen(self) -> bool:
        return (self.sx < -20 or self.sx > SCREEN_WIDTH + 20
                or self.sy < -20 or self.sy > SCREEN_HEIGHT + 20)
