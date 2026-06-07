from __future__ import annotations
import math
import random
import pygame


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "radius",
                 "drag", "gravity", "additive")

    def __init__(self, x: float, y: float, color: tuple, speed: float, radius: int,
                 life: float, drag: float = 0.90, gravity: float = 0.0,
                 additive: bool = False) -> None:
        angle = random.uniform(0, 6.2832)
        spd   = random.uniform(speed * 0.4, speed)
        self.x       = x
        self.y       = y
        self.vx      = spd * math.cos(angle)
        self.vy      = spd * math.sin(angle)
        self.life    = life
        self.max_life = life
        self.color   = color
        self.radius  = radius
        self.drag    = drag
        self.gravity = gravity
        self.additive = additive

    def update(self, dt: float) -> bool:
        """Return False when dead."""
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= self.drag ** (dt * 60)
        self.vy *= self.drag ** (dt * 60)
        return self.life > 0


class ParticleSystem:
    def __init__(self) -> None:
        self._particles: list[_Particle] = []

    # ── spawn helpers ─────────────────────────────────────────────
    def spawn_explosion(self, x: float, y: float, color: tuple = (255, 160, 40), count: int = 18) -> None:
        for _ in range(count):
            life = random.uniform(0.25, 0.55)
            r    = random.randint(3, 6)
            self._particles.append(_Particle(x, y, color, 220, r, life))

    def spawn_hit(self, x: float, y: float, color: tuple = (255, 255, 120), count: int = 8) -> None:
        for _ in range(count):
            life = random.uniform(0.12, 0.28)
            r    = random.randint(2, 4)
            self._particles.append(_Particle(x, y, color, 150, r, life))

    def spawn_player_hit(self, x: float, y: float) -> None:
        self.spawn_explosion(x, y, color=(80, 160, 255), count=14)

    def spawn_glow(self, x: float, y: float, color: tuple = (255, 220, 120),
                   count: int = 10, speed: float = 90.0) -> None:
        """加算合成のグロー粒子（ふわっと광る・低速・残光長め）。"""
        for _ in range(count):
            life = random.uniform(0.35, 0.7)
            r    = random.randint(4, 8)
            self._particles.append(_Particle(x, y, color, speed, r, life,
                                             drag=0.86, additive=True))

    def spawn_spark(self, x: float, y: float, color: tuple = (255, 240, 200),
                    count: int = 14, speed: float = 360.0) -> None:
        """高速で散る火花（重力あり・加算合成）。"""
        for _ in range(count):
            life = random.uniform(0.2, 0.45)
            r    = random.randint(1, 3)
            self._particles.append(_Particle(x, y, color, speed, r, life,
                                             drag=0.93, gravity=240.0, additive=True))

    def spawn_big_explosion(self, x: float, y: float) -> None:
        """撃破用の豪華爆発（火花＋煙＋グローの二層）。"""
        self.spawn_spark(x, y, count=20)
        self.spawn_glow(x, y, color=(255, 180, 80), count=14)
        self.spawn_explosion(x, y, color=(255, 140, 40), count=24)
        # 煙（暗色・上昇）
        for _ in range(10):
            life = random.uniform(0.5, 0.9)
            r    = random.randint(6, 11)
            p = _Particle(x, y, (90, 70, 70), 70, r, life, drag=0.9, gravity=-40.0)
            self._particles.append(p)

    # ── update / draw ─────────────────────────────────────────────
    def update(self, dt: float) -> None:
        self._particles = [p for p in self._particles if p.update(dt)]

    def draw(self, surface: pygame.Surface) -> None:
        for p in self._particles:
            alpha = max(0, int(255 * (p.life / p.max_life)))
            color = (*p.color[:3], alpha)
            s = pygame.Surface((p.radius * 2, p.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, color, (p.radius, p.radius), p.radius)
            if p.additive:
                surface.blit(s, (int(p.x) - p.radius, int(p.y) - p.radius),
                             special_flags=pygame.BLEND_RGB_ADD)
            else:
                surface.blit(s, (int(p.x) - p.radius, int(p.y) - p.radius))
