import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.core.balance import PLAYER_DMG_BULLET


class EnemyBullet(pygame.sprite.Sprite):
    """スクリーン座標で動作する敵の弾"""

    def __init__(
        self,
        sx: float,
        sy: float,
        vx: float,
        vy: float,
        damage: int = PLAYER_DMG_BULLET,
        *,
        radius: int = 5,
        size: tuple[int, int] | None = None,
        color: tuple[int, int, int] = (255, 60, 60),
        lifetime: float | None = None,
        terrain_passthrough: bool = False,
        warning_only: bool = False,
        fade_shrink: bool = False,
    ) -> None:
        super().__init__()
        self.sx     = sx
        self.sy     = sy
        self.vx     = vx
        self.vy     = vy
        self.damage = damage
        self.lifetime = lifetime
        self.terrain_passthrough = terrain_passthrough
        self.warning_only = warning_only
        self.fade_shrink = fade_shrink
        self._max_lifetime = lifetime

        if size is None:
            d = max(2, radius * 2)
            self.image = pygame.Surface((d, d), pygame.SRCALPHA)
            pygame.draw.circle(self.image, color, (radius, radius), radius)
        else:
            w, h = size
            self.image = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(self.image, color, (0, 0, w, h), border_radius=max(2, min(w, h) // 4))
        self._base_image = self.image.copy()
        self.rect = self.image.get_rect(center=(int(sx), int(sy)))

    def update(self, dt: float) -> None:
        if self.lifetime is not None:
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.kill()
                return
            if self.fade_shrink and self._max_lifetime:
                self._apply_fade_shrink()
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self.rect.center = (int(self.sx), int(self.sy))

    def is_off_screen(self) -> bool:
        return (self.sx < -20 or self.sx > SCREEN_WIDTH + 20
                or self.sy < -20 or self.sy > SCREEN_HEIGHT + 20)

    def _apply_fade_shrink(self) -> None:
        ratio = max(0.0, min(1.0, self.lifetime / self._max_lifetime))
        w, h = self._base_image.get_size()
        new_h = max(2, int(h * (0.18 + ratio * 0.82)))
        image = pygame.transform.smoothscale(self._base_image, (w, new_h))
        image.set_alpha(int(255 * ratio))
        center = self.rect.center
        self.image = image
        self.rect = self.image.get_rect(center=center)
