"""会話ウィンドウ用のダミーポートレートを生成する（pygame描画・Pillow不要）。

専用立ち絵/顔素材が未用意・不適切な話者向けのプレースホルダ。
ピクセル基調の角丸枠＋話者カラー＋簡易エンブレム＋ラベルで、誤用画像（例: BOSS3が
ブロリー）よりも「意図したダミー」に見えるようにする。

実行: tools/run.py dummies  もしくは python tools/gen_dummy_portraits.py
出力: assets/graphic/portrait_*_dummy.png
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

OUT = ROOT / "assets" / "graphic"
FONT = ROOT / "assets" / "font" / "DotGothic16-Regular.ttf"
SIZE = 128


def _frame(surf, accent):
    surf.fill((0, 0, 0, 0))
    pygame.draw.rect(surf, (18, 20, 30, 235), (3, 3, SIZE - 6, SIZE - 6), border_radius=14)
    pygame.draw.rect(surf, (*accent, 255), (3, 3, SIZE - 6, SIZE - 6), 4, border_radius=14)


def _label(surf, text, accent):
    try:
        font = pygame.font.Font(str(FONT), 22)
    except Exception:
        font = pygame.font.Font(None, 24)
    lab = font.render(text, True, (240, 245, 240))
    sh = font.render(text, True, (0, 0, 0))
    x = (SIZE - lab.get_width()) // 2
    y = SIZE - lab.get_height() - 10
    surf.blit(sh, (x + 1, y + 1))
    surf.blit(lab, (x, y))


def _pill(surf, cx, cy, color):
    w, h = 64, 30
    r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
    pygame.draw.rect(surf, color, r, border_radius=h // 2)
    pygame.draw.rect(surf, (250, 250, 250), (r.x, r.y, w // 2, h), border_radius=h // 2)
    pygame.draw.rect(surf, (20, 30, 24), r, 3, border_radius=h // 2)


def _heart(surf, cx, cy, color):
    r = 20
    pygame.draw.circle(surf, color, (cx - r // 2, cy - r // 3), r // 2 + 3)
    pygame.draw.circle(surf, color, (cx + r // 2, cy - r // 3), r // 2 + 3)
    pygame.draw.polygon(surf, color, [(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx, cy + r)])
    pygame.draw.circle(surf, (255, 235, 245), (cx - r // 2 - 1, cy - r // 3 - 2), 3)


def _sparkle(surf, cx, cy, color, r=10):
    pts = [(cx, cy - r), (cx + r * 0.22, cy - r * 0.22), (cx + r, cy),
           (cx + r * 0.22, cy + r * 0.22), (cx, cy + r),
           (cx - r * 0.22, cy + r * 0.22), (cx - r, cy), (cx - r * 0.22, cy - r * 0.22)]
    pygame.draw.polygon(surf, color, pts)


def main() -> int:
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)

    # 先輩（カロナール）: 緑・カプセル
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _frame(s, (120, 215, 140))
    _pill(s, SIZE // 2, 54, (110, 205, 130))
    _label(s, "先輩", (120, 215, 140))
    pygame.image.save(s, str(OUT / "portrait_karonaru_dummy.png"))

    # 先輩・薬効最大: 明るい緑・カプセル＋きらめき
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _frame(s, (170, 245, 190))
    _pill(s, SIZE // 2, 54, (150, 235, 175))
    _sparkle(s, 96, 30, (255, 255, 210), 11)
    _sparkle(s, 34, 40, (255, 255, 210), 7)
    _label(s, "薬効MAX", (170, 245, 190))
    pygame.image.save(s, str(OUT / "portrait_karonaru_max_dummy.png"))

    # 婚活要塞マッチング・ゼロ: ピンク・ハート
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _frame(s, (240, 120, 175))
    _heart(s, SIZE // 2, 52, (235, 95, 150))
    _label(s, "婚活", (240, 120, 175))
    pygame.image.save(s, str(OUT / "portrait_matching_zero_dummy.png"))

    for n in ("portrait_karonaru_dummy", "portrait_karonaru_max_dummy", "portrait_matching_zero_dummy"):
        print(f"wrote {OUT / (n + '.png')}")
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
