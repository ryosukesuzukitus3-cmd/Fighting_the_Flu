"""Render still captures for checking boss concepts without launching the game."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.entities.enemies.boss import Boss
from src.scenes.game_scene import GameScene

OUT = ROOT / "captures"


class _Resources:
    def image(self, path: str) -> pygame.Surface:
        return pygame.image.load(str(ROOT / "assets" / path)).convert_alpha()

    def pixelfont(self, size: int) -> pygame.font.Font:
        return pygame.font.Font(None, size)


class _Sound:
    def play_se_alias(self, *args, **kwargs) -> None:
        pass

    def play_se(self, *args, **kwargs) -> None:
        pass


class _Game:
    resources = _Resources()
    sound = _Sound()


class _Player:
    sx = 140.0
    sy = 300.0


class _LinkStub(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int) -> None:
        super().__init__()
        self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (90, 230, 255), (14, 14), 12, 2)
        self.rect = self.image.get_rect(center=(x, y))

    def alive(self) -> bool:
        return True


def _scene_stub(boss: Boss):
    scene = object.__new__(GameScene)
    scene._boss = boss
    scene.game = _Game()
    return scene


def _force_pattern(pattern: str, interval: float = 0.5) -> None:
    Boss._phase = property(lambda self: (1.0, pattern, interval))  # type: ignore[method-assign]


def _boss(stage_id: int, x: int, y: int) -> Boss:
    boss = Boss(_Game(), stage_id)
    boss._state = "fight"
    boss.sx = float(x)
    boss.sy = float(y)
    boss.rect.center = (x, y)
    return boss


def _cases() -> list[tuple[str, Boss, pygame.sprite.Group, str]]:
    orig_phase = Boss._phase
    cases: list[tuple[str, Boss, pygame.sprite.Group, str]] = []
    try:
        b2 = _boss(2, 612, 300)
        b2._armor = 26
        _force_pattern("mega_laser")
        bullets2 = pygame.sprite.Group()
        b2._shoot(bullets2, _Player())
        cases.append(("boss2_heavy_armor", b2, bullets2, "BOSS2: HEAVY ARMOR / LASER CHARGE"))

        b2w = _boss(2, 612, 300)
        b2w._weak_timer = 1.2
        b2w._armor = 10
        b2w._shot_variant = 1
        _force_pattern("mega_laser")
        bullets2w = pygame.sprite.Group()
        b2w._shoot(bullets2w, _Player())
        cases.append(("boss2_core_exposed", b2w, bullets2w, "BOSS2: CORE EXPOSED AFTER BIG MOVE"))

        b3 = _boss(3, 622, 300)
        b3._summoned = [_LinkStub(150, 120), _LinkStub(170, 300), _LinkStub(150, 480)]
        _force_pattern("drone_cross")
        bullets3 = pygame.sprite.Group()
        b3._shoot(bullets3, _Player())
        cases.append(("boss3_fortress_shield", b3, bullets3, "BOSS3: STATIONARY FORTRESS / DRONE SHIELD"))

        b4f2 = _boss(4, 470, 285)
        b4f2._form2 = True
        _force_pattern("dash_knives")
        bullets4f2 = pygame.sprite.Group()
        b4f2._shoot(bullets4f2, _Player())
        cases.append(("boss4_form2_dash", b4f2, bullets4f2, "FORM2: FAST DASH FIGHT"))

        b4f3 = _boss(4, 590, 300)
        b4f3._transform_form3()
        b4f3.sx = 590.0
        b4f3.sy = 300.0
        b4f3.rect.center = (590, 300)
        _force_pattern("curtain")
        bullets4f3 = pygame.sprite.Group()
        b4f3._shoot(bullets4f3, _Player())
        cases.append(("boss4_form3_aura", b4f3, bullets4f3, "FORM3: SLOW NIGHTMARE FIELD"))
    finally:
        Boss._phase = orig_phase  # type: ignore[method-assign]
    return cases


def _render(name: str, boss: Boss, bullets: pygame.sprite.Group, title: str) -> Path:
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    surf.fill((12, 14, 24, 255))
    for x in range(0, SCREEN_WIDTH, 80):
        pygame.draw.line(surf, (28, 32, 48), (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, 60):
        pygame.draw.line(surf, (28, 32, 48), (0, y), (SCREEN_WIDTH, y))
    pygame.draw.circle(surf, (90, 230, 120), (int(_Player.sx), int(_Player.sy)), 10, 2)
    bullets.draw(surf)
    for stub in getattr(boss, "_summoned", []):
        surf.blit(stub.image, stub.rect)
    surf.blit(boss.image, boss.rect)
    _scene_stub(boss)._draw_boss_gimmick(surf)
    label = pygame.font.Font(None, 26).render(title, True, (255, 230, 150))
    surf.blit(label, (18, 18))
    out = OUT / f"{name}.png"
    pygame.image.save(surf, str(out))
    return out


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(exist_ok=True)
    for case in _cases():
        print(_render(*case))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
