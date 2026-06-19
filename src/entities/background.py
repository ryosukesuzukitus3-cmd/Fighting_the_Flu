from __future__ import annotations
import math
import random
from pathlib import Path
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT

_STAGE2_BG_PATH = Path(__file__).parent.parent.parent / "assets" / "graphic" / "stage2_cyber_static_bg.png"


class _StarLayer:
    def __init__(self, count: int, speed_factor: float, color: tuple, size: int) -> None:
        self.speed_factor = speed_factor
        self.color = color
        self.size = size
        self.stars = [
            (random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT))
            for _ in range(count)
        ]

    def draw(self, screen: pygame.Surface, camera_x: float) -> None:
        offset = int(camera_x * self.speed_factor)
        for sx, sy in self.stars:
            x = (sx - offset) % SCREEN_WIDTH
            pygame.draw.circle(screen, self.color, (x, sy), self.size)


# ステージ別ベース色（テーマの下地）
_BASE_COLOR = {
    1: (16,  6,  8),    # 発熱回廊（暗赤）
    2: (8,   8,  14),   # ミーム汚染（暗）
    3: (8,  12,  20),   # 婚活・労働（寒色）
    4: (6,   5,  12),   # 棋理深淵（暗紫）
}


class ScrollingBackground:
    """ステージテーマ別のスクロール背景。

    星空レイヤーを下地に、stage_id ごとの手続き的テーマ図形を重ねる。
    新規画像は使わず軽量に描画する（視差は camera_x ベース）。
    """

    def __init__(self, stage_id: int = 0) -> None:
        self.stage_id = stage_id
        # 星空は薄めに（テーマを前面に出すため）
        self._layers = [
            _StarLayer(40,  0.1, (50,  50,  80),  1),
            _StarLayer(24,  0.3, (90,  90, 130),  1),
            _StarLayer(10,  0.6, (150, 150, 190), 2),
        ]
        self._time = 0.0
        self._ribs: list = []
        self._stage1_far_cells: list = []
        self._stage1_near_cells: list = []
        self._stage1_membranes: list = []
        self._stage2_fragments: list = []
        self._stage2_bg: pygame.Surface | None = None
        self._stage1_lumen: pygame.Surface | None = None
        self._theme_init(stage_id)

    # ── テーマ要素の事前生成（ランダム配置を固定）────────────────
    def _theme_init(self, sid: int) -> None:
        rnd = random.Random(sid * 1000 + 7)
        self._cells: list = []
        if sid == 1:
            # Distant blood cells. Tuple: x, y, rx, ry, angle, parallax, phase.
            self._stage1_far_cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(24, SCREEN_HEIGHT - 24),
                 rnd.uniform(30, 72), rnd.uniform(10, 24), rnd.uniform(-0.75, 0.75),
                 rnd.uniform(0.015, 0.055), rnd.uniform(0, 6.28), rnd.uniform(26, 46))
                for _ in range(16)
            ]
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(0, SCREEN_HEIGHT),
                 rnd.uniform(18, 42), rnd.uniform(9, 19), rnd.uniform(-0.55, 0.55),
                 rnd.uniform(0.08, 0.18), rnd.uniform(0, 6.28), rnd.uniform(52, 78))
                for _ in range(22)
            ]
            self._stage1_near_cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(42, SCREEN_HEIGHT - 42),
                 rnd.uniform(54, 110), rnd.uniform(16, 34), rnd.uniform(-0.7, 0.7),
                 rnd.uniform(0.20, 0.34), rnd.uniform(0, 6.28), rnd.uniform(22, 38))
                for _ in range(8)
            ]
            self._stage1_membranes = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(120, 240), rnd.uniform(0.025, 0.075),
                 rnd.uniform(0, 6.28), rnd.uniform(0.72, 1.15))
                for _ in range(8)
            ]
            # 洞窟奥の縦ひだ。地形の手前に出すぎないよう低コントラストにする。
            self._ribs = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(26, 64), rnd.uniform(0.08, 0.18),
                 rnd.uniform(0, 6.28))
                for _ in range(9)
            ]
        elif sid == 2:
            # 走査ノイズ帯（y, 高さ, 速度, 位相）
            self._cells = [
                (rnd.uniform(0, SCREEN_HEIGHT), rnd.uniform(2, 6),
                 rnd.uniform(0.15, 0.4), rnd.uniform(0, 6.28))
                for _ in range(10)
            ]
            self._stage2_fragments = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(48, SCREEN_HEIGHT - 52),
                 rnd.uniform(12, 54), rnd.uniform(5, 18), rnd.uniform(0.10, 0.28),
                 rnd.uniform(24, 62))
                for _ in range(26)
            ]
        elif sid == 3:
            # 婚活UIカード矩形（x, y, w, h, 速度）
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(30, SCREEN_HEIGHT - 90),
                 rnd.uniform(70, 130), rnd.uniform(40, 64), rnd.uniform(0.12, 0.3))
                for _ in range(8)
            ]
        elif sid == 4:
            # 駒グリフ（x, y, 速度, 文字）
            glyphs = "歩香桂銀金角飛王"
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(30, SCREEN_HEIGHT - 40),
                 rnd.uniform(0.1, 0.3), rnd.choice(glyphs))
                for _ in range(10)
            ]
            self._piece_font = None

    # ── 描画 ─────────────────────────────────────────────────────
    def draw(self, screen: pygame.Surface, camera_x: float) -> None:
        screen.fill(_BASE_COLOR.get(self.stage_id, (5, 5, 20)))
        if self.stage_id != 1:
            for layer in self._layers:
                layer.draw(screen, camera_x)
        # フレーム毎に時間を進める（静止時でもテーマを動かす）
        self._time += 1.0 / 60.0
        if   self.stage_id == 1: self._draw_vessel(screen, camera_x)
        elif self.stage_id == 2: self._draw_meme(screen, camera_x)
        elif self.stage_id == 3: self._draw_konkatsu(screen, camera_x)
        elif self.stage_id == 4: self._draw_shogi(screen, camera_x)

    # ── Stage1 発熱回廊（血管・血球）─────────────────────────────
    def _draw_vessel(self, screen: pygame.Surface, camera_x: float) -> None:
        t = self._time
        self._draw_vessel_depth(screen, camera_x, t)
        for cell in self._stage1_far_cells:
            self._draw_blood_cell_layer(screen, camera_x, t, cell, 1.0)

        # 奥に流れる発熱洞窟のひだ。TerrainStrip と重なって「回廊」に見せる。
        rib = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for (cx, w, sf, ph) in self._ribs:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 160) - 80
            amp = 18 + math.sin(t * 0.9 + ph) * 8
            pts_l = []
            pts_r = []
            for y in range(-40, SCREEN_HEIGHT + 80, 48):
                drift = math.sin(y * 0.018 + t * 0.45 + ph) * amp
                pts_l.append((int(x + drift), y))
                pts_r.append((int(x + w + drift * 0.55), y))
            pygame.draw.polygon(rib, (70, 18, 24, 42), pts_l + list(reversed(pts_r)))
            pygame.draw.lines(rib, (132, 38, 42, 24), False, pts_l, 1)
            pygame.draw.lines(rib, (108, 28, 34, 20), False, pts_r, 1)
        screen.blit(rib, (0, 0))

        # 管腔（ルーメン）の奥行き。中央を沈ませて血管トンネルの深さを出し、
        # 手前の血球・敵・弾のコントラストを上げる（壁側はそのまま明るく残す）。
        screen.blit(self._stage1_lumen_surface(), (0, 0))

        # 熱の霞（弱め）。
        haze_alpha = int(10 + 8 * (0.5 + 0.5 * math.sin(t * 1.5)))
        haze = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        haze.fill((120, 22, 18, haze_alpha))
        screen.blit(haze, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # うねる血管ライン（2本）
        vessel_lines = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for k, (base_y, col, hi_col) in enumerate((
            (SCREEN_HEIGHT * 0.32, (120, 34, 40, 42), (210, 72, 64, 18)),
            (SCREEN_HEIGHT * 0.7,  (104, 28, 34, 36), (190, 62, 58, 14)),
        )):
            pts = []
            for x in range(0, SCREEN_WIDTH + 20, 40):
                y = base_y + math.sin(x * 0.012 + t * 0.8 + k) * 26
                pts.append((x, int(y)))
            if len(pts) >= 2:
                pygame.draw.lines(vessel_lines, col, False, pts, 3)
                pygame.draw.lines(vessel_lines, hi_col, False, pts, 1)
        screen.blit(vessel_lines, (0, 0))
        # 脈打つ血球
        pulse = 0.5 + 0.5 * math.sin(t * 2.0)
        for cell in self._cells:
            self._draw_blood_cell_layer(screen, camera_x, t, cell, 0.92 + 0.10 * pulse)
        for cell in self._stage1_near_cells:
            self._draw_blood_cell_layer(screen, camera_x, t, cell, 1.02 + 0.08 * pulse)

    def _stage1_lumen_surface(self) -> pygame.Surface:
        """血管トンネルの深部を表す中央の暗がり（静的・キャッシュ）。"""
        if self._stage1_lumen is not None:
            return self._stage1_lumen
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        cy = SCREEN_HEIGHT * 0.52
        spread = SCREEN_HEIGHT * 0.30
        for y in range(SCREEN_HEIGHT):
            d = math.exp(-((y - cy) / spread) ** 2)
            a = int(64 * d)
            if a > 0:
                surf.fill((6, 0, 3, a), (0, y, SCREEN_WIDTH, 1))
        self._stage1_lumen = surf
        return surf

    def _draw_vessel_depth(self, screen: pygame.Surface, camera_x: float, t: float) -> None:
        depth = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for (cx, width, sf, ph, stretch) in self._stage1_membranes:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + width + 160) - width - 80
            pts_l = []
            pts_r = []
            for y in range(-32, SCREEN_HEIGHT + 64, 32):
                sway = math.sin(y * 0.012 * stretch + t * 0.28 + ph) * 18
                taper = math.sin((y + ph * 24) * 0.021) * 10
                pts_l.append((int(x + sway), y))
                pts_r.append((int(x + width + sway * 0.38 + taper), y))
            pygame.draw.polygon(depth, (118, 28, 33, 30), pts_l + list(reversed(pts_r)))
            pygame.draw.lines(depth, (205, 68, 62, 20), False, pts_l, 1)
            pygame.draw.lines(depth, (112, 28, 34, 18), False, pts_r, 1)

        for y_base, speed, alpha in ((118, 0.035, 24), (292, 0.055, 22), (458, 0.08, 18)):
            pts = []
            offset = camera_x * speed
            for x in range(-40, SCREEN_WIDTH + 80, 36):
                y = y_base + math.sin((x + offset) * 0.012 + t * 0.32) * 20
                pts.append((x, int(y)))
            pygame.draw.lines(depth, (150, 38, 42, alpha), False, pts, 5)
            pygame.draw.lines(depth, (235, 92, 78, max(10, alpha - 10)), False, pts, 1)
        screen.blit(depth, (0, 0))

    def _draw_blood_cell_layer(
        self,
        screen: pygame.Surface,
        camera_x: float,
        t: float,
        cell_data: tuple,
        pulse_scale: float,
    ) -> None:
        cx, cy, rx, ry, angle, sf, ph, alpha = cell_data
        x = (cx - camera_x * sf) % (SCREEN_WIDTH + 180) - 90
        y = cy + math.sin(t * 0.55 + ph) * (7 + sf * 12)
        wobble = 1.0 + 0.08 * math.sin(t * 0.9 + ph)
        rw = max(10, int(rx * pulse_scale * wobble))
        rh = max(5, int(ry * (1.0 + 0.10 * math.sin(t + ph))))
        pad = 10
        cell = pygame.Surface((rw * 2 + pad * 2, rh * 2 + pad * 2), pygame.SRCALPHA)
        rect = pygame.Rect(pad, pad, rw * 2, rh * 2)
        base_alpha = int(alpha)
        edge_alpha = min(150, base_alpha + 28)
        hollow_alpha = max(20, base_alpha - 22)
        pygame.draw.ellipse(cell, (72, 10, 18, max(12, base_alpha // 2)), rect.move(3, 4))
        pygame.draw.ellipse(cell, (172, 34, 44, base_alpha), rect)
        pygame.draw.ellipse(cell, (248, 96, 86, edge_alpha), rect, 2)
        pygame.draw.ellipse(cell, (76, 12, 22, hollow_alpha), rect.inflate(-max(9, rw), -max(5, rh // 2)))
        pygame.draw.ellipse(
            cell,
            (255, 156, 132, max(16, base_alpha // 2)),
            (rect.left + rw // 3, rect.top + rh // 4, max(6, rw // 2), max(3, rh // 3)),
            1,
        )
        rotated = pygame.transform.rotate(cell, math.degrees(angle + math.sin(t * 0.2 + ph) * 0.05))
        screen.blit(rotated, (int(x - rotated.get_width() / 2), int(y - rotated.get_height() / 2)))

    # ── Stage2 ミーム汚染（走査ノイズ）─────────────────────────
    def _draw_meme(self, screen: pygame.Surface, camera_x: float) -> None:
        t = self._time
        self._draw_stage2_concept_backdrop(screen, camera_x)
        for (y, h, sp, ph) in self._cells:
            yy = (y + math.sin(t * sp + ph) * 40) % SCREEN_HEIGHT
            alpha = int(9 + 8 * (0.5 + 0.5 * math.sin(t * 3 + ph)))
            band = pygame.Surface((SCREEN_WIDTH, int(h)), pygame.SRCALPHA)
            band.fill((150, 205, 188, alpha))
            screen.blit(band, (0, int(yy)))
        # ブロックノイズ点
        for idx, (cx, cy, w, h, sf, alpha) in enumerate(self._stage2_fragments):
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 120) - 60
            y = cy + math.sin(t * 0.35 + idx * 0.61) * 3
            frag = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            frag.fill((3, 8, 9, int(alpha)))
            if idx % 4 == 0:
                pygame.draw.rect(frag, (50, 140, 116, 24), frag.get_rect(), 1)
            screen.blit(frag, (int(x), int(y)))

        scan = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for y in range(0, SCREEN_HEIGHT, 4):
            pygame.draw.line(scan, (180, 224, 202, 7), (0, y), (SCREEN_WIDTH, y), 1)
        drift_y = int((t * 18) % SCREEN_HEIGHT)
        pygame.draw.rect(scan, (120, 210, 172, 18), (0, drift_y, SCREEN_WIDTH, 2))
        screen.blit(scan, (0, 0))

    # Stage2 concept backdrop image.
    def _draw_stage2_concept_backdrop(self, screen: pygame.Surface, camera_x: float) -> None:
        bg = self._load_stage2_backdrop()
        if bg is None:
            return
        width = bg.get_width()
        offset = int(camera_x * 0.10) % width
        for x in range(-offset, SCREEN_WIDTH, width):
            screen.blit(bg, (x, 0))
        veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 11, 12, 34))
        for y in range(SCREEN_HEIGHT):
            edge = abs(y - SCREEN_HEIGHT // 2) / (SCREEN_HEIGHT // 2)
            alpha = int(18 * edge)
            if alpha:
                pygame.draw.line(veil, (0, 0, 0, alpha), (0, y), (SCREEN_WIDTH, y), 1)
        screen.blit(veil, (0, 0))

    def _load_stage2_backdrop(self) -> pygame.Surface | None:
        if self._stage2_bg is not None:
            return self._stage2_bg
        try:
            raw = pygame.image.load(_STAGE2_BG_PATH)
        except (FileNotFoundError, pygame.error):
            return None
        if raw.get_height() != SCREEN_HEIGHT:
            scale = SCREEN_HEIGHT / raw.get_height()
            raw = pygame.transform.smoothscale(
                raw,
                (max(SCREEN_WIDTH, int(raw.get_width() * scale)), SCREEN_HEIGHT),
            )
        self._stage2_bg = raw
        return self._stage2_bg

    # ── Stage3 婚活・労働（UIカード）───────────────────────────
    def _draw_konkatsu(self, screen: pygame.Surface, camera_x: float) -> None:
        for (cx, cy, w, h, sf) in self._cells:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 160) - 80
            card = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            card.fill((40, 60, 90, 45))
            pygame.draw.rect(card, (90, 130, 180, 70), (0, 0, int(w), int(h)), 1, border_radius=4)
            # アバター丸＋行
            pygame.draw.circle(card, (110, 150, 200, 70), (12, int(h // 2)), 7)
            pygame.draw.rect(card, (90, 130, 180, 55), (26, int(h * 0.3), int(w - 36), 4))
            pygame.draw.rect(card, (70, 100, 150, 45), (26, int(h * 0.6), int(w - 52), 4))
            screen.blit(card, (int(x), int(cy)))

    # ── Stage4 棋理深淵（将棋盤・駒）───────────────────────────
    def _draw_shogi(self, screen: pygame.Surface, camera_x: float) -> None:
        # 薄い将棋盤グリッド（視差スクロール）
        cell = 72
        off = int(camera_x * 0.25) % cell
        grid_col = (40, 38, 60)
        for gx in range(-off, SCREEN_WIDTH + cell, cell):
            pygame.draw.line(screen, grid_col, (gx, 0), (gx, SCREEN_HEIGHT), 1)
        for gy in range(0, SCREEN_HEIGHT + cell, cell):
            pygame.draw.line(screen, grid_col, (0, gy), (SCREEN_WIDTH, gy), 1)
        # 点在する駒グリフ
        if self._piece_font is None:
            self._piece_font = pygame.font.SysFont("yugothic, meiryo, sans-serif", 30)
        for (cx, cy, sf, ch) in self._cells:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 80) - 40
            surf = self._piece_font.render(ch, True, (70, 64, 100))
            surf.set_alpha(60)
            screen.blit(surf, (int(x), int(cy)))
