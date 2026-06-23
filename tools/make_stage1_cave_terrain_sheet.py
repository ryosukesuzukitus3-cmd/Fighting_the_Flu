"""Stage1 fever-cave 地形シートを fortress シートからリカラー生成する。

Stage3 の手描き fortress 地形シート（`stage3_fortress_terrain_sheet.png`）は
レリーフ・凹凸が描き込まれた完成アセット。Stage1 はこれと同じアトラス配置
（rects / alpha mask）を流用しつつ、配色だけ `fever_cave` テーマの暗赤へ
remap して「感染した洞窟壁」に見せる。

手法は tritone（陰影→中間→ハイライトの3〜5段ランプ）の luminance remap。
元シートの輝度ディテール（彫り・段差・リベット感）はそのまま保ちつつ、
寒色メタルを fever_cave の暖色赤系へ置き換える。完全に決定的で再現可能。

  .venv/Scripts/python tools/make_stage1_cave_terrain_sheet.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "graphic" / "stage3_fortress_terrain_sheet.png"
DST = ROOT / "assets" / "graphic" / "stage1_cave_terrain_sheet.png"

# fever_cave (src/entities/terrain.py の _STRIP_THEMES["fever_cave"]) に揃えた
# 輝度→色ランプ。(luminance 0-255, (r, g, b))。
RAMP: list[tuple[int, tuple[int, int, int]]] = [
    (0, (20, 6, 10)),       # 最深部の影
    (56, (52, 14, 20)),     # dark (58,16,22) 付近
    (120, (92, 28, 34)),    # base (86,24,30) 付近
    (180, (148, 52, 52)),   # spot〜edge の中間
    (224, (192, 74, 66)),   # edge/glow 付近
    (255, (224, 116, 96)),  # 最も明るいハイライト
]
# 中間調を少し持ち上げて、暗くなりがちな fortress を洞窟壁として読みやすくする。
GAMMA = 0.86


def _build_luts() -> tuple[list[int], list[int], list[int]]:
    lut_r: list[int] = []
    lut_g: list[int] = []
    lut_b: list[int] = []
    for value in range(256):
        # gamma 補正後の輝度でランプを引く。
        adjusted = (value / 255.0) ** GAMMA * 255.0
        lo = RAMP[0]
        hi = RAMP[-1]
        for i in range(len(RAMP) - 1):
            if RAMP[i][0] <= adjusted <= RAMP[i + 1][0]:
                lo, hi = RAMP[i], RAMP[i + 1]
                break
        span = max(1, hi[0] - lo[0])
        t = (adjusted - lo[0]) / span
        t = min(1.0, max(0.0, t))
        lut_r.append(round(lo[1][0] + (hi[1][0] - lo[1][0]) * t))
        lut_g.append(round(lo[1][1] + (hi[1][1] - lo[1][1]) * t))
        lut_b.append(round(lo[1][2] + (hi[1][2] - lo[1][2]) * t))
    return lut_r, lut_g, lut_b


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"source sheet not found: {SRC}")
    source = Image.open(SRC).convert("RGB")
    luminance = ImageOps.grayscale(source)
    lut_r, lut_g, lut_b = _build_luts()
    channel_r = luminance.point(lut_r)
    channel_g = luminance.point(lut_g)
    channel_b = luminance.point(lut_b)
    recolored = Image.merge("RGB", (channel_r, channel_g, channel_b))
    recolored.save(DST)
    print(f"wrote {DST} ({recolored.size[0]}x{recolored.size[1]})")


if __name__ == "__main__":
    main()
