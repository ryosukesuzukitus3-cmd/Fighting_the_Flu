"""ブロリー系レーザーの演出スプライト群。

`enemy_bullets` グループに載せて毎フレーム `update(dt)` で自前描画する。
雑魚／ボス共通の「チャージ → フラッシュ → 太い本体 → 放電 → 先細りで消滅」を
ここに集約する（弾の見た目を `EnemyBullet` の静止画像で持たせる方式の置き換え）。

すべて `warning_only` / `terrain_passthrough` を持つので、当たり判定が必要な
ボス本体ビームだけ `damage`>0・`warning_only=False` を指定し、それ以外
（雑魚ビーム＝突進が本体ダメージ・チャージ球・マズルフラッシュ）は当たらない。
"""
from __future__ import annotations

import math
import random

import pygame

from src.entities.bullets.enemy_bullet import EnemyBullet

# パレット: (core=中心の白熱色, mid=中間色, glow=外周グロー)
Palette = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]

MOB_PALETTE: Palette = ((255, 250, 220), (255, 150, 50), (255, 80, 20))
BOSS_PALETTE: Palette = ((255, 245, 225), (255, 60, 55), (210, 15, 30))

# 放電アークの色（電撃感を出す寒色＋白）
_ARC_COLORS = ((215, 238, 255), (255, 255, 255), (150, 205, 255))


class LaserBeamSprite(EnemyBullet):
    """横一文字の極太レーザー本体。

    立ち上がり（fade_in）で一気に太くなり、寿命の最後（taper_time）で
    徐々に細く・薄くなって消える。`discharge=True` で周囲に放電アークを描く。
    """

    def __init__(
        self,
        cx: float,
        cy: float,
        width: int,
        height: int,
        *,
        palette: Palette,
        lifetime: float,
        damage: int = 0,
        warning_only: bool = True,
        discharge: bool = False,
        fade_in: float = 0.06,
        taper_time: float = 0.32,
        pulse_freq: float = 26.0,
    ) -> None:
        super().__init__(
            cx, cy, 0.0, 0.0, damage,
            size=(width, height),
            color=palette[2],
            lifetime=lifetime,
            terrain_passthrough=True,
            warning_only=warning_only,
        )
        self._w = width
        self._h = height
        self._core, self._mid, self._glow = palette
        self._discharge = discharge
        self._fade_in = max(0.0, fade_in)
        self._taper_time = max(0.001, taper_time)
        self._pulse_freq = pulse_freq
        self._t = 0.0
        self._render()

    def update(self, dt: float) -> None:
        self._t += dt
        if self.lifetime is not None:
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.kill()
                return
        self._render()
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self.rect = self.image.get_rect(center=(int(self.sx), int(self.sy)))

    # ── 描画 ────────────────────────────────────────────────────────
    def _vertical_scale(self) -> tuple[float, float, float]:
        """(太さスケール, 全体アルファ係数, 立ち上がりフラッシュ係数) を返す。"""
        max_life = self._max_lifetime or self.lifetime or self._taper_time
        remaining = self.lifetime if self.lifetime is not None else max_life
        elapsed = max_life - remaining

        flash = 0.0
        if self._fade_in > 0 and elapsed < self._fade_in:
            grow = elapsed / self._fade_in
            vscale = grow
            flash = 1.0 - grow
        elif remaining < self._taper_time:
            vscale = max(0.08, remaining / self._taper_time)
        else:
            vscale = 1.0

        vscale *= 1.0 + 0.10 * math.sin(self._t * self._pulse_freq)
        alpha = 1.0
        if remaining < self._taper_time:
            alpha = max(0.0, remaining / self._taper_time)
        return vscale, alpha, flash

    def _render(self) -> None:
        w, h = self._w, self._h
        vscale, alpha, flash = self._vertical_scale()
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cy = h // 2

        glow_h = max(2, int(h * vscale))
        mid_h = max(2, int(h * 0.55 * vscale))
        core_h = max(1, int(h * 0.30 * vscale))
        hot_h = max(1, core_h // 2)

        pygame.draw.rect(surf, (*self._glow, 110), (0, cy - glow_h // 2, w, glow_h),
                         border_radius=max(1, glow_h // 2))
        pygame.draw.rect(surf, (*self._mid, 215), (0, cy - mid_h // 2, w, mid_h),
                         border_radius=max(1, mid_h // 2))
        pygame.draw.rect(surf, (*self._core, 255), (0, cy - core_h // 2, w, core_h),
                         border_radius=max(1, core_h // 2))
        pygame.draw.rect(surf, (255, 255, 255, 255), (0, cy - hot_h // 2, w, hot_h))

        if self._discharge and vscale > 0.35:
            self._draw_arcs(surf, w, cy, glow_h)

        if flash > 0:
            surf.fill((255, 255, 255, int(150 * flash)), special_flags=pygame.BLEND_RGB_ADD)

        if alpha < 1.0:
            surf.set_alpha(int(255 * alpha))
        self.image = surf

    def _draw_arcs(self, surf: pygame.Surface, w: int, cy: int, band: int) -> None:
        reach = band * 0.65
        n = max(4, w // 95)
        for _ in range(n):
            x = random.uniform(0, w)
            span = random.uniform(40, 95)
            segs = random.randint(2, 4)
            pts = []
            for _s in range(segs + 1):
                pts.append((x, cy + random.uniform(-reach, reach)))
                x += span / segs
            col = random.choice(_ARC_COLORS)
            pygame.draw.lines(surf, (*col, 65), False, pts, 5)
            pygame.draw.lines(surf, (*col, 235), False, pts, 2)


class LaserChargeOrb(pygame.sprite.Sprite):
    """発射元（host）の銃口に張り付く充電エフェクト。

    粒子がリング状に収束しながら中心グローが膨らむ。host が消えるか
    duration を超えたら自滅する。`enemy_bullets` 用に warning_only。
    """

    warning_only = True
    terrain_passthrough = True

    def __init__(self, host: pygame.sprite.Sprite, duration: float, palette: Palette,
                 *, offset_ratio: float = -0.30, size: int = 104) -> None:
        super().__init__()
        self._host = host
        self._duration = max(0.001, duration)
        self._core, self._mid, self._glow = palette
        self._size = size
        self._offset_ratio = offset_ratio
        self._t = 0.0
        self.sx, self.sy = host.rect.center
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.sx), int(self.sy)))
        self._render(0.0)

    def update(self, dt: float) -> None:
        self._t += dt
        if self._host is None or not self._host.alive() or self._t >= self._duration:
            self.kill()
            return
        cx, cy = self._host.rect.center
        self.sx = cx + self._offset_ratio * self._host.rect.width
        self.sy = cy
        self._render(min(1.0, self._t / self._duration))
        self.rect = self.image.get_rect(center=(int(self.sx), int(self.sy)))

    def is_off_screen(self) -> bool:
        return False

    def _render(self, ratio: float) -> None:
        size = self._size
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2

        # 収束する粒子リング
        n = int(10 + 10 * ratio)
        dist = max(4.0, (size * 0.42) * (1.0 - ratio))
        for i in range(n):
            ang = self._t * 7.0 + i * (6.2832 / n)
            px = c + math.cos(ang) * dist
            py = c + math.sin(ang) * dist
            r = max(1, int(2 + 3 * ratio))
            pygame.draw.circle(surf, (*self._core, int(120 + 110 * ratio)), (int(px), int(py)), r)

        # 中心グロー（脈動）
        pulse = 0.5 + 0.5 * math.sin(self._t * 16.0)
        glow_r = int((size * 0.12) + (size * 0.20) * ratio + 3 * pulse)
        if glow_r > 0:
            pygame.draw.circle(surf, (*self._glow, int(70 + 90 * ratio)), (c, c), glow_r)
            pygame.draw.circle(surf, (*self._mid, int(110 + 110 * ratio)), (c, c),
                               max(1, int(glow_r * 0.6)))
            pygame.draw.circle(surf, (*self._core, min(255, int(160 + 95 * ratio))), (c, c),
                               max(1, int(glow_r * 0.32)))
        self.image = surf


class LaserMuzzleFlash(pygame.sprite.Sprite):
    """発射の瞬間に銃口で弾ける閃光（拡大しながらフェード）。"""

    warning_only = True
    terrain_passthrough = True

    def __init__(self, x: float, y: float, palette: Palette,
                 *, duration: float = 0.16, max_radius: int = 76, spikes: int = 8) -> None:
        super().__init__()
        self._core, self._mid, self._glow = palette
        self._duration = max(0.001, duration)
        self._max_radius = max_radius
        self._spikes = spikes
        self._spin = random.uniform(0, 6.2832)
        self._t = 0.0
        self.sx, self.sy = x, y
        dim = max_radius * 2 + 4
        self.image = pygame.Surface((dim, dim), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self._render()

    def update(self, dt: float) -> None:
        self._t += dt
        if self._t >= self._duration:
            self.kill()
            return
        self._render()

    def is_off_screen(self) -> bool:
        return False

    def _render(self) -> None:
        p = min(1.0, self._t / self._duration)
        fade = 1.0 - p
        dim = self._max_radius * 2 + 4
        surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
        c = dim // 2

        glow_r = int(self._max_radius * (0.45 + 0.55 * p))
        pygame.draw.circle(surf, (*self._glow, int(150 * fade)), (c, c), glow_r)
        pygame.draw.circle(surf, (*self._mid, int(200 * fade)), (c, c), max(1, int(glow_r * 0.6)))
        pygame.draw.circle(surf, (*self._core, int(255 * fade)), (c, c), max(1, int(glow_r * 0.32)))

        spike_len = self._max_radius * (0.7 + 0.4 * p)
        for i in range(self._spikes):
            ang = self._spin + i * (6.2832 / self._spikes)
            ex = c + math.cos(ang) * spike_len
            ey = c + math.sin(ang) * spike_len
            pygame.draw.line(surf, (*self._core, int(220 * fade)), (c, c), (int(ex), int(ey)),
                             max(1, int(4 * fade) + 1))
        self.image = surf
