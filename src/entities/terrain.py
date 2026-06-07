"""地形（壁・障害物・デブリ）。ワールド座標で配置し、カメラスクロールで左へ流れる。

自機が接触するとダメージ。砲台（EnemyTurret）の設置足場としても用いる。
ステージごとに `kind` と配置を変えて特色を出す（宇宙=debris まばら / 岩石=wall・rock 多め）。
"""
from __future__ import annotations
import random
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.core.camera import Camera

# kind 別の基調色 (本体, 縁)
_KIND_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "wall":   ((70, 72, 82),  (110, 114, 128)),   # 金属/コンクリの壁
    "rock":   ((96, 78, 60),  (140, 116, 86)),    # 岩石
    "debris": ((84, 86, 96),  (130, 134, 150)),   # 宇宙デブリ
}


class Terrain(pygame.sprite.Sprite):
    """スクロールする地形ブロック（ワールド座標 world_x / 画面 y 固定）。"""

    def __init__(self, world_x: float, y: float, w: int, h: int, kind: str = "wall") -> None:
        super().__init__()
        self.world_x = float(world_x)
        self.y       = float(y)
        self.kind    = kind
        self.image   = self._make_surface(w, h, kind)
        self.rect    = self.image.get_rect(topleft=(int(world_x), int(y)))

    @staticmethod
    def _make_surface(w: int, h: int, kind: str) -> pygame.Surface:
        base, edge = _KIND_COLORS.get(kind, _KIND_COLORS["wall"])
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        radius = 8 if kind != "wall" else 3
        pygame.draw.rect(surf, base, (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(surf, edge, (0, 0, w, h), 2, border_radius=radius)
        # ざらつき（決定的擬似ランダムの斑点）
        rng = random.Random((w * 73856093) ^ (h * 19349663) ^ hash(kind))
        for _ in range(max(3, (w * h) // 900)):
            sx = rng.randint(2, max(2, w - 3))
            sy = rng.randint(2, max(2, h - 3))
            shade = tuple(max(0, c - 24) for c in base)
            pygame.draw.circle(surf, shade, (sx, sy), rng.randint(1, 3))
        return surf

    def update(self, dt: float, camera: "Camera") -> None:
        self.rect.topleft = (int(camera.to_screen_x(self.world_x)), int(self.y))

    def is_off_left(self, camera: "Camera") -> bool:
        return self.world_x + self.rect.width < camera.x
