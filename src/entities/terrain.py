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
    ) -> None:
        super().__init__()
        self.world_x = float(world_x)
        self.y       = float(y)
        self.kind    = kind
        self.destructible = destructible
        self.max_hp = max(1, hp)
        self.hp = self.max_hp
        self.drop_chance = drop_chance
        self._w = w
        self._h = h
        self.image   = self._make_surface(w, h, kind, destructible=destructible)
        self.rect    = self.image.get_rect(topleft=(int(world_x), int(y)))

    @staticmethod
    def _make_surface(
        w: int,
        h: int,
        kind: str,
        *,
        destructible: bool = False,
        damage_ratio: float = 0.0,
    ) -> pygame.Surface:
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
        return surf

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
        "base": (92, 22, 28),
        "dark": (38, 8, 12),
        "edge": (210, 70, 62),
        "glow": (255, 105, 70),
        "spot": (130, 34, 42),
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
        "edge": (104, 188, 122),
        "glow": (130, 255, 150),
        "spot": (60, 120, 72),
    },
    "fortress": {
        "base": (64, 72, 86),
        "dark": (28, 34, 44),
        "edge": (130, 148, 174),
        "glow": (90, 180, 210),
        "spot": (88, 104, 124),
    },
    "shogi_void": {
        "base": (36, 30, 54),
        "dark": (14, 12, 24),
        "edge": (102, 86, 150),
        "glow": (190, 170, 255),
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
        for x in range(0, w + 9, 8):
            jitter = rng.randint(0, min(16, max(4, h // 3)))
            y = h - jitter if side == "top" else jitter
            pts.append((x, y))
        if side == "top":
            poly = [(0, 0), (w, 0)] + [(x, y) for x, y in reversed(pts)]
            pygame.draw.polygon(surf, base, poly)
        else:
            poly = [(0, h), (w, h)] + list(reversed(pts))
            pygame.draw.polygon(surf, base, poly)
        if len(pts) >= 2:
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
        glow_h = min(16, max(5, h // 4))
        glow_surf = pygame.Surface((w, glow_h), pygame.SRCALPHA)
        for gy in range(glow_h):
            alpha = int(55 * (1.0 - gy / glow_h))
            glow_surf.fill((*glow, alpha), rect=(0, gy, w, 1))
        if side == "top":
            surf.blit(glow_surf, (0, max(0, edge_y - glow_h + 1)))
        else:
            surf.blit(pygame.transform.flip(glow_surf, False, True), (0, 0))

        return surf

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
