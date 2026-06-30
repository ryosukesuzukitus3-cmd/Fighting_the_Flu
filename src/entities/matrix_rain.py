"""Stage2 背景の縦コード雨（Matrix 風）。

dim な緑のグリフが縦に流れ落ちる。パララックス背景の上・地形やプレイヤーの
下に薄く重ねて「情報汚染地帯」の空気を作る。STAGE_BG_TEXT の横スクロール
（廃止）の置き換えで、ステージ2でのみ有効化する。
"""
from __future__ import annotations

import random

import pygame

# カタカナ＋数字＋記号（Matrix 風のコード文字列）
_GLYPHS = ("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
           "マミムメモヤユヨラリルレロワヲ0123456789:.=*+-<>|")

# 明（head）→ 中 → 暗（trail 末端）の3トーン
_TONES = ((190, 255, 210), (60, 215, 110), (28, 120, 64))


class MatrixRain:
    """縦に流れるコード雨。背景サーフェスに薄く重ねる。"""

    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self._w = width
        self._h = height
        self._font = font
        self._cell = font.get_height() + 2
        self._rows = height // self._cell + 2
        n_cols = max(1, width // self._cell)
        self._cols = [self._make(i) for i in range(n_cols)]
        self._cache: dict[tuple[str, int], pygame.Surface] = {}

    def _make(self, i: int) -> dict:
        c: dict = {"x": i * self._cell,
                   "glyphs": [random.choice(_GLYPHS) for _ in range(self._rows + 4)]}
        self._reset(c, initial=True)
        return c

    def _reset(self, c: dict, *, initial: bool = False) -> None:
        c["head"] = random.uniform(-self._rows, 0.0) if initial else float(-random.randint(2, 16))
        c["speed"] = random.uniform(7.0, 18.0)   # rows / 秒
        c["trail"] = random.randint(6, 18)
        c["swap"] = 0.0

    def _glyph(self, ch: str, tone: int) -> pygame.Surface:
        key = (ch, tone)
        surf = self._cache.get(key)
        if surf is None:
            surf = self._font.render(ch, True, _TONES[tone]).convert_alpha()
            self._cache[key] = surf
        return surf

    def update(self, dt: float) -> None:
        for c in self._cols:
            c["head"] += c["speed"] * dt
            c["swap"] += dt
            if c["swap"] >= 0.07:
                c["swap"] = 0.0
                c["glyphs"][random.randrange(len(c["glyphs"]))] = random.choice(_GLYPHS)
            if c["head"] - c["trail"] > self._rows:
                self._reset(c)

    def draw(self, surf: pygame.Surface) -> None:
        cell = self._cell
        for c in self._cols:
            head_i = int(c["head"])
            trail = c["trail"]
            glyphs = c["glyphs"]
            n = len(glyphs)
            for t in range(trail):
                row = head_i - t
                if row < 0:
                    continue
                y = row * cell
                if y >= self._h:
                    continue
                ch = glyphs[row % n]
                if t == 0:
                    g = self._glyph(ch, 0)
                    alpha = 230
                elif t < trail * 0.4:
                    g = self._glyph(ch, 1)
                    alpha = max(30, int(200 * (1 - t / trail)))
                else:
                    g = self._glyph(ch, 2)
                    alpha = max(20, int(150 * (1 - t / trail)))
                g.set_alpha(alpha)
                surf.blit(g, (c["x"], y))
