from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from src.core.constants import SCREEN_WIDTH
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player

_CHARGE_SPEED   = 520.0
_APPROACH_TIME  = 0.9   # 秒：突進準備までの助走時間
_WINDUP_TIME    = 0.55  # 秒：チャージ（充電球＋かすかな予告線）を見せてから突進

_BEAM_FADE_TIME = 0.85  # 秒：発射継続。最後の _BEAM_TAPER 秒で徐々に細くなって消える
_BEAM_TAPER     = 0.40

_FIRE_SHAKE     = 4.5    # 発射時の画面シェイク強度

_ENH_CHARGE   = 650.0
_STATS        = enemy_stats("EnemyBroly")


class EnemyBroly(Enemy):
    def __init__(self, game: Game, world_x: float, world_y: float,
                 target_y: float | None = None,
                 enemy_bullets: pygame.sprite.Group | None = None,
                 player: "Player | None" = None,
                 *, enhanced: bool = False) -> None:
        hp       = _STATS.enhanced_hp    if enhanced else _STATS.base_hp
        approach = _STATS.enhanced_speed if enhanced else _STATS.base_speed
        super().__init__(world_x, world_y, hp=hp, speed=approach, enhanced=enhanced)
        self._game = game
        self._enemy_bullets = enemy_bullets
        self._player = player
        self._charge_speed = _ENH_CHARGE if enhanced else _CHARGE_SPEED
        raw        = game.resources.image("graphic/enemy_ブロリー.png")
        w, h       = raw.get_width(), raw.get_height()
        self.image = pygame.transform.smoothscale(raw, (int(w * 0.70), int(h * 0.70)))
        self.rect  = self.image.get_rect(center=(int(world_x), int(world_y)))
        self._target_y: float = target_y if target_y is not None else world_y
        self._state: str = "approach"
        self._timer: float = 0.0
        self._vy:    float = 0.0
        self._warning_fired = False
        self._beam_fired = False
        self._shock_fired = False
        self._camera: "Camera | None" = None
        self._init_glow()

    def update(self, dt: float, camera: "Camera") -> None:
        # 発射時の画面シェイク用にカメラを保持してから通常更新へ。
        self._camera = camera
        super().update(dt, camera)

    def _move(self, dt: float) -> None:
        self._timer += dt
        if self._state == "approach":
            self.world_x -= self.speed * dt
            if self._player is not None:
                self._target_y = float(self._player.sy)
            self.world_y += (self._target_y - self.world_y) * min(1.0, dt * 2.2)
            if self._timer >= _APPROACH_TIME:
                self._state = "windup"
                self._timer = 0.0
                self._fire_warning()
        elif self._state == "windup":
            self.world_x -= self.speed * 0.22 * dt
            if self._player is not None:
                self._target_y = float(self._player.sy)
            self.world_y += (self._target_y - self.world_y) * min(1.0, dt * 6.5)
            if self._timer >= _WINDUP_TIME:
                self._state = "charge"
                self._timer = 0.0
                dy = self._target_y - self.world_y
                d = abs(dy) if abs(dy) > 1 else 1
                self._vy = (dy / d) * (215.0 if self.enhanced else 170.0)
                self._fire_charge_beam()
                self._fire_shock()
        elif self._state == "charge":
            self.world_x -= self._charge_speed * dt
            self.world_y += self._vy * dt

    def _fire_warning(self) -> None:
        if self._enemy_bullets is None or self._warning_fired:
            return
        from src.entities.bullets.enemy_bullet import EnemyBullet
        from src.entities.bullets.laser_fx import MOB_PALETTE, LaserChargeOrb

        self._warning_fired = True
        # かすかな予告線（発射ラインの位置だけそっと示す）。
        beam = EnemyBullet(
            SCREEN_WIDTH / 2,
            self._target_y,
            0.0,
            0.0,
            size=(SCREEN_WIDTH + 76, 24),
            color=(255, 70, 70),
            lifetime=_WINDUP_TIME,
            terrain_passthrough=True,
            warning_only=True,
        )
        self._paint_warning_beam(beam.image)
        self._enemy_bullets.add(beam)
        # 銃口で充電球を育てる（＝発射前のチャージ演出）。
        self._enemy_bullets.add(LaserChargeOrb(self, _WINDUP_TIME, MOB_PALETTE))
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.3)

    def _paint_warning_beam(self, surf: pygame.Surface) -> None:
        surf.fill((0, 0, 0, 0))
        w, h = surf.get_size()
        cy = h // 2
        # 薄い赤グロー＋細い芯線のみ。視認できるが圧の弱いテレグラフにする。
        pygame.draw.rect(surf, (255, 40, 30, 40), (0, cy - 8, w, 16), border_radius=8)
        pygame.draw.rect(surf, (255, 90, 60, 70), (0, cy - 3, w, 6), border_radius=3)
        pygame.draw.line(surf, (255, 210, 170, 120), (0, cy), (w, cy), 1)

    def _fire_charge_beam(self) -> None:
        if self._enemy_bullets is None or self._beam_fired:
            return
        from src.entities.bullets.laser_fx import (
            MOB_PALETTE,
            LaserBeamSprite,
            LaserMuzzleFlash,
        )

        self._beam_fired = True
        # 太い本体ビーム。warning_only＝当たり判定は突進本体が担う（見た目専用）。
        # 立ち上がりで一気に展開し、最後の _BEAM_TAPER 秒で徐々に細くなって消える。
        beam = LaserBeamSprite(
            SCREEN_WIDTH / 2,
            self.world_y,
            SCREEN_WIDTH + 84,
            48,
            palette=MOB_PALETTE,
            lifetime=_BEAM_FADE_TIME,
            warning_only=True,
            taper_time=_BEAM_TAPER,
        )
        self._enemy_bullets.add(beam)
        # 発射の瞬間: 銃口フラッシュ＋画面シェイク。
        mx = self.rect.centerx - self.rect.width * 0.30
        self._enemy_bullets.add(LaserMuzzleFlash(mx, self.world_y, MOB_PALETTE))
        if self._camera is not None:
            self._camera.shake(_FIRE_SHAKE)

    def _fire_shock(self) -> None:
        if self._enemy_bullets is None or self._shock_fired:
            return
        from src.entities.bullets.enemy_bullet import EnemyBullet

        self._shock_fired = True
        sx, sy = self.rect.center
        for off in (-0.32, 0.32):
            self._enemy_bullets.add(
                EnemyBullet(
                    sx,
                    sy,
                    -math.cos(off) * 280.0,
                    math.sin(off) * 280.0,
                    radius=6,
                    color=(255, 170, 65),
                )
            )
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.5)
