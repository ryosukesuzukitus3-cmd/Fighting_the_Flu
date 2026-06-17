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
    from src.entities.player import Player

_STATS = enemy_stats("EnemyCoughSprayer")
_BASE_INTERVAL = 1.55
_ENH_INTERVAL = 1.05
_BULLET_SPEED = 185.0
_FAN_BASE = (-0.26, 0.0, 0.26)
_FAN_ENH = (-0.38, -0.14, 0.14, 0.38)
_ANCHOR_SX = SCREEN_WIDTH - 178.0
_SCALE = 2.0   # 中ボスは約2倍に大型化

# 攻撃パターン（一定間隔で巡回し、移動と合わせて単調さを解消）
_PATTERNS = ("fan", "ring", "spiral", "burst")
# パターン別の発射間隔（base, enhanced）
_FIRE_INTERVAL = {
    "fan":    (_BASE_INTERVAL, _ENH_INTERVAL),
    "ring":   (1.85, 1.45),
    "spiral": (0.34, 0.26),
    "burst":  (0.42, 0.32),
}
# 移動モード（縦移動のバリエーション。横はアンカー保持）
_MOVE_MODES = ("hover", "sweep", "zigzag")


class EnemyCoughSprayer(Enemy):
    """画面右前方に居座り、咳のような弾を吐く中ボス敵。

    移動（hover/sweep/zigzag）と攻撃（fan/ring/spiral/burst）を時間で巡回し、
    大型（約2倍）で存在感のある中ボスとして振る舞う。
    """

    def __init__(
        self,
        game: "Game",
        world_x: float,
        world_y: float,
        enemy_bullets: pygame.sprite.Group | None = None,
        player: "Player | None" = None,
        *,
        enhanced: bool = False,
    ) -> None:
        hp = _STATS.enhanced_hp if enhanced else _STATS.base_hp
        speed = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=speed, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        self._origin_y = world_y
        self._time = random.uniform(0.0, math.tau)

        # 攻撃パターン巡回
        self._pattern_idx = random.randrange(len(_PATTERNS))
        self._pattern_timer = random.uniform(3.4, 4.4)
        self._spiral_angle = random.uniform(0.0, math.tau)
        self._shoot_timer = self._fire_interval() * 0.5

        # 移動モード巡回
        self._move_idx = random.randrange(len(_MOVE_MODES))
        self._move_timer = random.uniform(3.8, 4.8)

        raw = game.resources.image("graphic/enemy_cough_sprayer.png")
        w, h = raw.get_size()
        self.image = pygame.transform.scale(raw, (int(w * _SCALE), int(h * _SCALE)))
        self.rect = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._init_glow()

    # ── パターン管理 ─────────────────────────────────────────────
    @property
    def _pattern(self) -> str:
        return _PATTERNS[self._pattern_idx]

    @property
    def _move_mode(self) -> str:
        return _MOVE_MODES[self._move_idx]

    def _fire_interval(self) -> float:
        base, enh = _FIRE_INTERVAL[self._pattern]
        return enh if self.enhanced else base

    # ── 移動 ─────────────────────────────────────────────────────
    def _vertical_wave(self) -> float:
        t = self._time
        mode = self._move_mode
        if mode == "sweep":
            return math.sin(t * 0.9) * 150.0          # 広い縦パトロール
        if mode == "zigzag":
            return math.sin(t * 6.0) * 40.0 + math.sin(t * 2.0) * 16.0  # 細かい上下動
        return math.sin(t * 2.2) * 38.0 + math.sin(t * 5.1) * 10.0      # hover

    def _move_vertical(self, dt: float) -> None:
        self._time += dt
        self._move_timer -= dt
        if self._move_timer <= 0.0:
            self._move_idx = (self._move_idx
                              + random.randint(1, len(_MOVE_MODES) - 1)) % len(_MOVE_MODES)
            self._move_timer = random.uniform(3.8, 4.8)
        target_y = max(46.0, min(float(SCREEN_HEIGHT - 46),
                                 self._origin_y + self._vertical_wave()))
        # モード切替時の段差を防ぐためターゲットへ追従
        self.world_y += (target_y - self.world_y) * min(1.0, dt * 4.0)

    def update(self, dt: float, camera: "Camera") -> None:
        self._move_vertical(dt)
        sx = camera.to_screen_x(self.world_x)
        target_sx = _ANCHOR_SX + math.sin(self._time * 1.35) * 18.0
        if sx > target_sx:
            sx = max(target_sx, sx - self.speed * dt)
        else:
            sx += (target_sx - sx) * min(1.0, dt * 5.5)
        self.world_x = camera.to_world_x(sx)
        self._place_on_screen(sx, dt)

        if self._enemy_bullets is None or self._player is None:
            return
        self._pattern_timer -= dt
        if self._pattern_timer <= 0.0:
            self._pattern_idx = (self._pattern_idx + 1) % len(_PATTERNS)
            self._pattern_timer = random.uniform(3.4, 4.4)
            self._shoot_timer = min(self._shoot_timer, self._fire_interval())
        self._shoot_timer -= dt
        if self._shoot_timer <= 0.0:
            self._fire_current()
            self._shoot_timer = self._fire_interval()

    # ── 攻撃 ─────────────────────────────────────────────────────
    def _spawn(self, angle: float, speed: float = _BULLET_SPEED,
               color: tuple[int, int, int] = (115, 245, 210)) -> None:
        from src.entities.bullets.enemy_bullet import EnemyBullet
        sx, sy = self.rect.center
        self._enemy_bullets.add(
            EnemyBullet(sx, sy, math.cos(angle) * speed, math.sin(angle) * speed,
                        radius=4, color=color)
        )

    def _aim_angle(self) -> float:
        sx, sy = self.rect.center
        return math.atan2(self._player.sy - sy, self._player.sx - sx)

    def _fire_current(self) -> None:
        pattern = self._pattern
        if pattern == "ring":
            self._fire_ring()
        elif pattern == "spiral":
            self._fire_spiral()
        elif pattern == "burst":
            self._fire_burst()
        else:
            self._fire_fan()
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.42)

    def _fire_fan(self) -> None:
        base = self._aim_angle()
        for off in (_FAN_ENH if self.enhanced else _FAN_BASE):
            self._spawn(base + off)

    def _fire_ring(self) -> None:
        count = 14 if self.enhanced else 10
        phase = self._aim_angle()
        for i in range(count):
            self._spawn(phase + math.tau * i / count, speed=150.0)

    def _fire_spiral(self) -> None:
        arms = 3 if self.enhanced else 2
        for i in range(arms):
            self._spawn(self._spiral_angle + math.tau * i / arms, speed=168.0,
                        color=(150, 250, 200))
        self._spiral_angle += 0.42

    def _fire_burst(self) -> None:
        # プレイヤーへ向け、進行方向に対し垂直へ少しずらした3連弾
        from src.entities.bullets.enemy_bullet import EnemyBullet
        base = self._aim_angle()
        perp = base + math.pi / 2.0
        sx, sy = self.rect.center
        for k in (-1, 0, 1):
            ox = math.cos(perp) * 10.0 * k
            oy = math.sin(perp) * 10.0 * k
            self._enemy_bullets.add(
                EnemyBullet(sx + ox, sy + oy,
                            math.cos(base) * 230.0, math.sin(base) * 230.0,
                            radius=4, color=(120, 255, 235))
            )
