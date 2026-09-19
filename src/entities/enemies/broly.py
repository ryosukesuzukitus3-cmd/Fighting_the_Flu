from __future__ import annotations
from typing import TYPE_CHECKING
import math
import pygame
from src.core.registries import enemy_stats
from src.entities.enemies.base import Enemy
from src.core.sprite_art import fit_character_art

if TYPE_CHECKING:
    from src.core.camera import Camera
    from src.core.game import Game
    from src.entities.player import Player

_CHARGE_SPEED   = 520.0
_ENH_CHARGE     = 650.0
_APPROACH_TIME  = 0.9   # 秒：突進準備までの助走時間
_WINDUP_TIME    = 1.45  # 秒：射線を固定した予告。基本速度で上下に回避できる猶予
_FIRE_HOLD_TIME = 1.30  # 秒：停止して発射。ビームの寿命もこの長さに揃える
_BEAM_TAPER     = 0.48  # 秒：終端で徐々に細くなって消える
_BEAM_H         = 286   # ビーム画像の描画高さ（当たり判定は非透明画素）
_FIRE_SHAKE     = 4.5
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
        raw = game.resources.image("graphic/characters/broly.png")
        self.image = fit_character_art(raw, (56, 45))
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
            # Lock world_y where the warning began. Retain the latest target
            # only for the subsequent body charge, not for steering the cannon.
            if self._player is not None:
                self._target_y = float(self._player.sy)
            if self._timer >= _WINDUP_TIME:
                self._state = "charge"
                self._timer = 0.0
                dy = self._target_y - self.world_y
                d = abs(dy) if abs(dy) > 1 else 1
                self._vy = (dy / d) * (215.0 if self.enhanced else 170.0)
                self._fire_charge_beam()
                self._fire_shock()
                self._state = "fire"
        elif self._state == "fire":
            # Never slide during the visible cannon discharge.
            if self._timer >= _FIRE_HOLD_TIME:
                self._state = "charge"
                self._timer = 0.0
        elif self._state == "charge":
            self.world_x -= self._charge_speed * dt
            self.world_y += self._vy * dt

    def _muzzle_x(self) -> float:
        """銃口（ブロリーの左端寄り）のスクリーンX。レーザーはここから左へ伸びる。"""
        return self.rect.centerx - self.rect.width * 0.30

    def _fire_warning(self) -> None:
        if self._enemy_bullets is None or self._warning_fired:
            return
        from src.entities.bullets.laser_fx import (
            ZUNDA_PALETTE,
            LaserBeamSprite,
            zunda_charge_frames,
        )

        self._warning_fired = True
        # 固定した射線でチャージ相を表示。銃口のスクロール位置だけ追従する。
        # warning_only=True の予告は無害。高さ・中心Yは発射ビームと同じ。
        mx = self._muzzle_x()
        self._enemy_bullets.add(LaserBeamSprite(
            max(80, int(mx)) / 2, self.world_y, max(80, int(mx)), _BEAM_H,
            palette=ZUNDA_PALETTE, lifetime=_WINDUP_TIME, warning_only=True,
            frames=zunda_charge_frames(self._game.resources), frame_mode="progress",
            host=self, offset_ratio=-0.30,
        ))
        self._game.sound.play_se_alias("SE_ENEMY_SHOT", volume=0.3)

    def _fire_charge_beam(self) -> None:
        if self._enemy_bullets is None or self._beam_fired:
            return
        from src.entities.bullets.laser_fx import (
            ZUNDA_PALETTE,
            LaserBeamSprite,
            LaserMuzzleFlash,
            zunda_beam_frames,
        )

        self._beam_fired = True
        # 予告と同じ射線に有害なビームを発射（通常12・強化16ダメージ）。
        # 寿命進捗で本体→放電を1周し、終端でアルファが抜ける。
        mx = self._muzzle_x()
        width = max(80, int(mx))
        beam = LaserBeamSprite(
            width / 2,
            self.world_y,
            width,
            _BEAM_H,
            palette=ZUNDA_PALETTE,
            lifetime=_FIRE_HOLD_TIME,
            damage=16 if self.enhanced else 12,
            warning_only=False,
            taper_time=_BEAM_TAPER,
            frames=zunda_beam_frames(self._game.resources),
            frame_fps=11.0,
            frame_mode="progress",
        )
        self._enemy_bullets.add(beam)
        # 発射の瞬間: 銃口フラッシュ＋画面シェイク＋発射音。
        self._enemy_bullets.add(LaserMuzzleFlash(mx, self.world_y, ZUNDA_PALETTE, max_radius=64))
        self._game.sound.play_se_alias("SE_LASER_FIRE", volume=0.4)
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
