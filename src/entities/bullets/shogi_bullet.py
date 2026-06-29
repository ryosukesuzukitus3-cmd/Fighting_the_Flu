from __future__ import annotations

import math
import random

import pygame

from src.entities.bullets.enemy_bullet import EnemyBullet


# 駒種ごとの軌道メモ（ラスボス藤井竜王の弾。boss.py から生成される）:
#   pawn   歩 : ノーマル直進（隊列で並んで進む。出現率が一番高い）
#   lance  香 : 高速で直進（香車は前へ突き抜ける）
#   silver 銀 : 軽い狙いをつけた直進
#   gold   金 : やや遅いが大きい直進
#   knight 桂 : 細かいジグザグ（前進軸に直交して跳ねる）
#   bishop 角 : 45°の斜め一直線（一撃。Form2 で解禁）
#   rook   飛 : 大型・高速の直進（Form2 で解禁）
#   dragon 龍 : プレイヤーを追尾する（Form2 で解禁・成り駒）
# 軌道は前進ベクトル fwd に対して定義し、どの向きから来ても成立する（持ち駒打ち対応）。
_STRAIGHT_MULT = {
    "pawn":   1.0,
    "lance":  1.7,
    "silver": 1.0,
    "gold":   0.82,
    "rook":   1.5,
}

# 駒種ごとの耐久（撃墜に必要なダメージ量。自機弾は低ダメ高連射）。
PIECE_HP = {
    "pawn":   2,
    "lance":  3,
    "knight": 3,
    "silver": 4,
    "gold":   5,
    "bishop": 4,
    "rook":   7,
    "dragon": 9,
}

_SNAP_POP = 0.18   # 着駒の「ピシッ」スケール演出時間


class ShogiBullet(EnemyBullet):
    """将棋駒の弾。駒種(kind)ごとに違う軌道で進み、毎フレーム進行方向へ向きを回す。

    `base_surface` は「上向き」に描かれた駒（五角形＋文字）。素のままだと上を
    向いたまま横滑りして不自然なので、速度ベクトルの向きへ回転させて「駒が正面に
    進む」ように見せる。

    drop_target を渡すと「持ち駒打ち」モードになる: 指定マスへ任意の向きから
    飛来 → ピシッと着駒(snap) → 一拍置いてプレイヤー方向へ駒種の軌道で動き出す。
    撃墜可能（hp/take_damage）。
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
        lifetime: float | None = 5.0,
        target=None,
        hp: int | None = None,
        drop_target: tuple[float, float] | None = None,
        incoming_speed: float = 0.0,
        incoming_time: float = 0.55,
    ) -> None:
        super().__init__(sx, sy, 0.0, 0.0, damage,
                         size=base_surface.get_size(), lifetime=lifetime)
        self.kind = kind
        self._piece_base = base_surface
        self._target = target
        self._spd = speed
        self._t = 0.0
        self._rot_deg: float | None = None
        self._bishop_sign = random.choice((-1.0, 1.0))
        self._snap_anim = 0.0

        # 撃墜可能
        self.destructible = True
        self.hp = hp if hp is not None else PIECE_HP.get(kind, 3)

        if drop_target is not None:
            # 持ち駒打ち: まず指定マスへ飛来する。
            self._mode = "incoming"
            self._drop_target = drop_target
            self._incoming_time = incoming_time
            self._place_t = 0.22
            dx, dy = drop_target[0] - sx, drop_target[1] - sy
            d = math.hypot(dx, dy) or 1.0
            self.vx, self.vy = dx / d * incoming_speed, dy / d * incoming_speed
        else:
            self._mode = "active"
            self._drop_target = None
            f = math.hypot(*forward) or 1.0
            self._fwd = (forward[0] / f, forward[1] / f)
            self._update_velocity(0.0)
        self._face_velocity()

    # ── 撃墜 ─────────────────────────────────────────────────────
    def take_damage(self, amount: int) -> bool:
        self.hp -= amount
        return self.hp <= 0

    # ── 駒種ごとの速度（前進ベクトル fwd に対して定義）─────────────
    def _update_velocity(self, dt: float) -> None:
        f = self._fwd
        p = (-f[1], f[0])   # fwd に直交（ジグザグ用）
        s = self._spd
        k = self.kind
        if k == "bishop":
            # 45° の斜め一直線（一撃。折り返さない）。
            ang = math.radians(45.0 * self._bishop_sign)
            ca, sa = math.cos(ang), math.sin(ang)
            self.vx = (f[0] * ca - f[1] * sa) * s
            self.vy = (f[0] * sa + f[1] * ca) * s
        elif k == "knight":
            weave = math.sin(self._t * 9.0)
            self.vx = (f[0] * 1.05 + p[0] * weave * 0.9) * s
            self.vy = (f[1] * 1.05 + p[1] * weave * 0.9) * s
        elif k == "dragon":
            self._home(dt, max_speed=s * 1.2, turn=3.4)
        else:
            mult = _STRAIGHT_MULT.get(k, 1.0)
            self.vx, self.vy = f[0] * s * mult, f[1] * s * mult

    def _home(self, dt: float, max_speed: float, turn: float) -> None:
        target = self._target
        if target is None:
            self.vx, self.vy = self._fwd[0] * max_speed, self._fwd[1] * max_speed
            return
        dx = float(getattr(target, "sx", self.sx)) - self.sx
        dy = float(getattr(target, "sy", self.sy)) - self.sy
        d = math.hypot(dx, dy) or 1.0
        blend = min(1.0, turn * dt)
        self.vx += (dx / d * max_speed - self.vx) * blend
        self.vy += (dy / d * max_speed - self.vy) * blend

    def _activate(self) -> None:
        """着駒後、プレイヤー方向を前進ベクトルにして駒種の軌道へ移行する。"""
        tgt = self._target
        if tgt is not None:
            dx = float(getattr(tgt, "sx", self.sx)) - self.sx
            dy = float(getattr(tgt, "sy", self.sy)) - self.sy
            d = math.hypot(dx, dy) or 1.0
            self._fwd = (dx / d, dy / d)
        else:
            self._fwd = (-1.0, 0.0)
        self._t = 0.0
        self._update_velocity(0.0)

    # ── 進行方向へ回転（＋着駒スケール演出）─────────────────────
    def _face_velocity(self, *, force: bool = False) -> None:
        if not force and self._snap_anim <= 0.0 and self.vx == 0.0 and self.vy == 0.0:
            return
        if self.vx or self.vy:
            deg = -90.0 - math.degrees(math.atan2(self.vy, self.vx))
        else:
            deg = self._rot_deg or 0.0
        rotated_changed = self._rot_deg is None or abs(deg - self._rot_deg) >= 2.0
        if not rotated_changed and self._snap_anim <= 0.0 and not force:
            return
        self._rot_deg = deg
        img = pygame.transform.rotate(self._piece_base, deg)
        if self._snap_anim > 0.0:   # 「ピシッ」と置く: 一瞬大きくしてから戻す
            prog = 1.0 - max(0.0, self._snap_anim) / _SNAP_POP
            scale = 1.0 + 0.30 * math.sin(min(1.0, prog) * math.pi)
            w, h = img.get_size()
            img = pygame.transform.smoothscale(img, (max(1, int(w * scale)), max(1, int(h * scale))))
        center = self.rect.center
        self.image = img
        self.rect = self.image.get_rect(center=center)

    # ── 更新 ─────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        if self.lifetime is not None and self._mode == "active":
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.kill()
                return
        self._t += dt

        if self._mode == "incoming":
            self.sx += self.vx * dt
            self.sy += self.vy * dt
            if self._t >= self._incoming_time:
                self.sx, self.sy = self._drop_target
                self.vx = self.vy = 0.0
                self._mode = "placed"
                self._snap_anim = _SNAP_POP
                self.snap_event = True   # game_scene が SE/粒子を出す
            self._face_velocity()
        elif self._mode == "placed":
            self._place_t -= dt
            if self._snap_anim > 0.0:
                self._snap_anim = max(0.0, self._snap_anim - dt)
                self._face_velocity(force=True)
            if self._place_t <= 0:
                self._mode = "active"
                self._activate()
                self._face_velocity(force=True)
        else:  # active
            self._update_velocity(dt)
            self.sx += self.vx * dt
            self.sy += self.vy * dt
            self._face_velocity()

        self.rect.center = (int(self.sx), int(self.sy))

    def is_off_screen(self) -> bool:
        # 飛来/着駒中は画面外判定で消さない（端から差してくるため）。
        if self._mode in ("incoming", "placed"):
            return False
        return super().is_off_screen()


class ThrownBoardBullet(EnemyBullet):
    """投げつけられる将棋盤（Form3 投了王の「ちゃぶ台返し」）。回転しながら飛ぶ大型弾・撃墜可能。"""

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
        hp: int = 16,
    ) -> None:
        super().__init__(sx, sy, vx, vy, damage,
                         size=base_surface.get_size(), lifetime=lifetime,
                         terrain_passthrough=True)
        self._board_base = base_surface
        self._spin = spin
        self._gravity = gravity
        self._angle = 0.0
        self.destructible = True
        self.hp = hp

    def take_damage(self, amount: int) -> bool:
        self.hp -= amount
        return self.hp <= 0

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
