"""ZUNDA粒子砲の元動画からゲーム用RGBAフレームを再生成する。

元動画の16:9画角を維持し、発光外周を切らずに固定キャンバスへ収める。
黒背景は輝度ベースのソフトマットへ変換し、全フレームの寸法と余白を
検証してから ``assets/graphic/laser/zunda`` を置き換える。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "graphic" / "laser" / "nc226126_ZUNDA粒子砲final.mp4"
DEFAULT_OUTPUT = ROOT / "assets" / "graphic" / "laser" / "zunda"
DEFAULT_SIZE = (640, 400)
DEFAULT_FPS = 18.5
DEFAULT_FRAME_COUNT = 48
TRANSPARENT_THRESHOLD = 8
OPAQUE_THRESHOLD = 180
MIN_VERTICAL_PADDING = 20

_FFMPEG_CANDIDATES = (
    Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"),
    Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files\TuneFab All-in-one Music Converter\ffmpeg.exe"),
)


def _find_ffmpeg(override: str | None) -> Path:
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise FileNotFoundError(f"ffmpeg が見つかりません: {path}")

    command = shutil.which("ffmpeg")
    if command:
        return Path(command)
    for path in _FFMPEG_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("ffmpeg が見つかりません。--ffmpeg でパスを指定してください。")


def _soft_black_matte(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    red, green, blue = rgb.split()
    strength = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    span = OPAQUE_THRESHOLD - TRANSPARENT_THRESHOLD
    alpha_lut = [
        0
        if value <= TRANSPARENT_THRESHOLD
        else 255
        if value >= OPAQUE_THRESHOLD
        else round((value - TRANSPARENT_THRESHOLD) * 255 / span)
        for value in range(256)
    ]
    rgb.putalpha(strength.point(alpha_lut))
    return rgb


def _validate_frame(image: Image.Image, expected_size: tuple[int, int], name: str) -> None:
    if image.size != expected_size:
        raise ValueError(f"{name}: size={image.size}, expected={expected_size}")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"{name}: 透過後に有効画素がありません")
    height = expected_size[1]
    top_padding = bbox[1]
    bottom_padding = height - bbox[3]
    if min(top_padding, bottom_padding) < MIN_VERTICAL_PADDING:
        raise ValueError(
            f"{name}: 上下余白不足 top={top_padding}, bottom={bottom_padding}"
        )


def extract_frames(
    source: Path,
    output: Path,
    *,
    ffmpeg: Path,
    size: tuple[int, int] = DEFAULT_SIZE,
    fps: float = DEFAULT_FPS,
    frame_count: int = DEFAULT_FRAME_COUNT,
) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"元動画が見つかりません: {source}")
    if fps <= 0 or frame_count <= 0:
        raise ValueError("fps と frame_count は正の整数で指定してください")

    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="zunda_frames_", dir=tmp_root) as tmp:
        tmp_dir = Path(tmp)
        raw_dir = tmp_dir / "raw"
        processed_dir = tmp_dir / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        width, height = size
        content_height = round(width * 9 / 16)
        content_height += content_height % 2
        if height < content_height:
            raise ValueError(
                f"出力高さ {height}px は16:9素材の高さ {content_height}px より小さいです"
            )
        command = [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            (
                f"fps={fps},scale={width}:{content_height}:flags=lanczos,"
                f"pad={width}:{height}:0:(oh-ih)/2:color=black"
            ),
            "-frames:v",
            str(frame_count),
            str(raw_dir / "raw_%02d.png"),
        ]
        subprocess.run(command, check=True)

        raw_frames = sorted(raw_dir.glob("raw_*.png"))
        if len(raw_frames) != frame_count:
            raise RuntimeError(f"抽出枚数が不正です: {len(raw_frames)} / {frame_count}")

        generated: list[Path] = []
        for index, raw_path in enumerate(raw_frames):
            frame = _soft_black_matte(Image.open(raw_path))
            name = f"zunda_{index:02d}.png"
            _validate_frame(frame, size, name)
            destination = processed_dir / name
            frame.save(destination, optimize=True)
            generated.append(destination)

        output.mkdir(parents=True, exist_ok=True)
        expected_names = {path.name for path in generated}
        for stale in output.glob("zunda_*.png"):
            if stale.name not in expected_names:
                stale.unlink()
        for generated_path in generated:
            shutil.copy2(generated_path, output / generated_path.name)

    print(
        f"generated {frame_count} frames: {output} "
        f"({size[0]}x{size[1]}, {fps} fps, vertical padding >= {MIN_VERTICAL_PADDING}px)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffmpeg", help="ffmpeg.exe のパス（省略時は自動検出）")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAME_COUNT)
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = parser.parse_args()
    extract_frames(
        args.source.resolve(),
        args.out.resolve(),
        ffmpeg=_find_ffmpeg(args.ffmpeg),
        size=(args.width, args.height),
        fps=args.fps,
        frame_count=args.frames,
    )


if __name__ == "__main__":
    main()
