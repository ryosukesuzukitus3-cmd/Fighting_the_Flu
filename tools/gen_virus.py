"""
ウイルス/菌キャラクター画像を生成する
"""
from PIL import Image, ImageDraw
import math
from pathlib import Path

SIZE   = 48
CX, CY = SIZE // 2, SIZE // 2
RADIUS = 17   # 本体円半径
SPIKE  = 8    # トゲの長さ
N_SPIKE = 12  # トゲの本数

img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# トゲ（先が細い三角形）
for i in range(N_SPIKE):
    angle = 2 * math.pi * i / N_SPIKE
    tip_x = CX + (RADIUS + SPIKE) * math.cos(angle)
    tip_y = CY + (RADIUS + SPIKE) * math.sin(angle)
    left_angle  = angle - math.pi / N_SPIKE * 0.5
    right_angle = angle + math.pi / N_SPIKE * 0.5
    left_x  = CX + RADIUS * math.cos(left_angle)
    left_y  = CY + RADIUS * math.sin(left_angle)
    right_x = CX + RADIUS * math.cos(right_angle)
    right_y = CY + RADIUS * math.sin(right_angle)
    draw.polygon(
        [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)],
        fill=(180, 80, 200, 255)
    )

# 本体円（グラデーション風に2段描き）
draw.ellipse(
    [CX - RADIUS - 1, CY - RADIUS - 1, CX + RADIUS + 1, CY + RADIUS + 1],
    fill=(100, 40, 160, 255)
)
draw.ellipse(
    [CX - RADIUS + 2, CY - RADIUS + 2, CX + RADIUS - 2, CY + RADIUS - 2],
    fill=(140, 60, 200, 255)
)

# 目（黄色い点）
eye_r = 3
for ex, ey in [(CX - 5, CY - 3), (CX + 5, CY - 3)]:
    draw.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r], fill=(255, 230, 30, 255))
    draw.ellipse([ex - 1, ey - 1, ex + 1, ey + 1], fill=(20, 20, 20, 255))

# 口（への字）
draw.arc([CX - 6, CY + 2, CX + 6, CY + 9], start=0, end=180, fill=(30, 10, 50, 255), width=2)

out = Path(__file__).parent.parent / "assets" / "graphic" / "enemy_virus.png"
img.save(out)
print(f"saved: {out}  size={img.size}")
