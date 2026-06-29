from __future__ import annotations

import math

import pygame

from src.entities.bullets.enemy_bullet import EnemyBullet


# 駒種ごとの軌道メモ（ラスボス藤井竜王の弾。boss.py から生成される）:
#   pawn   歩 : ノーマル直進（隊列で並んで進む。出現率が一番高い）
#   lance  香 : 高速で直進（香車は前へ突き抜ける）
#   silver 銀 : 軽い狙いをつけた直進
#   gold   金 : やや遅いが大きい直進
#   knight 桂 : 細かいジグザグ（桂馬らしい跳ね）
#   bishop 角 : 45°の斜めジグザグ（Form2 で解禁）
#   rook   飛 : 大型・高速の直進（Form2 で解禁）
#   dragon 龍 : プレイヤーを追尾する（Form2 で解禁・成り駒）
_STRAIGHT_MULT = {
    "pawn":   1.0,
    "lance":  1.7,
    "silver": 1.0,
    "gold":   0.82,
    "rook":   1.5,
}


class ShogiBullet(EnemyBullet):
    """将棋駒の弾。駒種(kind)ごとに違う軌道で進み、毎フレーム進行方向へ向きを回す。

    `base_surface` は「上向き」に描かれた駒（五角形＋文字）。素のままだと上を
    向いたまま横へ滑って不自然なので、速度ベクトルの向きへ回転させて「駒が
    正面に進む」ように見せる。ジグザグ・追尾系は速度が変わるたびに回し直す。
    """

    def __init__(
        self,
        sx: float,
        sy: float,
        base_surface: pygame.Surface,
        *,
        kind: str,
        speed: float,
        forward: tuple[float, float] = (-1.0, 0.0),
        damage: int = 14,
        lifetime: float | None = 4.6,
        target=None,
    ) -> None:
        # EnemyBullet の矩形画像生成は使わず、駒サーフェスを基準画像にする。
        super().__init__(sx, sy, 0.0, 0.0, damage,
                         size=base_surface.get_size(), lifetime=lifetime)
        self.kind = kind
        self._piece_base = base_surface
        self._target = target
        f = math.hypot(*forward) or 1.0
        self._fwd = (forward[0] / f, forward[1] / f)
        self._spd = speed
        self._t = 0.0
        self._rot_deg: float | None = None
        self._update_velocity(0.0)
        self._face_velocity()

    # ── 駒種ごとの速度 ────────────────────────────────────────────
    def _update_velocity(self, dt: float) -> None:
        k = self.kind
        fx, fy = self._fwd
        s = self._spd
        if k == "bishop":
            # 45° 斜めジグザグ（0.5秒ごとに上下を切り替える）
            sign = 1.0 if int(self._t / 0.5) % 2 == 0 else -1.0
            self.vx = fx * s * 0.8
            self.vy = sign * s * 0.84
        elif k == "knight":
            # 細かいジグザグ（前進しつつ上下に小さく跳ねる）
            self.vx = fx * s * 1.05
            self.vy = math.sin(self._t * 9.0) * s * 0.9
        elif k == "dragon":
            self._home(dt, max_speed=s * 1.2, turn=3.4)
        else:
            mult = _STRAIGHT_MULT.get(k, 1.0)
            self.vx = fx * s * mult
            self.vy = fy * s * mult

    def _home(self, dt: float, max_speed: float, turn: float) -> None:
        target = self._target
        if target is None:
            self.vx = self._fwd[0] * max_speed
            self.vy = self._fwd[1] * max_speed
            return
        dx = float(getattr(target, "sx", self.sx)) - self.sx
        dy = float(getattr(target, "sy", self.sy)) - self.sy
        d = math.hypot(dx, dy) or 1.0
        desired_x = dx / d * max_speed
        desired_y = dy / d * max_speed
        blend = min(1.0, turn * dt)
        self.vx += (desired_x - self.vx) * blend
        self.vy += (desired_y - self.vy) * blend

    # ── 進行方向へ回転 ────────────────────────────────────────────
    def _face_velocity(self) -> None:
        if self.vx == 0.0 and self.vy == 0.0:
            return
        # base は上向き(0,-1)。速度方向へ向くよう回す（pygame は反時計回りが正）。
        deg = -90.0 - math.degrees(math.atan2(self.vy, self.vx))
        if self._rot_deg is not None and abs(deg - self._rot_deg) < 2.0:
            return
        self._rot_deg = deg
        center = self.rect.center
        self.image = pygame.transform.rotate(self._piece_base, deg)
        self.rect = self.image.get_rect(center=center)

    # ── 更新（直進弾と同じ寿命処理＋駒の挙動）─────────────────────
    def update(self, dt: float) -> None:
        if self.lifetime is not None:
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.kill()
                return
        self._t += dt
        self._update_velocity(dt)
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self._face_velocity()
        self.rect.center = (int(self.sx), int(self.sy))


class ThrownBoardBullet(EnemyBullet):
    """投げつけられる将棋盤（Form3 投了王の「ちゃぶ台返し」）。回転しながら飛ぶ大型弾。"""

    def __init__(
        self,
        sx: float,
        sy: float,
        base_surface: pygame.Surface,
        *,
        vx: float,
        vy: float,
        spin: float = 200.0,
        gravity: float = 0.0,
        damage: int = 20,
        lifetime: float | None = 5.0,
    ) -> None:
        super().__init__(sx, sy, vx, vy, damage,
                         size=base_surface.get_size(), lifetime=lifetime,
                         terrain_passthrough=True)
        self._board_base = base_surface
        self._spin = spin
        self._gravity = gravity
        self._angle = 0.0

    def update(self, dt: float) -> None:
        if self.lifetime is not None:
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.kill()
                return
        self.vy += self._gravity * dt
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self._angle = (self._angle + self._spin * dt) % 360.0
        center = (int(self.sx), int(self.sy))
        self.image = pygame.transform.rotate(self._board_base, self._angle)
        self.rect = self.image.get_rect(center=center)
