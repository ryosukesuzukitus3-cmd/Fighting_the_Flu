from __future__ import annotations
import random
from typing import TYPE_CHECKING
import pygame
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.game import Game
    from src.core.camera import Camera

_SIZE  = (76, 80)
_STATS = enemy_stats("EnemyBilly")

_SHAKE_DURATION = 0.35   # 被弾時震え時間（秒）
_SHAKE_AMOUNT   = 5      # 震れ幅 px


class EnemyBilly(Enemy):
    """ビリー・ヘリントン。HP 高く動き鈍い。被弾ごとにアｯー♂と震え。必ず W ドロップ。"""

    # クラスレベル画像キャッシュ
    _base_image: pygame.Surface | None = None

    def __init__(self, game: "Game", world_x: float, world_y: float) -> None:
        super().__init__(world_x, world_y, hp=_STATS.base_hp, speed=_STATS.base_speed)
        self._game = game

        if EnemyBilly._base_image is None:
            raw = game.resources.image("graphic/enemy_billy-herrington.jpg")
            EnemyBilly._base_image = pygame.transform.smoothscale(raw, _SIZE)

        self.image = EnemyBilly._base_image
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))

        self._shake_timer: float = 0.0

    # 確定 WeaponItem ドロップフラグ（game_scene 側で参照）
    force_drop: bool = True

    def take_damage(self, amount: int) -> bool:
        dead = super().take_damage(amount)
        if not dead:
            self._game.sound.play_se("music/se/アｯー♂.mp3", volume=0.9)
            self._shake_timer = _SHAKE_DURATION
        return dead

    def update(self, dt: float, camera: "Camera") -> None:
        self._shake_timer = max(0.0, self._shake_timer - dt)
        super().update(dt, camera)
        if self._shake_timer > 0:
            ox = random.randint(-_SHAKE_AMOUNT, _SHAKE_AMOUNT)
            oy = random.randint(-_SHAKE_AMOUNT, _SHAKE_AMOUNT)
            self.rect = self.rect.move(ox, oy)
