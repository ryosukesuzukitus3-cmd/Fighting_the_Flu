from __future__ import annotations
import math
import random
import pygame
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


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
        self._stage2_panels: list = []
        self._stage2_glyphs: list = []
        self._stage3_gate_frames: list = []
        self._stage3_badges: list = []
        self._stage4_grid_layers: list = []
        self._stage4_pieces: list = []
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
            self._stage2_panels = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(26, SCREEN_HEIGHT - 92),
                 rnd.uniform(58, 150), rnd.uniform(34, 92), rnd.uniform(0.045, 0.16),
                 rnd.choice(((38, 92, 78), (46, 110, 118), (76, 86, 128))))
                for _ in range(14)
            ]
            self._stage2_glyphs = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(18, SCREEN_HEIGHT - 38),
                 rnd.uniform(0.08, 0.22), rnd.choice(("0101", "ERR", "404", "SYS", "NOISE", "MEME")),
                 rnd.uniform(0, 6.28))
                for _ in range(16)
            ]
        elif sid == 3:
            # 婚活UIカード矩形（x, y, w, h, 速度）
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(30, SCREEN_HEIGHT - 90),
                 rnd.uniform(70, 130), rnd.uniform(40, 64), rnd.uniform(0.12, 0.3))
                for _ in range(8)
            ]
            self._stage3_gate_frames = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(42, SCREEN_HEIGHT - 126),
                 rnd.uniform(74, 132), rnd.uniform(118, 210), rnd.uniform(0.045, 0.12),
                 rnd.uniform(0, 6.28))
                for _ in range(7)
            ]
            self._stage3_badges = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(62, SCREEN_HEIGHT - 64),
                 rnd.uniform(0.16, 0.34), rnd.uniform(0, 6.28))
                for _ in range(10)
            ]
        elif sid == 4:
            # 駒グリフ（x, y, 速度, 文字）
            glyphs = "歩香桂銀金角飛王"
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(30, SCREEN_HEIGHT - 40),
                 rnd.uniform(0.1, 0.3), rnd.choice(glyphs))
                for _ in range(10)
            ]
            self._stage4_grid_layers = [
                (rnd.randint(48, 96), rnd.uniform(0.06, 0.22), rnd.randint(18, 46),
                 rnd.uniform(0, 6.28))
                for _ in range(3)
            ]
            self._stage4_pieces = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(44, SCREEN_HEIGHT - 76),
                 rnd.uniform(34, 64), rnd.uniform(0.055, 0.20), rnd.uniform(-0.35, 0.35),
                 rnd.choice("歩香桂銀金角飛王玉"))
                for _ in range(12)
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

        # 熱の霞。
        haze_alpha = int(18 + 10 * (0.5 + 0.5 * math.sin(t * 1.5)))
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
        grid = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for step, sf, alpha in ((56, 0.08, 16), (34, 0.18, 12)):
            off = int(camera_x * sf) % step
            for x in range(-off, SCREEN_WIDTH + step, step):
                pygame.draw.line(grid, (60, 190, 150, alpha), (x, 0), (x, SCREEN_HEIGHT), 1)
            for y in range(0, SCREEN_HEIGHT + step, step):
                pygame.draw.line(grid, (45, 125, 170, alpha // 2), (0, y), (SCREEN_WIDTH, y), 1)
        screen.blit(grid, (0, 0))

        for idx, (cx, cy, w, h, sf, color) in enumerate(self._stage2_panels):
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 220) - 110
            pulse = 0.5 + 0.5 * math.sin(t * 1.4 + idx * 0.7)
            self._draw_circuit_panel(screen, int(x), int(cy), int(w), int(h), color, pulse)

        for (y, h, sp, ph) in self._cells:
            yy = (y + math.sin(t * sp + ph) * 40) % SCREEN_HEIGHT
            alpha = int(24 + 22 * (0.5 + 0.5 * math.sin(t * 3 + ph)))
            band = pygame.Surface((SCREEN_WIDTH, int(h)), pygame.SRCALPHA)
            band.fill((80, 155, 130, alpha))
            screen.blit(band, (0, int(yy)))
        # ブロックノイズ点
        font = getattr(self, "_stage2_font", None)
        if font is None:
            font = pygame.font.SysFont("consolas, meiryo, sans-serif", 15)
            self._stage2_font = font
        for idx, (cx, cy, sf, text, ph) in enumerate(self._stage2_glyphs):
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 120) - 60
            alpha = int(28 + 26 * (0.5 + 0.5 * math.sin(t * 1.7 + ph)))
            glyph = font.render(text, True, (86, 225, 178))
            glyph.set_alpha(alpha)
            if idx % 3 == 0:
                pygame.draw.line(screen, (58, 210, 168, 28), (int(x) - 18, int(cy) + 8), (int(x) - 2, int(cy) + 8), 1)
            screen.blit(glyph, (int(x), int(cy)))

        tick = int(t * 18)
        for i in range(18):
            bx = (i * 73 + tick * (i % 4 + 1) - int(camera_x * 0.42)) % (SCREEN_WIDTH + 40) - 20
            by = (i * 47 + tick * (i % 3 + 2)) % SCREEN_HEIGHT
            bw = 4 + (i * 5 + tick) % 18
            bh = 2 + (i * 3) % 6
            s = pygame.Surface((bw, bh), pygame.SRCALPHA)
            s.fill((110, 235, 185, 18 + (i % 4) * 8))
            screen.blit(s, (int(bx), int(by)))

    # ── Stage3 婚活・労働（UIカード）───────────────────────────
    def _draw_circuit_panel(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple[int, int, int],
        pulse: float,
    ) -> None:
        if w <= 0 or h <= 0:
            return
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        base_alpha = int(28 + 18 * pulse)
        panel.fill((*color, base_alpha))
        pygame.draw.rect(panel, (90, 235, 190, 46), (0, 0, w, h), 1, border_radius=3)
        pygame.draw.rect(panel, (36, 78, 92, 60), (5, 5, max(4, w - 10), max(4, h - 10)), 1, border_radius=2)
        mid = h // 2
        for i in range(3, w - 8, 18):
            y1 = 10 + (i * 7) % max(12, h - 18)
            pygame.draw.line(panel, (112, 250, 205, 42), (i, y1), (min(w - 7, i + 14), y1), 1)
            pygame.draw.line(panel, (80, 160, 210, 28), (min(w - 7, i + 14), y1), (min(w - 7, i + 14), mid), 1)
            pygame.draw.rect(panel, (122, 245, 208, 52), (min(w - 8, i + 12), max(4, mid - 2), 4, 4))
        screen.blit(panel, (x, y))

    def _draw_konkatsu(self, screen: pygame.Surface, camera_x: float) -> None:
        t = self._time
        for idx, (cx, cy, w, h, sf, ph) in enumerate(self._stage3_gate_frames):
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 180) - 90
            gate = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            gate.fill((18, 30, 48, 24))
            pygame.draw.rect(gate, (86, 142, 190, 45), (0, 0, int(w), int(h)), 1, border_radius=4)
            pygame.draw.rect(gate, (45, 82, 120, 46), (7, 8, max(6, int(w) - 14), max(8, int(h) - 16)), 1, border_radius=3)
            scan_y = int((0.5 + 0.5 * math.sin(t * 0.8 + ph)) * max(1, int(h) - 18)) + 9
            pygame.draw.line(gate, (100, 225, 230, 65), (8, scan_y), (int(w) - 9, scan_y), 2)
            for k in range(3):
                yy = 18 + k * max(14, int(h) // 4)
                pygame.draw.line(gate, (110, 160, 210, 24), (14, yy), (int(w) - 15, yy), 1)
            if idx % 2 == 0:
                self._draw_tiny_heart(gate, int(w) - 22, 18, 7, (210, 112, 150, 42))
            screen.blit(gate, (int(x), int(cy)))

        for (cx, cy, w, h, sf) in self._cells:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 160) - 80
            card = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            card.fill((34, 48, 72, 48))
            pygame.draw.rect(card, (94, 136, 184, 74), (0, 0, int(w), int(h)), 1, border_radius=4)
            pygame.draw.rect(card, (70, 118, 168, 38), (0, 0, int(w), max(7, int(h * 0.18))), border_radius=4)
            # アバター丸＋行
            pygame.draw.circle(card, (110, 150, 200, 70), (12, int(h // 2)), 7)
            pygame.draw.rect(card, (98, 152, 198, 58), (26, int(h * 0.3), int(w - 36), 4))
            pygame.draw.rect(card, (72, 106, 160, 48), (26, int(h * 0.6), int(w - 52), 4))
            self._draw_tiny_heart(card, int(w) - 14, int(h) - 13, 5, (220, 110, 150, 48))
            screen.blit(card, (int(x), int(cy)))

    # ── Stage4 棋理深淵（将棋盤・駒）───────────────────────────
        for cx, cy, sf, ph in self._stage3_badges:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 90) - 45
            r = int(8 + 3 * (0.5 + 0.5 * math.sin(t * 1.1 + ph)))
            badge = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            self._draw_tiny_heart(badge, r * 2, r * 2, r, (224, 116, 150, 34))
            pygame.draw.circle(badge, (96, 160, 210, 24), (r * 2, r * 2), r + 5, 1)
            screen.blit(badge, (int(x) - r * 2, int(cy) - r * 2))

    @staticmethod
    def _draw_tiny_heart(
        surface: pygame.Surface,
        cx: int,
        cy: int,
        size: int,
        color: tuple[int, int, int, int],
    ) -> None:
        r = max(2, size // 2)
        pygame.draw.circle(surface, color, (cx - r, cy - r), r)
        pygame.draw.circle(surface, color, (cx + r, cy - r), r)
        pygame.draw.polygon(surface, color, ((cx - size, cy - r // 2), (cx + size, cy - r // 2), (cx, cy + size + r)))

    # Stage4 shogi board depth.
    def _draw_shogi(self, screen: pygame.Surface, camera_x: float) -> None:
        t = self._time
        for cell, sf, alpha, ph in self._stage4_grid_layers:
            off = int(camera_x * sf + math.sin(t * 0.22 + ph) * cell * 0.18) % cell
            grid = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            col = (84, 72, 124, alpha)
            for gx in range(-off, SCREEN_WIDTH + cell, cell):
                pygame.draw.line(grid, col, (gx, 0), (gx, SCREEN_HEIGHT), 1)
            for gy in range(-off // 2, SCREEN_HEIGHT + cell, cell):
                pygame.draw.line(grid, (58, 50, 92, max(10, alpha - 14)), (0, gy), (SCREEN_WIDTH, gy), 1)
            screen.blit(grid, (0, 0))

        for idx, (cx, cy, size, sf, angle, ch) in enumerate(self._stage4_pieces):
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 150) - 75
            y = cy + math.sin(t * 0.35 + idx) * 8
            self._draw_shogi_piece(screen, int(x), int(y), int(size), angle + math.sin(t * 0.14 + idx) * 0.05, ch)

        cell = 72
        # 薄い将棋盤グリッド（視差スクロール）
        cell = 72
        off = int(camera_x * 0.25) % cell
        grid_col = (52, 46, 78)
        for gx in range(-off, SCREEN_WIDTH + cell, cell):
            pygame.draw.line(screen, grid_col, (gx, 0), (gx, SCREEN_HEIGHT), 1)
        for gy in range(0, SCREEN_HEIGHT + cell, cell):
            pygame.draw.line(screen, grid_col, (0, gy), (SCREEN_WIDTH, gy), 1)
        # 点在する駒グリフ
        if self._piece_font is None:
            self._piece_font = pygame.font.SysFont("yugothic, meiryo, sans-serif", 30)
        for (cx, cy, sf, ch) in self._cells:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 80) - 40
            surf = self._piece_font.render(ch, True, (104, 92, 146))
            surf.set_alpha(54)
            screen.blit(surf, (int(x), int(cy)))

    def _draw_shogi_piece(
        self,
        screen: pygame.Surface,
        cx: int,
        cy: int,
        size: int,
        angle: float,
        ch: str,
    ) -> None:
        if self._piece_font is None:
            self._piece_font = pygame.font.SysFont("yugothic, meiryo, sans-serif", 30)
        w = max(28, size)
        h = int(w * 1.22)
        piece = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
        pts = [
            (w // 2 + 6, 6),
            (w + 4, int(h * 0.34) + 6),
            (int(w * 0.80) + 6, h + 4),
            (int(w * 0.20) + 6, h + 4),
            (8, int(h * 0.34) + 6),
        ]
        pygame.draw.polygon(piece, (32, 26, 50, 84), pts)
        pygame.draw.lines(piece, (164, 132, 92, 70), True, pts, 2)
        glyph = self._piece_font.render(ch, True, (184, 154, 112))
        glyph.set_alpha(72)
        piece.blit(glyph, glyph.get_rect(center=(w // 2 + 6, int(h * 0.56) + 6)))
        rotated = pygame.transform.rotate(piece, math.degrees(angle))
        screen.blit(rotated, rotated.get_rect(center=(cx, cy)))
