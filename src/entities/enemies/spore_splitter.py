from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING

import pygame

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game

_SPLITTER_STATS = enemy_stats("EnemySporeSplitter")
_POD_STATS = enemy_stats("EnemySporePod")
_ANCHOR_SX = SCREEN_WIDTH - 162.0
_SCALE = 2.0   # 中ボスは約2倍に大型化
_MOVE_MODES = ("drift", "wide", "quiver")   # 縦移動のバリエーション（横はアンカー保持）


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
    """右前方に居座り、倒すと複数の胞子ポッドに割れる中ボス敵。

    大型（約2倍）。縦移動（drift/wide/quiver）を巡回しつつ、
    一定間隔で胞子弾をプレイヤーへ吐く。
    """

    def __init__(
        self,
        game: "Game",
        world_x: float,
        world_y: float,
        enemy_bullets: "pygame.sprite.Group | None" = None,
        player=None,
        *,
        enhanced: bool = False,
    ) -> None:
        hp = _SPLITTER_STATS.enhanced_hp if enhanced else _SPLITTER_STATS.base_hp
        speed = _SPLITTER_STATS.enhanced_speed if enhanced else _SPLITTER_STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        raw = game.resources.image("graphic/enemy_spore_splitter.png")
        w, h = raw.get_size()
        self.image = pygame.transform.scale(raw, (int(w * _SCALE), int(h * _SCALE)))
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._base_y = world_y
        self._time = random.uniform(0.0, math.tau)
        self._seed = int(world_x * 11 + world_y * 17)
        # 縦移動モード巡回
        self._move_idx = random.randrange(len(_MOVE_MODES))
        self._move_timer = random.uniform(4.0, 5.0)
        # 胞子弾の発射
        self._spit_interval = 2.4 if enhanced else 3.0
        self._spit_timer = self._spit_interval * random.uniform(0.5, 0.9)
        self._init_glow()

    @property
    def _move_mode(self) -> str:
        return _MOVE_MODES[self._move_idx]

    def _vertical_wave(self) -> float:
        t = self._time
        mode = self._move_mode
        if mode == "wide":
            return math.sin(t * 0.8) * 120.0
        if mode == "quiver":
            return math.sin(t * 5.0) * 26.0 + math.sin(t * 1.3) * 14.0
        return math.sin(t * 1.7) * 22.0   # drift

    def _move_vertical(self, dt: float) -> None:
        self._time += dt
        self._move_timer -= dt
        if self._move_timer <= 0.0:
            self._move_idx = (self._move_idx
                              + random.randint(1, len(_MOVE_MODES) - 1)) % len(_MOVE_MODES)
            self._move_timer = random.uniform(4.0, 5.0)
        target_y = max(42.0, min(float(SCREEN_HEIGHT - 42),
                                 self._base_y + self._vertical_wave()))
        self.world_y += (target_y - self.world_y) * min(1.0, dt * 3.5)

    def update(self, dt: float, camera: "Camera") -> None:
        self._move_vertical(dt)
        sx = camera.to_screen_x(self.world_x)
        target_sx = _ANCHOR_SX + math.sin(self._time * 1.15) * 12.0
        if sx > target_sx:
            sx = max(target_sx, sx - self.speed * dt)
        else:
            sx += (target_sx - sx) * min(1.0, dt * 4.5)
        self.world_x = camera.to_world_x(sx)
        self._place_on_screen(sx, dt)

        if self._enemy_bullets is None or self._player is None:
            return
        self._spit_timer -= dt
        if self._spit_timer <= 0.0:
            self._spit_timer = self._spit_interval
            self._spit_spores()

    def _spit_spores(self) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet
        sx, sy = self.rect.center
        base = math.atan2(self._player.sy - sy, self._player.sx - sx)
        count = 4 if self.enhanced else 3
        for i in range(count):
            off = (i - (count - 1) / 2.0) * 0.30
            a = base + off
            speed = random.uniform(140.0, 178.0)
            self._enemy_bullets.add(
                EnemyBullet(sx, sy, math.cos(a) * speed, math.sin(a) * speed,
                            radius=5, color=(236, 126, 48))
            )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.4)

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
