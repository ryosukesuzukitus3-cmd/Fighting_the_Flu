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
        self._theme_init(stage_id)

    # ── テーマ要素の事前生成（ランダム配置を固定）────────────────
    def _theme_init(self, sid: int) -> None:
        rnd = random.Random(sid * 1000 + 7)
        self._cells: list = []
        if sid == 1:
            # 血球（漂う赤い円）と血管うねりの位相
            self._cells = [
                (rnd.uniform(0, SCREEN_WIDTH), rnd.uniform(0, SCREEN_HEIGHT),
                 rnd.uniform(6, 16), rnd.uniform(0.06, 0.22), rnd.uniform(0, 6.28))
                for _ in range(14)
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
            pygame.draw.polygon(rib, (58, 10, 16, 60), pts_l + list(reversed(pts_r)))
            pygame.draw.lines(rib, (115, 22, 28, 45), False, pts_l, 2)
            pygame.draw.lines(rib, (115, 22, 28, 35), False, pts_r, 2)
        screen.blit(rib, (0, 0))

        # 熱の霞。
        haze_alpha = int(18 + 10 * (0.5 + 0.5 * math.sin(t * 1.5)))
        haze = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        haze.fill((120, 22, 18, haze_alpha))
        screen.blit(haze, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # うねる血管ライン（2本）
        for k, (base_y, col) in enumerate(((SCREEN_HEIGHT * 0.32, (82, 24, 28)),
                                           (SCREEN_HEIGHT * 0.7,  (68, 18, 22)))):
            pts = []
            for x in range(0, SCREEN_WIDTH + 20, 40):
                y = base_y + math.sin(x * 0.012 + t * 0.8 + k) * 26
                pts.append((x, int(y)))
            if len(pts) >= 2:
                pygame.draw.lines(screen, col, False, pts, 6)
        # 脈打つ血球
        pulse = 0.5 + 0.5 * math.sin(t * 2.0)
        for (cx, cy, r, sf, ph) in self._cells:
            x = (cx - camera_x * sf) % (SCREEN_WIDTH + 80) - 40
            rr = int(r * (0.8 + 0.4 * pulse))
            s = pygame.Surface((rr * 2 + 2, rr * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (150, 30, 40, 70), (rr + 1, rr + 1), rr)
            pygame.draw.circle(s, (200, 70, 80, 90), (rr + 1, rr + 1), max(1, rr // 2))
            screen.blit(s, (int(x), int(cy)))

    # ── Stage2 ミーム汚染（走査ノイズ）─────────────────────────
    def _draw_meme(self, screen: pygame.Surface, camera_x: float) -> None:
        t = self._time
        for (y, h, sp, ph) in self._cells:
            yy = (y + math.sin(t * sp + ph) * 40) % SCREEN_HEIGHT
            alpha = int(30 + 25 * (0.5 + 0.5 * math.sin(t * 3 + ph)))
            band = pygame.Surface((SCREEN_WIDTH, int(h)), pygame.SRCALPHA)
            band.fill((90, 120, 90, alpha))
            screen.blit(band, (0, int(yy)))
        # ブロックノイズ点
        for _ in range(8):
            bx = random.randint(0, SCREEN_WIDTH - 6)
            by = random.randint(0, SCREEN_HEIGHT - 4)
            s = pygame.Surface((random.randint(3, 7), random.randint(2, 4)), pygame.SRCALPHA)
            s.fill((120, 160, 120, 40))
            screen.blit(s, (bx, by))

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
