"""地形（壁・障害物・デブリ）。ワールド座標で配置し、カメラスクロールで左へ流れる。

自機が接触するとダメージ。砲台（EnemyTurret）の設置足場としても用いる。
ステージごとに `kind` と配置を変えて特色を出す（宇宙=debris まばら / 岩石=wall・rock 多め）。
"""
from __future__ import annotations
import math
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any
import pygame
from src.core.constants import SCREEN_HEIGHT

if TYPE_CHECKING:
    from src.core.camera import Camera

# kind 別の基調色 (本体, 縁)
_KIND_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "wall":   ((70, 72, 82),  (110, 114, 128)),   # 金属/コンクリの壁
    "rock":   ((96, 78, 60),  (140, 116, 86)),    # 岩石
    "debris": ((84, 86, 96),  (130, 134, 150)),   # 宇宙デブリ
    "data_block": ((10, 16, 18), (38, 82, 70)),
    "fortress_block": ((42, 49, 55), (86, 96, 102)),
    "clot":   ((126, 24, 34), (230, 82, 76)),
}
_STAGE3_TERRAIN_SHEET_PATH = Path(__file__).parent.parent.parent / "assets" / "graphic" / "stage3_fortress_terrain_sheet.png"
_STAGE3_TERRAIN_SHEET: pygame.Surface | None = None


def _load_stage3_terrain_sheet() -> pygame.Surface | None:
    global _STAGE3_TERRAIN_SHEET
    if _STAGE3_TERRAIN_SHEET is not None:
        return _STAGE3_TERRAIN_SHEET
    try:
        _STAGE3_TERRAIN_SHEET = pygame.image.load(_STAGE3_TERRAIN_SHEET_PATH)
    except (FileNotFoundError, pygame.error):
        return None
    return _STAGE3_TERRAIN_SHEET


def _stage3_material_surface(w: int, h: int, *, seed: int, role: str) -> pygame.Surface:
    sheet = _load_stage3_terrain_sheet()
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((12, 15, 18))
    if sheet is None:
        return surf

    sw, sh = sheet.get_size()
    bands = {
        "strip": ((0.02, 0.17), (0.18, 0.48), (0.50, 0.74), (0.75, 0.97)),
        "block": ((0.18, 0.48), (0.50, 0.74), (0.75, 0.97)),
    }.get(role, ((0.18, 0.48),))
    rng = random.Random(seed)
    tile_w = max(36, min(148, w))
    tile_h = max(40, min(128, h))

    for dy in range(0, h, tile_h):
        dh = min(tile_h, h - dy)
        band_start, band_end = bands[(dy // tile_h + seed) % len(bands)]
        y0 = int(sh * band_start)
        band_h = max(1, int(sh * (band_end - band_start)))
        for dx in range(0, w, tile_w):
            dw = min(tile_w, w - dx)
            src_w = min(sw, max(80, dw * 3))
            src_h = min(band_h, max(80, dh * 3))
            span_x = max(1, sw - src_w)
            span_y = max(1, band_h - src_h)
            sx = (seed * 37 + dx * 5 + rng.randint(0, span_x - 1)) % span_x
            sy = y0 + ((seed * 17 + dy * 3 + rng.randint(0, span_y - 1)) % span_y)
            tile = sheet.subsurface(pygame.Rect(sx, sy, src_w, src_h)).copy()
            if tile.get_size() != (dw, dh):
                tile = pygame.transform.smoothscale(tile, (dw, dh))
            surf.blit(tile, (dx, dy))

    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 34 if role == "strip" else 22))
    surf.blit(veil, (0, 0))
    return surf


def _stage3_piece_fill(image: pygame.Surface, w: int, h: int) -> pygame.Surface:
    sw, sh = image.get_size()
    scale = max(w / max(1, sw), h / max(1, sh))
    scaled_size = (max(w, int(sw * scale)), max(h, int(sh * scale)))
    scaled = pygame.transform.smoothscale(image, scaled_size)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.blit(scaled, ((w - scaled.get_width()) // 2, (h - scaled.get_height()) // 2))
    return surf


def _stage3_rect_material_surface(w: int, h: int, *, seed: int, require_top: bool) -> pygame.Surface | None:
    try:
        from src.entities.stage3_composer_terrain import load_stage3_composer_pieces
    except Exception:
        return None
    try:
        pieces_by_group = load_stage3_composer_pieces()
    except Exception:
        return None

    aspect = w / max(1, h)
    if require_top:
        if h > w * 1.35:
            groups = ("block_tall", "block_square", "block_wide")
        elif w > h * 1.55:
            groups = ("block_wide", "strip_top", "block_square")
        else:
            groups = ("block_square", "block_wide", "block_tall")
    elif h > w * 1.35:
        groups = ("block_tall", "block_square")
    elif w > h * 1.55:
        groups = ("block_wide", "block_square")
    else:
        groups = ("block_square", "block_tall", "block_wide")
    candidates = [
        piece
        for group in groups
        for piece in pieces_by_group.get(group, [])
    ]
    if not candidates:
        return None

    ranked = sorted(
        candidates,
        key=lambda piece: (
            abs((piece.image.get_width() / max(1, piece.image.get_height())) - aspect),
            abs(piece.image.get_width() - w) + abs(piece.image.get_height() - h),
        ),
    )
    piece = ranked[seed % min(4, len(ranked))]
    surf = _stage3_piece_fill(piece.image, w, h)
    if require_top:
        top_candidates = pieces_by_group.get("block_wide", []) or pieces_by_group.get("strip_top", [])
        if top_candidates:
            top_piece = top_candidates[(seed >> 3) % min(4, len(top_candidates))]
            cap_h = min(h, max(34, min(92, int(h * 0.42))))
            cap = _stage3_piece_fill(top_piece.image, w, cap_h)
            surf.blit(cap, (0, 0))
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 24))
    surf.blit(veil, (0, 0))
    return surf


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
        self._surface_anchor = "ceiling" if self.y <= 1.0 else "floor"
        self.image   = self._make_surface(
            w, h, kind,
            destructible=destructible,
            fixed_drop=fixed_drop,
            surface_anchor=self._surface_anchor,
        )
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
        surface_anchor: str = "floor",
    ) -> pygame.Surface:
        if kind == "clot":
            return Terrain._make_clot_surface(
                w, h,
                destructible=destructible,
                damage_ratio=damage_ratio,
                fixed_drop=fixed_drop,
            )
        if kind == "data_block":
            return Terrain._make_data_block_surface(
                w, h,
                destructible=destructible,
                damage_ratio=damage_ratio,
                fixed_drop=fixed_drop,
            )
        if kind == "fortress_block":
            return Terrain._make_fortress_block_surface(
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
    def _make_fortress_block_surface(
        w: int,
        h: int,
        *,
        destructible: bool = False,
        damage_ratio: float = 0.0,
        fixed_drop: str | None = None,
        surface_anchor: str = "floor",
    ) -> pygame.Surface:
        seed = (w * 33013) ^ (h * 77041) ^ (0xB10C if destructible else 0xF077)
        rng = random.Random(seed)
        surf = _stage3_rect_material_surface(
            w, h, seed=seed, require_top=surface_anchor != "ceiling",
        ) or _stage3_material_surface(
            w, h, seed=seed, role="block",
        )

        light_count = max(1, (w * h) // 8200)
        for _ in range(light_count):
            sx = rng.randint(8, max(8, w - 10))
            sy = rng.randint(8, max(8, h - 10))
            pygame.draw.rect(surf, (174, 78, 108), (sx, sy, rng.randint(2, 4), rng.randint(1, 3)))
            if rng.random() < 0.45:
                pygame.draw.rect(surf, (80, 210, 170), (max(0, sx - 4), sy + 1, rng.randint(1, 3), 1))

        if destructible:
            damage = max(0.0, min(1.0, damage_ratio))
            for _ in range(4 + int(damage * 7)):
                x = rng.randint(6, max(6, w - 7))
                y = rng.randint(7, max(7, h - 8))
                pts = [(x, y)]
                for _step in range(rng.randint(2, 4)):
                    x += rng.randint(-12, 12)
                    y += rng.randint(-10, 10)
                    pts.append((max(3, min(w - 4, x)), max(3, min(h - 4, y))))
                pygame.draw.lines(surf, (190, 132, 104), False, pts, 1)
            for _ in range(max(1, (w * h) // 6400)):
                sx = rng.randint(7, max(7, w - 8))
                sy = rng.randint(7, max(7, h - 8))
                pygame.draw.circle(surf, (210, 96, 92), (sx, sy), rng.randint(2, 4))

        Terrain._draw_reward_core(surf, w, h, fixed_drop, damage_ratio=damage_ratio)
        return surf

    @staticmethod
    def _make_data_block_surface(
        w: int,
        h: int,
        *,
        destructible: bool = False,
        damage_ratio: float = 0.0,
        fixed_drop: str | None = None,
    ) -> pygame.Surface:
        rng = random.Random((w * 61001) ^ (h * 97003) ^ 0xDADA)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((2, 5, 7, 252))
        pygame.draw.rect(surf, (0, 1, 2, 230), (0, 0, w, h), 2)

        panel_count = max(4, (w * h) // 1200)
        for _ in range(panel_count):
            px = rng.randint(2, max(2, w - 12))
            py = rng.randint(2, max(2, h - 10))
            pw = rng.randint(8, max(10, min(42, w - px)))
            ph = rng.randint(5, max(7, min(28, h - py)))
            panel = pygame.Rect(px, py, pw, ph)
            col = rng.choice(((4, 10, 12, 112), (8, 15, 16, 88), (1, 4, 6, 132)))
            pygame.draw.rect(surf, col, panel)
            if rng.random() < 0.22:
                pygame.draw.rect(surf, (26, 70, 60, 28), panel, 1)

        for _ in range(max(2, (w * h) // 2600)):
            sx = rng.randint(5, max(5, w - 6))
            sy = rng.randint(5, max(5, h - 6))
            pygame.draw.rect(surf, (74, 180, 146, rng.randint(18, 38)), (sx, sy, rng.randint(1, 3), 1))

        for _ in range(max(2, w // 32)):
            x = rng.randint(2, max(2, w - 4))
            y = rng.choice((0, h - 1))
            drip_h = rng.randint(5, max(6, min(22, h // 2)))
            if y == 0:
                rect = pygame.Rect(x, 0, rng.randint(1, 3), drip_h)
            else:
                rect = pygame.Rect(x, max(0, h - drip_h), rng.randint(1, 3), drip_h)
            pygame.draw.rect(surf, (0, 2, 3, 170), rect)

        if destructible:
            damage = max(0.0, min(1.0, damage_ratio))
            for _ in range(3 + int(damage * 6)):
                x = rng.randint(7, max(7, w - 8))
                y = rng.randint(7, max(7, h - 8))
                pts = [(x, y)]
                for _step in range(rng.randint(2, 4)):
                    x += rng.randint(-12, 12)
                    y += rng.randint(-10, 10)
                    pts.append((max(3, min(w - 4, x)), max(3, min(h - 4, y))))
                pygame.draw.lines(surf, (84, 156, 130, 92), False, pts, 1)
            for _ in range(max(1, (w * h) // 6000)):
                sx = rng.randint(8, max(8, w - 9))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, (130, 78, 112, 110), (sx, sy), rng.randint(2, 4))

        Terrain._draw_reward_core(surf, w, h, fixed_drop, damage_ratio=damage_ratio)
        return surf

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
            surface_anchor=self._surface_anchor,
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
AUTHORED_TERRAIN_TYPES: frozenset[str] = frozenset({"AuthoredTerrain", "TerrainPath"})
RANDOM_TERRAIN_TYPES: frozenset[str] = frozenset({"TerrainStrip", "cave_section", "corridor"})
CONTINUOUS_TERRAIN_TYPES: frozenset[str] = AUTHORED_TERRAIN_TYPES | RANDOM_TERRAIN_TYPES


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
        if theme == "meme_static":
            return TerrainStripSegment._make_meme_static_surface(
                w,
                h,
                side=side,
                rng=rng,
                index=index,
                destructible=destructible,
                damage_ratio=damage_ratio,
            )
        if theme == "fortress":
            return TerrainStripSegment._make_fortress_surface(
                w,
                h,
                side=side,
                rng=rng,
                index=index,
                destructible=destructible,
                damage_ratio=damage_ratio,
            )

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
    def _make_fortress_surface(
        w: int,
        h: int,
        *,
        side: str,
        rng: random.Random,
        index: int,
        destructible: bool = False,
        damage_ratio: float = 0.0,
    ) -> pygame.Surface:
        seed = (index * 1009) ^ (w * 37) ^ (h * 131) ^ (0x71 if side == "top" else 0xE3)
        surf = _stage3_material_surface(w, h, seed=seed, role="strip")

        cap_h = max(8, min(24, h // 4))
        cap = pygame.Surface((w, cap_h), pygame.SRCALPHA)
        cap.fill((0, 2, 4, 118))
        if side == "top":
            surf.blit(cap, (0, 0))
        else:
            surf.blit(cap, (0, max(0, h - cap_h)))

        shadow_h = min(18, max(8, h // 5))
        shadow = pygame.Surface((w, shadow_h), pygame.SRCALPHA)
        for sy in range(shadow_h):
            alpha = int(38 * (1.0 - sy / shadow_h))
            shadow.fill((0, 0, 0, alpha), rect=(0, sy, w, 1))
        if side == "top":
            surf.blit(pygame.transform.flip(shadow, False, True), (0, max(0, h - shadow_h)))
        else:
            surf.blit(shadow, (0, 0))

        for _ in range(max(1, (w * h) // 5200)):
            sx = rng.randint(4, max(4, w - 5))
            sy = rng.randint(4, max(4, h - 5))
            pygame.draw.rect(surf, (184, 78, 108), (sx, sy, rng.randint(2, 4), rng.randint(1, 3)))

        if destructible:
            damage = max(0.0, min(1.0, damage_ratio))
            for _ in range(3 + int(damage * 6)):
                x = rng.randint(5, max(5, w - 6))
                y = rng.randint(6, max(6, h - 7))
                pts2 = [(x, y)]
                for _step in range(rng.randint(2, 4)):
                    x += rng.randint(-11, 11)
                    y += rng.randint(-8, 8)
                    pts2.append((max(2, min(w - 3, x)), max(3, min(h - 4, y))))
                pygame.draw.lines(surf, (192, 136, 106), False, pts2, 1)
            for _ in range(max(1, (w * h) // 5600)):
                sx = rng.randint(5, max(5, w - 6))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, (214, 98, 96), (sx, sy), rng.randint(2, 4))

        return surf

    @staticmethod
    def _make_meme_static_surface(
        w: int,
        h: int,
        *,
        side: str,
        rng: random.Random,
        index: int,
        destructible: bool = False,
        damage_ratio: float = 0.0,
    ) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((1, 4, 6, 254))

        for _ in range(max(4, (w * h) // 1250)):
            px = rng.randint(0, max(0, w - 8))
            py = rng.randint(0, max(0, h - 8))
            pw = rng.randint(8, max(10, min(46, w - px)))
            ph = rng.randint(6, max(8, min(34, h - py)))
            rect = pygame.Rect(px, py, pw, ph)
            pygame.draw.rect(surf, rng.choice(((0, 2, 4, 164), (5, 10, 12, 118), (11, 18, 18, 72))), rect)
            if rng.random() < 0.16:
                pygame.draw.rect(surf, (28, 72, 62, 26), rect, 1)

        edge_step = 12
        max_jitter = min(20, max(5, h // 4))
        pts = []
        for x in range(0, w + edge_step + 1, edge_step):
            jitter = rng.randint(0, max_jitter)
            y = h - jitter if side == "top" else jitter
            pts.append((x, y))
        if len(pts) >= 2:
            pygame.draw.lines(surf, (0, 1, 2, 240), False, pts, 6)
            pygame.draw.lines(surf, (38, 92, 78, 62), False, pts, 1)

        for _ in range(max(3, w // 22)):
            sx = rng.randint(2, max(2, w - 4))
            if side == "top":
                sy = rng.randint(max(0, h - max_jitter - 18), max(0, h - 3))
                rect = pygame.Rect(sx, sy, rng.randint(1, 3), rng.randint(5, 18))
            else:
                sy = rng.randint(0, min(h - 3, max_jitter + 12))
                rect = pygame.Rect(sx, sy, rng.randint(1, 3), rng.randint(5, 18))
            pygame.draw.rect(surf, (0, 2, 3, 170), rect)

        for _ in range(max(2, (w * h) // 2600)):
            sx = rng.randint(3, max(3, w - 4))
            sy = rng.randint(3, max(3, h - 4))
            pygame.draw.rect(surf, (70, 172, 140, rng.randint(14, 32)), (sx, sy, rng.randint(1, 3), 1))

        if destructible:
            damage = max(0.0, min(1.0, damage_ratio))
            for _ in range(3 + int(damage * 6)):
                x = rng.randint(5, max(5, w - 6))
                y = rng.randint(6, max(6, h - 7))
                pts2 = [(x, y)]
                for _step in range(rng.randint(2, 4)):
                    x += rng.randint(-10, 10)
                    y += rng.randint(-8, 8)
                    pts2.append((max(2, min(w - 3, x)), max(3, min(h - 4, y))))
                pygame.draw.lines(surf, (76, 146, 122, 88), False, pts2, 1)
            for _ in range(max(1, (w * h) // 5200)):
                sx = rng.randint(5, max(5, w - 6))
                sy = rng.randint(8, max(8, h - 9))
                pygame.draw.circle(surf, (128, 72, 108, 112), (sx, sy), rng.randint(2, 4))

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


def make_terrain_segments_from_event(
    event: dict[str, Any],
    start_x: float,
    *,
    default_seed: int = 1,
) -> list[TerrainStripSegment]:
    terrain_type = str(event.get("type", ""))
    if terrain_type in AUTHORED_TERRAIN_TYPES:
        return make_authored_terrain(
            start_x,
            top=event.get("top", []),
            bottom=event.get("bottom", []),
            length=int(event["length"]) if "length" in event else None,
            theme=str(event.get("theme", "fever_cave")),
            segment_w=int(event.get("segment_w", 64)),
            seed=int(event.get("seed", default_seed)),
            min_gap=int(event.get("min_gap", 160)),
            curve=str(event.get("curve", "smooth")),
        )
    if terrain_type in RANDOM_TERRAIN_TYPES:
        return make_terrain_strip(
            start_x,
            length=int(event.get("length", 3600)),
            theme=event.get("theme", "fever_cave"),
            segment_w=int(event.get("segment_w", 64)),
            seed=int(event.get("seed", default_seed)),
            gap_min=int(event.get("gap_min", 270)),
            gap_max=int(event.get("gap_max", 380)),
            center_y=int(event.get("center_y", SCREEN_HEIGHT // 2)),
            center_wave=int(event.get("center_wave", 42)),
            top_min=int(event.get("top_min", 38)),
            bottom_min=int(event.get("bottom_min", 42)),
            irregularity=int(event.get("irregularity", 36)),
            breakable_chance=float(event.get("breakable_chance", 0.0)),
            breakable_hp=int(event.get("breakable_hp", 3)),
            breakable_drop_chance=float(event.get("breakable_drop_chance", 0.0)),
            profile=str(event.get("profile", "normal")),
        )
    raise ValueError(f"unsupported continuous terrain type: {terrain_type}")


def make_authored_terrain(
    start_x: float,
    *,
    top: Any,
    bottom: Any,
    length: int | None = None,
    theme: str = "fever_cave",
    segment_w: int = 64,
    seed: int = 1,
    min_gap: int = 160,
    curve: str = "smooth",
    height: int = SCREEN_HEIGHT,
) -> list[TerrainStripSegment]:
    top_points = _terrain_control_points(top, label="top")
    bottom_points = _terrain_control_points(bottom, label="bottom")
    end_x = max(top_points[-1][0], bottom_points[-1][0])
    total_length = max(1, int(length if length is not None else end_x))
    segment_width = max(1, int(segment_w))
    count = max(1, math.ceil(total_length / segment_width))
    segments: list[TerrainStripSegment] = []

    for i in range(count):
        local_x = i * segment_width
        width = min(segment_width, total_length - local_x)
        if width <= 0:
            continue
        sample_x = min(total_length, local_x + width * 0.5)
        top_y = int(round(_sample_terrain_boundary(top_points, sample_x, curve=curve)))
        bottom_y = int(round(_sample_terrain_boundary(bottom_points, sample_x, curve=curve)))
        top_y, bottom_y = _clamp_authored_corridor(top_y, bottom_y, min_gap=min_gap, height=height)
        world_x = start_x + local_x

        if top_y > 0:
            segments.append(TerrainStripSegment(
                world_x,
                0,
                width,
                top_y,
                side="top",
                theme=theme,
                seed=seed,
                index=i * 2,
            ))
        if bottom_y < height:
            segments.append(TerrainStripSegment(
                world_x,
                bottom_y,
                width,
                height - bottom_y,
                side="bottom",
                theme=theme,
                seed=seed,
                index=i * 2 + 1,
            ))
    return segments


def _terrain_control_points(raw: Any, *, label: str) -> list[tuple[float, float]]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(f"AuthoredTerrain.{label} requires at least two control points")
    points: list[tuple[float, float]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            if "x" not in item or "y" not in item:
                raise ValueError(f"AuthoredTerrain.{label}[{i}] requires x and y")
            x = float(item["x"])
            y = float(item["y"])
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x = float(item[0])
            y = float(item[1])
        else:
            raise ValueError(f"AuthoredTerrain.{label}[{i}] must be [x, y] or {{x, y}}")
        points.append((x, y))
    points.sort(key=lambda p: p[0])
    for prev, cur in zip(points, points[1:]):
        if cur[0] <= prev[0]:
            raise ValueError(f"AuthoredTerrain.{label} control point x values must be unique")
    return points


def _sample_terrain_boundary(points: list[tuple[float, float]], x: float, *, curve: str) -> float:
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / max(1.0, x1 - x0)
            if curve != "linear":
                t = t * t * (3.0 - 2.0 * t)
            return y0 * (1.0 - t) + y1 * t
    return points[-1][1]


def _clamp_authored_corridor(
    top_y: int,
    bottom_y: int,
    *,
    min_gap: int,
    height: int,
) -> tuple[int, int]:
    top_y = max(0, min(height, top_y))
    bottom_y = max(0, min(height, bottom_y))
    gap = max(1, int(min_gap))
    if bottom_y - top_y >= gap:
        return top_y, bottom_y
    center = (top_y + bottom_y) // 2
    top_y = max(0, center - gap // 2)
    bottom_y = min(height, top_y + gap)
    if bottom_y - top_y < gap:
        top_y = max(0, bottom_y - gap)
    return top_y, bottom_y
