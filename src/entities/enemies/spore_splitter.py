from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING

import pygame

from src.core.constants import SCREEN_HEIGHT
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game

_SPLITTER_STATS = enemy_stats("EnemySporeSplitter")
_POD_STATS = enemy_stats("EnemySporePod")


def _pod_sprite(seed: int, enhanced: bool) -> pygame.Surface:
    rng = random.Random(seed)
    size = 22
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    base = (214, 86, 22) if not enhanced else (248, 110, 42)
    dark = (48, 22, 52)
    hi = (255, 196, 92)
    pts = []
    for i in range(8):
        a = math.tau * i / 8.0
        r = rng.choice((8, 10, 11))
        pts.append((int(size / 2 + math.cos(a) * r), int(size / 2 + math.sin(a) * r)))
    pygame.draw.polygon(surf, dark, pts)
    inner = [(int(size / 2 + (x - size / 2) * 0.72), int(size / 2 + (y - size / 2) * 0.72)) for x, y in pts]
    pygame.draw.polygon(surf, base, inner)
    pygame.draw.line(surf, dark, (7, 6), (15, 16), 3)
    pygame.draw.circle(surf, hi, (8, 8), 2)
    return surf


class EnemySporePod(Enemy):
    """分裂後に慣性で飛ぶ小型胞子。"""

    def __init__(
        self,
        game: "Game",
        world_x: float,
        world_y: float,
        vx: float = -150.0,
        vy: float = 0.0,
        *,
        enhanced: bool = False,
        seed: int = 1,
    ) -> None:
        hp = _POD_STATS.enhanced_hp if enhanced else _POD_STATS.base_hp
        super().__init__(world_x, world_y, hp=hp, speed=0.0, enhanced=enhanced)
        self._vx = vx
        self._vy = vy
        self._base_image = _pod_sprite(seed, enhanced)
        self.image = self._base_image
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self.drops_enabled = False
        self._init_glow()

    def _move(self, dt: float) -> None:
        self.world_x += self._vx * dt
        self.world_y = max(32.0, min(float(SCREEN_HEIGHT - 32), self.world_y + self._vy * dt))
        self._vy += 18.0 * dt

    def update(self, dt: float, camera: "Camera") -> None:
        self._move(dt)
        sx = camera.to_screen_x(self.world_x)
        self.rect.center = (int(sx), int(self.world_y))


class EnemySporeSplitter(Enemy):
    """倒すと複数の胞子ポッドに割れる硬めの雑魚敵。"""

    def __init__(self, game: "Game", world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp = _SPLITTER_STATS.enhanced_hp if enhanced else _SPLITTER_STATS.base_hp
        speed = _SPLITTER_STATS.enhanced_speed if enhanced else _SPLITTER_STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        raw = game.resources.image("graphic/enemy_spore_splitter.png")
        self.image = pygame.transform.scale(raw, raw.get_size())
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._base_y = world_y
        self._time = random.uniform(0.0, math.tau)
        self._seed = int(world_x * 11 + world_y * 17)
        self._init_glow()

    def _move(self, dt: float) -> None:
        self._time += dt
        self.world_x -= self.speed * dt
        self.world_y = max(
            42.0,
            min(float(SCREEN_HEIGHT - 42), self._base_y + math.sin(self._time * 1.7) * 22.0),
        )

    def split(self, game: "Game") -> list[EnemySporePod]:
        pods: list[EnemySporePod] = []
        count = 5 if self.enhanced else 4
        spread = (-62, -26, 22, 58, 92) if self.enhanced else (-54, -18, 24, 58)
        for i, deg in enumerate(spread[:count]):
            a = math.radians(180 + deg)
            speed = random.uniform(132.0, 215.0)
            pods.append(
                EnemySporePod(
                    game,
                    self.world_x + random.uniform(-12.0, 12.0),
                    self.world_y + random.uniform(-12.0, 12.0),
                    math.cos(a) * speed,
                    math.sin(a) * speed,
                    enhanced=self.enhanced,
                    seed=self._seed + i * 37,
                )
            )
        return pods
