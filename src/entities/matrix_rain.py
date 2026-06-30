"""Stage2 背景の縦コード雨（Matrix 風）。

奥行きを出すため3層構成（奥＝小さく遅く暗い／手前＝大きく速く明るい）。
等幅フォント（MS ゴシック）で列を揃え、グリフは左右反転、縦は詰めて流す。
パララックス背景の上・地形やプレイヤーの下に薄く重ね、ステージ2でのみ有効化する。
"""
from __future__ import annotations

import random
from typing import Callable

import pygame

# カタカナ＋全角数字・記号（半角全角の混在を避けて等幅で揃える。英字は混ぜない）
_GLYPHS = ("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
           "マミムメモヤユヨラリルレロワヲ"
           "０１２３４５６７８９：＝＋－｜")

# 明（head）→ 中 → 暗（trail 末端）の3トーン（緑）
_TONES = ((190, 255, 210), (60, 215, 110), (28, 120, 64))

# 奥→手前の層スペック: (フォントサイズ, 速度倍率, 不透明度倍率)
#   全体に小さめ・控えめ・暗めにして背景へ沈める。
_LAYER_SPECS = ((5, 0.55, 0.45), (7, 0.8, 0.6), (9, 1.1, 0.8))


class _RainLayer:
    """1層分の縦コード雨。"""

    def __init__(self, width: int, height: int, font: pygame.font.Font,
                 *, speed_mul: float, alpha_mul: float) -> None:
        self._h = height
        self._font = font
        glyph_w = max(1, font.size("ア")[0])
        self._col_w = max(1, int(glyph_w * 1.7))               # 列を間引いて量を控えめに
        self._row_h = max(6, int(font.get_height() * 0.74))    # 縦を詰める
        self._rows = height // self._row_h + 2
        self._speed_mul = speed_mul
        self._alpha_mul = alpha_mul
        n_cols = max(1, width // self._col_w)
        self._cols = [self._make(i) for i in range(n_cols)]
        self._cache: dict[tuple[str, int], pygame.Surface] = {}

    def _make(self, i: int) -> dict:
        c: dict = {"x": i * self._col_w,
                   "glyphs": [random.choice(_GLYPHS) for _ in range(self._rows + 4)]}
        self._reset(c, initial=True)
        return c

    def _reset(self, c: dict, *, initial: bool = False) -> None:
        # initial=True は生成時。ヘッドを画面全体に散らして「最初から降っている」状態にする。
        c["head"] = random.uniform(0.0, self._rows) if initial else float(-random.randint(2, 16))
        c["speed"] = random.uniform(7.0, 18.0) * self._speed_mul
        c["trail"] = random.randint(12, 28)
        c["swap"] = 0.0

    def _glyph(self, ch: str, tone: int) -> pygame.Surface:
        key = (ch, tone)
        surf = self._cache.get(key)
        if surf is None:
            surf = self._font.render(ch, True, _TONES[tone]).convert_alpha()
            surf = pygame.transform.flip(surf, True, False)   # 左右反転
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
        row_h = self._row_h
        amul = self._alpha_mul
        for c in self._cols:
            head_i = int(c["head"])
            trail = c["trail"]
            glyphs = c["glyphs"]
            n = len(glyphs)
            for t in range(trail):
                row = head_i - t
                if row < 0:
                    continue
                y = row * row_h
                if y >= self._h:
                    continue
                ch = glyphs[row % n]
                if t == 0:
                    g = self._glyph(ch, 0)
                    alpha = 150
                elif t < trail * 0.4:
                    g = self._glyph(ch, 1)
                    alpha = max(20, int(120 * (1 - t / trail)))
                else:
                    g = self._glyph(ch, 2)
                    alpha = max(12, int(80 * (1 - t / trail)))
                g.set_alpha(int(alpha * amul))
                surf.blit(g, (c["x"], y))


class MatrixRain:
    """3層の縦コード雨（奥→手前）で奥行きを出す。"""

    def __init__(self, width: int, height: int,
                 font_factory: Callable[[int], pygame.font.Font]) -> None:
        self._layers = [
            _RainLayer(width, height, font_factory(size),
                       speed_mul=speed_mul, alpha_mul=alpha_mul)
            for size, speed_mul, alpha_mul in _LAYER_SPECS
        ]

    def update(self, dt: float) -> None:
        for layer in self._layers:
            layer.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        for layer in self._layers:   # 奥→手前の順に重ねる
            layer.draw(surf)
