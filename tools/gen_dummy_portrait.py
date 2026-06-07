"""カロナール先輩のダミーポートレート画像を生成する。

専用立ち絵が未用意のため、会話ウィンドウ表示用のプレースホルダを生成する。
先輩カラー(140,230,150)の角丸ボックスに「先輩」と描く。

実行: .venv/Scripts/python tools/gen_dummy_portrait.py
出力: assets/graphic/portrait_karonaru_dummy.png
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_ROOT = Path(__file__).resolve().parent.parent
_OUT  = _ROOT / "assets" / "graphic" / "portrait_karonaru_dummy.png"
_FONT = _ROOT / "assets" / "font" / "DotGothic16-Regular.ttf"

_SIZE   = 96
_GREEN  = (140, 230, 150, 255)
_DARK   = (18, 40, 24, 235)
_TEXT   = (235, 255, 240, 255)


def main() -> None:
    img  = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 角丸の背景＋枠
    draw.rounded_rectangle((2, 2, _SIZE - 3, _SIZE - 3), radius=12, fill=_DARK, outline=_GREEN, width=3)
    # 「先輩」テキスト中央寄せ
    try:
        font = ImageFont.truetype(str(_FONT), 34)
    except OSError:
        font = ImageFont.load_default()
    text = "先輩"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((_SIZE - tw) / 2 - bbox[0], (_SIZE - th) / 2 - bbox[1]), text, font=font, fill=_TEXT)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(_OUT)
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
