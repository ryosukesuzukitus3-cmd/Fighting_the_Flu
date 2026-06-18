"""地形（壁・障害物・デブリ）。ワールド座標で配置し、カメラスクロールで左へ流れる。

自機が接触するとダメージ。砲台（EnemyTurret）の設置足場としても用いる。
ステージごとに `kind` と配置を変えて特色を出す（宇宙=debris まばら / 岩石=wall・rock 多め）。
"""
from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame
from src.core.constants import SCREEN_HEIGHT

if TYPE_CHECKING:
    from src.core.camera import Camera

# kind 別の基調色 (本体, 縁)
_KIND_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "wall":   ((70, 72, 82),  (110, 114, 128)),   # 金属/コンクリの壁
    "rock":   ((96, 78, 60),  (140, 116, 86)),    # 岩石
    "debris": ((84, 86, 96),  (130, 134, 150)),   # 宇宙デブリ
    "clot":   ((126, 24, 34), (230, 82, 76)),
}


class Terrain(pygame.sprite.Sprite):
    """スクロールする地形ブロック（ワールド座標 world_x / 画面 y 固定）。"""

    def __init__(
        self,
        world_x: float,
        y: float,
        w: int,
        h: int,
        kind: str = "wall",
        *,
        destructible: bool = False,
        hp: int = 5,
        drop_chance: float = 0.0,
        fixed_drop: str | None = None,
    ) -> None:
        super().__init__()
        self.world_x = float(world_x)
        self.y       = float(y)
        self.kind    = kind
        self.destructible = destructible
        self.max_hp = max(1, hp)
        self.hp = self.max_hp
        self.drop_chance = drop_chance
        self.fixed_drop = fixed_drop
        self._w = w
        self._h = h
        self.image   = self._make_surface(w, h, kind, destructible=destructible, fixed_drop=fixed_drop)
        self.rect    = self.image.get_rect(topleft=(int(world_x), int(y)))

    @staticmethod
    def _make_surface(
        w: int,
        h: int,
        kind: str,
        *,
        destructible: bool = False,
        damage_ratio: float = 0.0,
        fixed_drop: str | None = None,
    ) -> pygame.Surface:
        if kind == "clot":
            return Terrain._make_clot_surface(
                w, h,
                destructible=destructible,
                damage_ratio=damage_ratio,
                fixed_drop=fixed_drop,
            )

        base, edge = _KIND_COLORS.get(kind, _KIND_COLORS["wall"])
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        radius = 8 if kind != "wall" else 3
        pygame.draw.rect(surf, base, (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(surf, edge, (0, 0, w, h), 2, border_radius=radius)
        # ざらつき（決定的擬似ランダムの斑点）
        rng = random.Random((w * 73856093) ^ (h * 19349663) ^ hash(kind))
        for _ in range(max(3, (w * h) // 900)):
            sx = rng.randint(2, max(2, w - 3))
            sy = rng.randint(2, max(2, h - 3))
            shade = tuple(max(0, c - 24) for c in base)
            pygame.draw.circle(surf, shade, (sx, sy), rng.randint(1, 3))
        Terrain._draw_kind_details(surf, rng, w, h, kind, base, edge)
        if destructible:
            crack_col = (255, 190, 105)
            node_col = (255, 125, 70)
            for _ in range(4 + int(damage_ratio * 8)):
                x = rng.randint(5, max(5, w - 6))
                y = rng.randint(8, max(8, h - 9))
                pts = [(x, y)]
                for _step in range(rng.randint(2, 5)):
                    x += rng.randint(-14, 14)
                    y += rng.randint(-16, 16)
                    pts.append((max(3, min(w - 4, x)), max(4, min(h - 5, y))))
                pygame.draw.lines(surf, crack_col, False, pts, 2)
            for _ in range(max(2, (w * h) // 7000)):
                sx = rng.randint(8, max(8, w - 9))
                sy = rng.randint(12, max(12, h - 13))
                pygame.draw.circle(surf, node_col, (sx, sy), rng.randint(3, 6))
        Terrain._draw_reward_core(surf, w, h, fixed_drop, damage_ratio=damage_ratio)
        return surf

    @staticmethod
    def _draw_kind_details(
        surf: pygame.Surface,
        rng: random.Random,
        w: int,
        h: int,
        kind: str,
        base: tuple[int, int, int],
        edge: tuple[int, int, int],
    ) -> None:
        dark = tuple(max(0, c - 34) for c in base)
        pale = tuple(min(255, c + 28) for c in edge)
        if kind == "wall":
            for x in range(18, w, 32):
                pygame.draw.line(surf, (*dark, 95), (x, 4), (x, h - 5), 1)
            for y in range(16, h, 28):
                pygame.draw.line(surf, (*pale, 50), (5, y), (w - 6, y), 1)
            for _ in range(max(2, (w * h) // 2400)):
                sx = rng.randint(8, max(8, w - 9))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, (*pale, 92), (sx, sy), 2)
                pygame.draw.circle(surf, (*dark, 70), (sx + 1, sy + 1), 2)
        elif kind == "debris":
            for _ in range(max(3, (w * h) // 1800)):
                sx = rng.randint(4, max(4, w - 18))
                sy = rng.randint(4, max(4, h - 16))
                plate = pygame.Rect(sx, sy, rng.randint(12, max(14, min(34, w // 2))), rng.randint(8, max(10, min(24, h // 2))))
                pygame.draw.rect(surf, (*dark, 72), plate, border_radius=2)
                pygame.draw.rect(surf, (*pale, 50), plate, 1, border_radius=2)
            for _ in range(max(2, (w * h) // 2600)):
                pts = []
                x = rng.randint(4, max(4, w - 5))
                y = rng.randint(4, max(4, h - 5))
                for _step in range(4):
                    pts.append((max(2, min(w - 3, x)), max(2, min(h - 3, y))))
                    x += rng.randint(-10, 14)
                    y += rng.randint(-8, 10)
                pygame.draw.lines(surf, (92, 210, 230, 54), False, pts, 1)
        elif kind == "rock":
            for _ in range(max(3, (w * h) // 1400)):
                x = rng.randint(6, max(6, w - 7))
                y = rng.randint(6, max(6, h - 7))
                pts = [
                    (x, y),
                    (max(2, min(w - 3, x + rng.randint(-18, 18))), max(2, min(h - 3, y + rng.randint(8, 22)))),
                    (max(2, min(w - 3, x + rng.randint(10, 28))), max(2, min(h - 3, y + rng.randint(-8, 12)))),
                ]
                pygame.draw.polygon(surf, (*dark, 46), pts)
                pygame.draw.lines(surf, (*pale, 38), True, pts, 1)

    @staticmethod
    def _make_clot_surface(
        w: int,
        h: int,
        *,
        destructible: bool = False,
        damage_ratio: float = 0.0,
        fixed_drop: str | None = None,
    ) -> pygame.Surface:
        rng = random.Random((w * 92837111) ^ (h * 689287499) ^ 0xC107)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        if w >= h * 1.35:
            pygame.draw.ellipse(surf, (40, 6, 12, 130), (4, int(h * 0.28), w - 8, int(h * 0.66)))
            pygame.draw.ellipse(surf, (90, 14, 22, 190), (2, int(h * 0.12), w - 4, int(h * 0.76)))
            pygame.draw.ellipse(surf, (172, 42, 46, 116), (8, int(h * 0.06), w - 16, int(h * 0.76)))
            count = max(5, min(11, w // 34))
            for i in range(count):
                cx = int((i + 0.5) * w / count + rng.randint(-8, 8))
                cy = int(h * (0.50 + rng.uniform(-0.12, 0.10)))
                cw = max(26, min(int(h * rng.uniform(0.82, 1.28)), max(28, w // 3)))
                ch = max(20, min(int(h * rng.uniform(0.48, 0.78)), h - 6))
                Terrain._draw_blood_cell(surf, (cx, cy), (cw, ch), rng)
        else:
            pygame.draw.ellipse(surf, (40, 6, 12, 130), (int(w * 0.18), 4, int(w * 0.66), h - 8))
            pygame.draw.ellipse(surf, (90, 14, 22, 190), (int(w * 0.08), 2, int(w * 0.84), h - 4))
            pygame.draw.ellipse(surf, (172, 42, 46, 116), (int(w * 0.04), 8, int(w * 0.88), h - 16))
            count = max(5, min(9, h // 30))
            for i in range(count):
                cx = int(w * (0.50 + rng.uniform(-0.12, 0.12)))
                cy = int((i + 0.5) * h / count + rng.randint(-8, 8))
                cw = max(24, min(int(w * rng.uniform(0.58, 0.86)), w - 6))
                ch = max(24, min(int(w * rng.uniform(0.52, 0.82)), max(28, h // 3)))
                Terrain._draw_blood_cell(surf, (cx, cy), (cw, ch), rng)

        Terrain._draw_clot_strands(surf, rng, w, h)
        pygame.draw.ellipse(surf, (250, 105, 92, 110), surf.get_rect().inflate(-5, -5), 2)
        pygame.draw.ellipse(surf, (255, 180, 132, 45), surf.get_rect().inflate(-16, -18), 1)

        if destructible:
            crack_col = (255, 190, 115)
            node_col = (255, 112, 82)
            crack_count = 4 + int(max(0.0, min(1.0, damage_ratio)) * 8)
            for _ in range(crack_count):
                x = rng.randint(8, max(8, w - 9))
                y = rng.randint(8, max(8, h - 9))
                pts = [(x, y)]
                for _step in range(rng.randint(2, 5)):
                    x += rng.randint(-16, 16)
                    y += rng.randint(-12, 12)
                    pts.append((max(4, min(w - 5, x)), max(4, min(h - 5, y))))
                pygame.draw.lines(surf, crack_col, False, pts, 2)
            for _ in range(max(2, (w * h) // 6000)):
                sx = rng.randint(10, max(10, w - 11))
                sy = rng.randint(10, max(10, h - 11))
                pygame.draw.circle(surf, node_col, (sx, sy), rng.randint(3, 6))

        Terrain._draw_reward_core(surf, w, h, fixed_drop, damage_ratio=damage_ratio)
        return surf

    @staticmethod
    def _draw_reward_core(
        surf: pygame.Surface,
        w: int,
        h: int,
        fixed_drop: str | None,
        *,
        damage_ratio: float = 0.0,
    ) -> None:
        if fixed_drop != "WeaponItem":
            return

        cx, cy = w // 2, h // 2
        core = max(24, min(w, h) // 3)
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        pulse = int(32 * max(0.0, min(1.0, damage_ratio)))
        pygame.draw.ellipse(
            glow,
            (70, 230, 255, 68 + pulse),
            pygame.Rect(cx - core, cy - core, core * 2, core * 2),
        )
        pygame.draw.ellipse(
            glow,
            (255, 235, 130, 42),
            pygame.Rect(cx - core // 2, cy - core, core, core * 2),
            2,
        )
        surf.blit(glow, (0, 0))

        capsule_w = max(26, min(w - 12, int(core * 1.25)))
        capsule_h = max(14, min(h - 12, int(core * 0.55)))
        capsule = pygame.Rect(0, 0, capsule_w, capsule_h)
        capsule.center = (cx, cy)
        pygame.draw.ellipse(surf, (18, 54, 70, 230), capsule.inflate(8, 8))
        pygame.draw.ellipse(surf, (96, 230, 255, 240), capsule)
        pygame.draw.ellipse(surf, (255, 248, 180, 230), capsule, 2)
        pygame.draw.line(
            surf,
            (255, 255, 245, 245),
            (capsule.left + 7, cy),
            (capsule.right - 7, cy),
            3,
        )
        pygame.draw.line(
            surf,
            (255, 255, 245, 230),
            (cx, capsule.top + 4),
            (cx, capsule.bottom - 4),
            3,
        )
        for ox, oy in ((-core, 0), (core, 0), (0, -core), (0, core)):
            pygame.draw.circle(surf, (255, 226, 104, 210), (cx + ox // 2, cy + oy // 2), 3)

    @staticmethod
    def _draw_clot_strands(surf: pygame.Surface, rng: random.Random, w: int, h: int) -> None:
        strand_col = (255, 126, 104, 72)
        dark_col = (68, 8, 16, 70)
        for _ in range(max(3, (w * h) // 3200)):
            x = rng.randint(4, max(4, w - 5))
            y = rng.randint(4, max(4, h - 5))
            pts = [(x, y)]
            for _step in range(rng.randint(3, 6)):
                x += rng.randint(-22, 22)
                y += rng.randint(-15, 15)
                pts.append((max(2, min(w - 3, x)), max(2, min(h - 3, y))))
            if len(pts) > 1:
                pygame.draw.lines(surf, dark_col, False, pts, 3)
                pygame.draw.lines(surf, strand_col, False, pts, 1)

        for _ in range(max(4, (w * h) // 2600)):
            sx = rng.randint(8, max(8, w - 9))
            sy = rng.randint(8, max(8, h - 9))
            pygame.draw.circle(surf, (238, 92, 74, 128), (sx, sy), rng.randint(2, 4))
            pygame.draw.circle(surf, (255, 176, 126, 100), (sx - 1, sy - 1), 1)

    @staticmethod
    def _draw_blood_cell(
        surf: pygame.Surface,
        center: tuple[int, int],
        size: tuple[int, int],
        rng: random.Random,
    ) -> None:
        cx, cy = center
        w, h = size
        cell = pygame.Surface((w + 10, h + 10), pygame.SRCALPHA)
        rect = pygame.Rect(5, 5, w, h)
        base = rng.choice(((174, 34, 44, 230), (192, 42, 48, 220), (150, 28, 38, 235)))
        edge = (248, 105, 94, 155)
        hollow = (86, 12, 22, 110)
        shine = (255, 152, 130, 70)

        pygame.draw.ellipse(cell, (50, 8, 14, 100), rect.move(2, 3))
        pygame.draw.ellipse(cell, base, rect)
        pygame.draw.ellipse(cell, edge, rect, 2)
        inner = rect.inflate(-max(8, w // 3), -max(6, h // 3))
        pygame.draw.ellipse(cell, hollow, inner)
        glint = pygame.Rect(rect.left + w // 6, rect.top + h // 6, max(8, w // 3), max(4, h // 5))
        pygame.draw.ellipse(cell, shine, glint, 1)
        rotated = pygame.transform.rotate(cell, rng.uniform(-18, 18))
        target = rotated.get_rect(center=(cx, cy))
        surf.blit(rotated, target)

    def take_damage(self, amount: int) -> bool:
        """破壊されたら True。破壊不能地形は常に False。"""
        if not self.destructible:
            return False
        self.hp -= amount
        if self.hp <= 0:
            return True
        center = self.rect.center
        damage_ratio = 1.0 - (self.hp / self.max_hp)
        self.image = self._make_surface(
            self._w, self._h, self.kind,
            destructible=True,
            damage_ratio=damage_ratio,
            fixed_drop=self.fixed_drop,
        )
        self.rect = self.image.get_rect(center=center)
        return False

    def update(self, dt: float, camera: "Camera") -> None:
        self.rect.topleft = (int(camera.to_screen_x(self.world_x)), int(self.y))

    def is_off_left(self, camera: "Camera") -> bool:
        return self.world_x + self.rect.width < camera.x


# ── 連続地形（グラディウス風の上下壁）──────────────────────────────

_STRIP_THEMES: dict[str, dict] = {
    "fever_cave": {
        "base": (86, 24, 30),
        "dark": (58, 16, 22),
        "edge": (168, 62, 60),
        "glow": (198, 78, 68),
        "spot": (118, 38, 44),
    },
    "debris": {
        "base": (74, 76, 86),
        "dark": (32, 34, 44),
        "edge": (144, 150, 166),
        "glow": (95, 180, 220),
        "spot": (108, 112, 126),
    },
    "meme_static": {
        "base": (34, 62, 48),
        "dark": (10, 18, 18),
        "edge": (82, 174, 130),
        "glow": (92, 220, 180),
        "spot": (60, 120, 72),
    },
    "fortress": {
        "base": (64, 72, 86),
        "dark": (28, 34, 44),
        "edge": (120, 145, 172),
        "glow": (82, 165, 205),
        "spot": (88, 104, 124),
    },
    "shogi_void": {
        "base": (36, 30, 54),
        "dark": (14, 12, 24),
        "edge": (116, 96, 148),
        "glow": (168, 140, 220),
        "spot": (52, 44, 78),
    },
}
TERRAIN_STRIP_THEMES: tuple[str, ...] = tuple(_STRIP_THEMES.keys())


class TerrainStripSegment(pygame.sprite.Sprite):
    """連続地形の1セグメント。

    見た目はタイル状に描くが、衝突は矩形単位に保つ。
    """

    def __init__(
        self,
        world_x: float,
        y: float,
        w: int,
        h: int,
        *,
        side: str,
        theme: str,
        seed: int,
        index: int,
        destructible: bool = False,
        hp: int = 3,
        drop_chance: float = 0.0,
    ) -> None:
        super().__init__()
        self.world_x = float(world_x)
        self.y       = float(y)
        self.side    = side
        self.theme   = theme
        self.destructible = destructible
        self.max_hp = max(1, hp)
        self.hp = self.max_hp
        self.drop_chance = drop_chance
        self._w = w
        self._h = h
        self._seed = seed
        self._index = index
        self.image   = self._make_surface(
            w, h, side=side, theme=theme, seed=seed, index=index,
            destructible=destructible, damage_ratio=0.0,
        )
        self.rect    = self.image.get_rect(topleft=(int(world_x), int(y)))

    @staticmethod
    def _make_surface(
        w: int,
        h: int,
        *,
        side: str,
        theme: str,
        seed: int,
        index: int,
        destructible: bool = False,
        damage_ratio: float = 0.0,
    ) -> pygame.Surface:
        colors = _STRIP_THEMES.get(theme, _STRIP_THEMES["fever_cave"])
        base = colors["base"]
        dark = colors["dark"]
        edge = colors["edge"]
        glow = colors["glow"]
        spot = colors["spot"]
        rng = random.Random(seed * 1009 + index * 9176 + (0 if side == "top" else 53))

        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill(base)

        # 奥行きの暗部。
        if side == "top":
            pygame.draw.rect(surf, dark, (0, 0, w, max(3, h // 3)))
            edge_y = h - 1
        else:
            pygame.draw.rect(surf, dark, (0, max(0, h * 2 // 3), w, max(3, h // 3)))
            edge_y = 0

        # 有機的な凹凸と危険縁。
        pts = []
        edge_step = 16 if theme == "fever_cave" else 8
        max_jitter = min(7 if theme == "fever_cave" else 16, max(4, h // 3))
        for x in range(0, w + edge_step + 1, edge_step):
            jitter = rng.randint(0, max_jitter)
            y = h - jitter if side == "top" else jitter
            pts.append((x, y))
        if side == "top":
            poly = [(0, 0), (w, 0)] + [(x, y) for x, y in reversed(pts)]
            pygame.draw.polygon(surf, base, poly)
        else:
            poly = [(0, h), (w, h)] + list(reversed(pts))
            pygame.draw.polygon(surf, base, poly)
        if len(pts) >= 2:
            if theme == "fever_cave":
                pygame.draw.lines(surf, (*edge, 132), False, pts, 2)
                pygame.draw.lines(surf, (*glow, 46), False, pts, 1)
            else:
                pygame.draw.lines(surf, edge, False, pts, 3)
                pygame.draw.lines(surf, glow, False, pts, 1)

        # Fever cave は血管っぽい筋を強めに入れる。
        vein_count = max(2, (w * h) // 3600)
        for _ in range(vein_count):
            x0 = rng.randint(-10, w)
            y0 = rng.randint(6, max(7, h - 6))
            length = rng.randint(20, max(24, w // 2))
            wave = rng.randint(3, 9)
            pts2 = []
            for t in range(0, length, 8):
                x = x0 + t
                if 0 <= x <= w:
                    y = y0 + int(math.sin((t + index * 7) * 0.22) * wave)
                    pts2.append((x, max(3, min(h - 4, y))))
            if len(pts2) > 1:
                pygame.draw.lines(surf, spot, False, pts2, 2)

        # 斑点・細胞・岩肌のノイズ。
        for _ in range(max(4, (w * h) // 1200)):
            sx = rng.randint(2, max(2, w - 3))
            sy = rng.randint(2, max(2, h - 3))
            r = rng.randint(1, 4)
            col = spot if rng.random() < 0.7 else dark
            pygame.draw.circle(surf, col, (sx, sy), r)

        TerrainStripSegment._draw_theme_details(surf, rng, w, h, side, theme, colors, index)

        if destructible:
            # 破壊可能な薄膜は縁と亀裂を明るくし、撃てる壁だと読めるようにする。
            crack_col = (255, 180, 100)
            node_col = (255, 110, 70)
            crack_count = 3 + int(5 * max(0.0, min(1.0, damage_ratio)))
            for _ in range(crack_count):
                x = rng.randint(4, max(4, w - 5))
                y = rng.randint(8, max(8, h - 9))
                pts3 = [(x, y)]
                for _step in range(rng.randint(2, 4)):
                    x += rng.randint(-10, 12)
                    y += rng.randint(-8, 8)
                    pts3.append((max(2, min(w - 3, x)), max(3, min(h - 4, y))))
                pygame.draw.lines(surf, crack_col, False, pts3, 1)
            for _ in range(max(1, (w * h) // 5200)):
                sx = rng.randint(5, max(5, w - 6))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, node_col, (sx, sy), rng.randint(2, 4))

        # 内側エッジに薄い発光を足して、通路の輪郭を読みやすくする。
        glow_h = min(10 if theme == "fever_cave" else 16, max(4, h // 4))
        glow_alpha = 18 if theme == "fever_cave" else 55
        glow_surf = pygame.Surface((w, glow_h), pygame.SRCALPHA)
        for gy in range(glow_h):
            alpha = int(glow_alpha * (1.0 - gy / glow_h))
            glow_surf.fill((*glow, alpha), rect=(0, gy, w, 1))
        if side == "top":
            surf.blit(glow_surf, (0, max(0, edge_y - glow_h + 1)))
        else:
            surf.blit(pygame.transform.flip(glow_surf, False, True), (0, 0))

        return surf

    @staticmethod
    def _draw_theme_details(
        surf: pygame.Surface,
        rng: random.Random,
        w: int,
        h: int,
        side: str,
        theme: str,
        colors: dict,
        index: int,
    ) -> None:
        base = colors["base"]
        dark = colors["dark"]
        edge = colors["edge"]
        glow = colors["glow"]
        if theme == "meme_static":
            for x in range(8 + (index % 3) * 5, w, 22):
                y0 = rng.randint(8, max(8, h - 10))
                y1 = max(4, min(h - 5, y0 + rng.randint(-22, 22)))
                pygame.draw.line(surf, (*glow, 58), (x, y0), (min(w - 5, x + 14), y0), 1)
                pygame.draw.line(surf, (*edge, 44), (min(w - 5, x + 14), y0), (min(w - 5, x + 14), y1), 1)
                pygame.draw.rect(surf, (*glow, 58), (min(w - 8, x + 12), y1 - 2, 4, 4))
            for _ in range(max(1, (w * h) // 5200)):
                yy = rng.randint(6, max(6, h - 7))
                pygame.draw.rect(surf, (116, 240, 190, 38), (0, yy, w, 2))
        elif theme == "fortress":
            seam_col = tuple(max(0, c - 18) for c in dark)
            hi_col = tuple(min(255, c + 18) for c in edge)
            for x in range(0, w, 28):
                pygame.draw.line(surf, (*seam_col, 96), (x, 3), (x, h - 4), 1)
            for y in range(14 + (index % 2) * 8, h, 30):
                pygame.draw.line(surf, (*hi_col, 46), (4, y), (w - 5, y), 1)
            for _ in range(max(2, (w * h) // 2300)):
                sx = rng.randint(8, max(8, w - 9))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, (*hi_col, 88), (sx, sy), 2)
                pygame.draw.circle(surf, (*seam_col, 72), (sx + 1, sy + 1), 2)
            if h > 34 and index % 5 == 0:
                stripe_y = 8 if side == "bottom" else max(6, h - 18)
                for x in range(-10, w, 16):
                    pygame.draw.line(surf, (220, 175, 70, 70), (x, stripe_y + 10), (x + 10, stripe_y), 2)
        elif theme == "shogi_void":
            board_col = (174, 136, 94, 24)
            shadow_col = tuple(max(0, c - 4) for c in base)
            for x in range((index * 7) % 46, w, 46):
                pygame.draw.line(surf, (*shadow_col, 18), (x, 4), (x, h - 5), 1)
                pygame.draw.line(surf, board_col, (x + 1, 4), (x + 1, h - 5), 1)
            for y in range((index * 5) % 42, h, 42):
                pygame.draw.line(surf, (*shadow_col, 16), (4, y), (w - 5, y), 1)
                pygame.draw.line(surf, board_col, (4, y + 1), (w - 5, y + 1), 1)
            for _ in range(max(1, (w * h) // 3600)):
                sx = rng.randint(8, max(8, w - 9))
                sy = rng.randint(8, max(8, h - 9))
                pts = [(sx, sy)]
                for _step in range(3):
                    sx += rng.randint(-12, 12)
                    sy += rng.randint(-10, 10)
                    pts.append((max(3, min(w - 4, sx)), max(3, min(h - 4, sy))))
                pygame.draw.lines(surf, (190, 154, 104, 62), False, pts, 1)

    @property
    def surface_y(self) -> float:
        """通路に接している側のY座標。砲台の吸着やアイテム配置に使う。"""
        if self.side == "top":
            return self.y + self.rect.height
        return self.y

    def take_damage(self, amount: int) -> bool:
        """破壊されたら True。破壊不能地形は常に False。"""
        if not self.destructible:
            return False
        self.hp -= amount
        if self.hp <= 0:
            return True
        damage_ratio = 1.0 - (self.hp / self.max_hp)
        center = self.rect.center
        self.image = self._make_surface(
            self._w, self._h,
            side=self.side,
            theme=self.theme,
            seed=self._seed,
            index=self._index,
            destructible=True,
            damage_ratio=damage_ratio,
        )
        self.rect = self.image.get_rect(center=center)
        return False

    def update(self, dt: float, camera: "Camera") -> None:
        self.rect.topleft = (int(camera.to_screen_x(self.world_x)), int(self.y))

    def is_off_left(self, camera: "Camera") -> bool:
        return self.world_x + self.rect.width < camera.x


def make_terrain_strip(
    start_x: float,
    *,
    length: int,
    theme: str = "fever_cave",
    segment_w: int = 64,
    seed: int = 1,
    gap_min: int = 270,
    gap_max: int = 380,
    center_y: int = SCREEN_HEIGHT // 2,
    center_wave: int = 42,
    top_min: int = 38,
    bottom_min: int = 42,
    irregularity: int = 36,
    breakable_chance: float = 0.0,
    breakable_hp: int = 3,
    breakable_drop_chance: float = 0.0,
    profile: str = "normal",
) -> list[TerrainStripSegment]:
    """上下壁の連続地形をセグメント列として生成する。"""
    segments: list[TerrainStripSegment] = []
    count = max(1, math.ceil(length / segment_w))
    rng = random.Random(seed)
    gap_controls = [rng.uniform(0.0, 1.0) for _ in range(8)]
    center_controls = [rng.uniform(-1.0, 1.0) for _ in range(8)]

    def sample(points: list[float], p: float) -> float:
        pos = p * (len(points) - 1)
        idx = min(len(points) - 2, max(0, int(pos)))
        frac = pos - idx
        frac = frac * frac * (3.0 - 2.0 * frac)
        return points[idx] * (1.0 - frac) + points[idx + 1] * frac

    for i in range(count):
        wx = start_x + i * segment_w
        p = i / max(1, count - 1)
        gap_t = sample(gap_controls, p)
        gap = gap_min + int((gap_max - gap_min) * gap_t)
        center = center_y + int(sample(center_controls, p) * center_wave)
        center += int(math.sin(p * math.tau * 5.5 + seed * 0.13) * irregularity * 0.35)
        center += rng.randint(-irregularity, irregularity) // 4

        top_h = int(center - gap / 2)
        bottom_y = int(center + gap / 2)

        if profile == "mountain":
            mound = math.sin(math.pi * p)
            shoulder = 0.35 * math.sin(math.pi * p * 3.0 + seed * 0.17)
            height = max(90, int(center_wave * 1.9 + irregularity))
            top_h = top_min
            bottom_y = int(SCREEN_HEIGHT - bottom_min - height * max(0.0, mound + shoulder))
        elif profile == "ceiling":
            bulge = math.sin(math.pi * p)
            bite = 0.28 * math.sin(math.pi * p * 2.5 + seed * 0.11)
            depth = max(95, int(center_wave * 1.8 + irregularity))
            top_h = int(top_min + depth * max(0.0, bulge + bite))
            bottom_y = SCREEN_HEIGHT - bottom_min

        top_h = max(top_min, min(SCREEN_HEIGHT - bottom_min - gap_min, top_h))
        bottom_y = max(top_h + gap_min, min(SCREEN_HEIGHT - bottom_min, bottom_y))
        bottom_h = SCREEN_HEIGHT - bottom_y

        if top_h > 0:
            destructible = i > 6 and rng.random() < breakable_chance
            if destructible:
                protrusion_h = min(54, max(1, top_h - 8), max(18, top_h // 2))
                base_h = top_h - protrusion_h
                if base_h > 0:
                    segments.append(TerrainStripSegment(
                        wx, 0, segment_w, base_h,
                        side="top", theme=theme, seed=seed, index=i * 2,
                    ))
                segments.append(TerrainStripSegment(
                    wx, base_h, segment_w, protrusion_h,
                    side="top", theme=theme, seed=seed, index=i * 2 + 1,
                    destructible=True,
                    hp=breakable_hp,
                    drop_chance=breakable_drop_chance,
                ))
            else:
                segments.append(TerrainStripSegment(
                    wx, 0, segment_w, top_h,
                    side="top", theme=theme, seed=seed, index=i * 2,
                ))
        if bottom_h > 0:
            destructible = i > 6 and rng.random() < breakable_chance
            if destructible:
                protrusion_h = min(54, max(1, bottom_h - 8), max(18, bottom_h // 2))
                base_h = bottom_h - protrusion_h
                segments.append(TerrainStripSegment(
                    wx, bottom_y, segment_w, protrusion_h,
                    side="bottom", theme=theme, seed=seed, index=i * 2 + 1,
                    destructible=True,
                    hp=breakable_hp,
                    drop_chance=breakable_drop_chance,
                ))
                if base_h > 0:
                    segments.append(TerrainStripSegment(
                        wx, bottom_y + protrusion_h, segment_w, base_h,
                        side="bottom", theme=theme, seed=seed, index=i * 2,
                    ))
            else:
                segments.append(TerrainStripSegment(
                    wx, bottom_y, segment_w, bottom_h,
                    side="bottom", theme=theme, seed=seed, index=i * 2,
                ))
    return segments
