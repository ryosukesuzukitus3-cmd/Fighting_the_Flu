"""Small, anchored pixel effects and the player's deliberate final beam."""
from __future__ import annotations
import math
import pygame

from src.entities.bullet import Bullet
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT

ASSET_ROOT = "graphic/effects/kenney"
SOUND_ROOT = "music/se/kenney"


def pixel_stamp(resources, name, size, color):
    """Nearest-neighbour enlargement keeps every accent on a 2px grid."""
    raw = resources.image(f"{ASSET_ROOT}/{name}.png")
    small = pygame.transform.scale(raw, (max(1, size // 2), max(1, size // 2)))
    result = pygame.transform.scale(small, (size, size))
    result = result.copy()
    result.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def draw_bond_light(screen, resources, center, progress):
    if not 0 <= progress < 1:
        return
    x, y = map(int, center)
    layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    radius = 12 + int(54 * progress)
    alpha = int(170 * (1 - progress))
    # Four broken corners, never a screen-filling explosion.
    for angle in range(0, 360, 90):
        a = math.radians(angle + 45)
        px, py = x + int(math.cos(a) * radius), y + int(math.sin(a) * radius)
        pygame.draw.rect(layer, (151, 236, 204, alpha), (px - 2, py - 2, 4, 4))
    stamp = pixel_stamp(resources, "spark", 48, (150, 240, 207))
    stamp.set_alpha(alpha)
    layer.blit(stamp, stamp.get_rect(center=(x, y)))
    screen.blit(layer, (0, 0))


class EnergyMuzzle(pygame.sprite.Sprite):
    """Local harmless muzzle accent; the emitted bullets define the danger."""
    warning_only = True
    terrain_passthrough = True
    damage = 0
    def __init__(self, resources, x, y):
        super().__init__()
        self._base = pixel_stamp(resources, "spark", 32, (117, 208, 255))
        self.image = self._base.copy()
        self.rect = self.image.get_rect(center=(round(x), round(y)))
        self._life = 0.15

    def update(self, dt):
        self._life -= dt
        if self._life <= 0:
            self.kill()
        else:
            self.image.set_alpha(int(220 * self._life / 0.15))

    def is_off_screen(self):
        return False


class FinalBeam(Bullet):
    """Aimed cinematic projectile: the bright wavefront must reach the boss."""
    final_strike = True
    piercing = True
    terrain_passthrough = True
    CHARGE = 0.55
    TRAVEL = 0.24
    DURATION = 1.55

    def __init__(self, game, origin, target):
        super().__init__(origin[0], origin[1], 0, 0, damage=1)
        self.game = game
        self.origin = pygame.Vector2(origin)
        self.target = pygame.Vector2(target)
        self.age = 0.0
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = pygame.Rect(round(origin[0]), round(origin[1]), 1, 1)
        self.game.sound.play_se(f"{SOUND_ROOT}/forceField_002.ogg", volume=0.5)

    @property
    def reached_target(self):
        return self.age >= self.CHARGE + self.TRAVEL

    def advance(self, dt):
        before = self.age
        self.age += dt
        if before < self.CHARGE <= self.age:
            self.game.sound.play_se(f"{SOUND_ROOT}/laserLarge_002.ogg", volume=0.75)
        progress = max(0.0, min(1.0, (self.age - self.CHARGE) / self.TRAVEL))
        head = self.origin.lerp(self.target, progress)
        self.rect.center = (round(head.x), round(head.y))

    def update(self, dt, camera):
        # The director also advances the fade after the sprite hits and dies.
        pass

    def is_off_screen(self, camera):
        return self.age > self.DURATION

    def collides_with_rect(self, rect):
        return self.reached_target and rect.collidepoint(self.target)

    def draw_effect(self, screen):
        if self.age >= self.DURATION:
            return
        resources = self.game.resources
        origin, target = self.origin / 2, self.target / 2
        layer = pygame.Surface((SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), pygame.SRCALPHA)
        charge = min(1.0, self.age / self.CHARGE)
        fade = min(1.0, max(0.0, (self.DURATION - self.age) / 0.45))
        # Charge converges towards the player's muzzle, with no repeated flashes.
        if self.age < self.CHARGE:
            for i in range(8):
                angle = i * math.tau / 8 + self.age * 2
                r = 8 + (1 - charge) * 42
                p = origin + pygame.Vector2(math.cos(angle), math.sin(angle)) * r
                pygame.draw.rect(layer, (153, 240, 217, 190), (round(p.x), round(p.y), 2, 2))
        else:
            travel = min(1.0, (self.age - self.CHARGE) / self.TRAVEL)
            direction = target - origin
            distance = direction.length()
            if distance:
                direction /= distance
            tip = origin + direction * (distance * travel + (100 if self.reached_target else 0))
            normal = pygame.Vector2(-direction.y, direction.x)
            width = (31 + 3 * math.sin(self.age * 24)) * fade
            for scale, color in ((1.45, (36, 117, 148, 100)),
                                 (1.0, (91, 218, 235, 240)),
                                 (0.66, (167, 255, 227, 255)),
                                 (0.24, (251, 255, 238, 255))):
                w = max(1, width * scale)
                points = [origin - normal * w * .3, tip - normal * w,
                          tip + normal * w, origin + normal * w * .3]
                pygame.draw.polygon(layer, color, points)
            for i in range(7):
                phase = (i / 7 + self.age * 2.1) % 1
                a = origin.lerp(tip, phase)
                b = a + direction * 18
                pygame.draw.line(layer, (245, 255, 241, int(190 * fade)), a, b, 2)
        screen.blit(pygame.transform.scale(layer, screen.get_size()), (0, 0))
        stamp = pixel_stamp(resources, "flare", int(48 + 72 * charge), (169, 248, 221))
        stamp.set_alpha(int(225 * fade))
        screen.blit(stamp, stamp.get_rect(center=self.origin))
        if self.reached_target:
            impact = pixel_stamp(resources, "spark", int(150 * fade) + 2, (255, 246, 205))
            impact.set_alpha(int(240 * fade))
            screen.blit(impact, impact.get_rect(center=self.target))

