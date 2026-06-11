from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game

_LARGE_STATS = enemy_stats("EnemyDebrisLarge")
_SHARD_STATS = enemy_stats("EnemyDebrisShard")


def _rock_sprite(size: int, seed: int, base: tuple[int, int, int]) -> pygame.Surface:
    rng = random.Random(seed)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    pts = []
    for i in range(14):
        a = math.tau * i / 14.0
        r = rng.uniform(size * 0.33, size * 0.48)
        pts.append((int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)))
    edge = tuple(min(255, c + 46) for c in base)
    dark = tuple(max(0, c - 34) for c in base)
    pygame.draw.polygon(surf, base, pts)
    pygame.draw.lines(surf, edge, True, pts, max(2, size // 26))
    for _ in range(max(5, size // 6)):
        x = rng.randint(size // 5, size * 4 // 5)
        y = rng.randint(size // 5, size * 4 // 5)
        rr = rng.randint(2, max(3, size // 11))
        pygame.draw.circle(surf, dark, (x, y), rr)
    for _ in range(max(3, size // 12)):
        x = rng.randint(size // 5, size * 4 // 5)
        y = rng.randint(size // 5, size * 4 // 5)
        pygame.draw.line(surf, edge, (x, y), (x + rng.randint(-10, 10), y + rng.randint(-8, 8)), 1)
    return surf


class EnemyDebrisShard(Enemy):
    """巨大デブリから割れて飛ぶ小デブリ。"""

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
        hp = _SHARD_STATS.enhanced_hp if enhanced else _SHARD_STATS.base_hp
        super().__init__(world_x, world_y, hp=hp, speed=0.0, enhanced=enhanced)
        self._vx = vx
        self._vy = vy
        self._angle = random.Random(seed).uniform(0.0, 360.0)
        self._spin = random.choice((-1.0, 1.0)) * random.uniform(150.0, 260.0)
        self._base_image = _rock_sprite(30, seed, (88, 88, 98))
        self.image = self._base_image
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    def _move(self, dt: float) -> None:
        self.world_x += self._vx * dt
        self.world_y += self._vy * dt
        self._vy += 8.0 * dt
        self._angle = (self._angle + self._spin * dt) % 360.0

    def update(self, dt: float, camera: "Camera") -> None:
        self._move(dt)
        img = pygame.transform.rotate(self._base_image, self._angle)
        sx = camera.to_screen_x(self.world_x)
        self.image = img
        self.rect = self.image.get_rect(center=(int(sx), int(self.world_y)))


class EnemyDebrisLarge(Enemy):
    """回転しながら迫り、破壊すると小デブリへ分裂する大型障害物。"""

    def __init__(self, game: "Game", world_x: float, world_y: float, *, enhanced: bool = False) -> None:
        hp = _LARGE_STATS.enhanced_hp if enhanced else _LARGE_STATS.base_hp
        speed = _LARGE_STATS.enhanced_speed if enhanced else _LARGE_STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._angle = 0.0
        self._spin = -72.0 if enhanced else -54.0
        self._bob_t = random.uniform(0.0, math.tau)
        self._base_y = world_y
        self._base_image = _rock_sprite(84, int(world_x) ^ int(world_y), (82, 80, 92))
        self.image = self._base_image
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    def _move(self, dt: float) -> None:
        self.world_x -= self.speed * dt
        self._bob_t += dt * 1.7
        self.world_y = self._base_y + math.sin(self._bob_t) * 28.0
        self._angle = (self._angle + self._spin * dt) % 360.0

    def update(self, dt: float, camera: "Camera") -> None:
        self._move(dt)
        img = pygame.transform.rotate(self._base_image, self._angle)
        sx = camera.to_screen_x(self.world_x)
        self.image = img
        self.rect = self.image.get_rect(center=(int(sx), int(self.world_y)))

    def split(self, game: "Game") -> list[EnemyDebrisShard]:
        shards: list[EnemyDebrisShard] = []
        for i, deg in enumerate((-55, -28, 0, 28, 55)):
            a = math.radians(180 + deg)
            speed = random.uniform(120.0, 210.0)
            shards.append(EnemyDebrisShard(
                game,
                self.world_x + random.uniform(-18, 18),
                self.world_y + random.uniform(-18, 18),
                math.cos(a) * speed,
                math.sin(a) * speed,
                seed=int(self.world_x * 17 + self.world_y * 13 + i * 97),
            ))
        return shards
