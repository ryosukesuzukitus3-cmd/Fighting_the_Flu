"""Generate compact PNG sequences from videos placed in tmp/effect-source.

The source material is intentionally ignored by Git.  This script records all
trim/key/canvas choices so the committed runtime assets are reproducible.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tmp" / "effect-source"
DEFAULT_OUTPUT = ROOT / "assets" / "graphic" / "effects"


@dataclass(frozen=True)
class ExtractDef:
    key: str
    source_id: str
    start: float
    frames: int
    fps: float
    canvas: tuple[int, int]
    key_mode: str = "black"
    crop_alpha: bool = False
    flip_x: bool = False
    crop_each: bool = False


DEFS = (
    ExtractDef("electrical_hit", "nc114420", 0.0, 14, 18.0, (512, 288)),
    ExtractDef("electric_arcs", "nc156896", 0.15, 24, 18.0, (512, 288)),
    ExtractDef("anime_impact", "nc172648", 0.0, 18, 18.0, (384, 384), crop_each=True),
    ExtractDef("blue_slash", "nc186236", 0.0, 18, 18.0, (512, 288)),
    ExtractDef("radiant_flash", "nc224911", 0.0, 32, 16.0, (512, 288), "native"),
    ExtractDef("light_arrow_tunnel", "nc234645", 2.2, 20, 16.0, (512, 288), "opaque"),
    ExtractDef("missile_loop", "nc243927", 0.0, 18, 12.0, (240, 104), "green", True, True),
    ExtractDef("angel_flash", "nc268435", 0.0, 32, 16.0, (512, 288)),
    ExtractDef("rupture_laser", "nc338669", 0.0, 30, 12.0, (512, 288)),
    ExtractDef("warp_flash", "nc68226", 0.0, 28, 16.0, (512, 288)),
    ExtractDef("magenta_cleave", "nc95306", 0.0, 28, 16.0, (512, 288)),
    ExtractDef("retro_lasers", "nc97528", 0.0, 36, 16.0, (512, 288)),
)


def _find_ffmpeg(explicit: str | None) -> Path:
    candidates = [
        Path(explicit) if explicit else None,
        Path(shutil.which("ffmpeg") or ""),
        Path(r"C:\Program Files\TuneFab All-in-one Music Converter\ffmpeg.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError("ffmpeg was not found; pass --ffmpeg PATH")


def _source_for(folder: Path, source_id: str) -> Path:
    matches = sorted(folder.glob(f"{source_id}_*"))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one {source_id}_* in {folder}, found {len(matches)}")
    return matches[0]


def _black_key(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    peak = ImageChops.lighter(ImageChops.lighter(rgb.getchannel("R"), rgb.getchannel("G")),
                              rgb.getchannel("B"))
    alpha = peak.point(lambda value: max(0, min(255, round((value - 10) * 255 / 245))))
    rgba.putalpha(alpha)
    return rgba


def _green_key(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    get_pixels = getattr(rgba, "get_flattened_data", rgba.getdata)
    for r, g, b, _ in get_pixels():
        dominance = g - max(r, b)
        alpha = max(0, min(255, 255 - max(0, dominance - 18) * 5))
        # Despill the keyed edge so it does not leave a neon-green fringe.
        g = min(g, int(max(r, b) * 1.18 + 8)) if dominance > 18 else g
        pixels.append((r, g, b, alpha))
    rgba.putdata(pixels)
    return rgba


def _fit(image: Image.Image, canvas: tuple[int, int]) -> Image.Image:
    image = image.convert("RGBA")
    image.thumbnail(canvas, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.alpha_composite(image, ((canvas[0] - image.width) // 2, (canvas[1] - image.height) // 2))
    return out


def _crop_union(images: list[Image.Image]) -> list[Image.Image]:
    union = Image.new("L", images[0].size, 0)
    for image in images:
        union = ImageChops.lighter(union, image.getchannel("A"))
    bbox = union.getbbox()
    if bbox is None:
        return images
    pad = 10
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(images[0].width, bbox[2] + pad)
    bottom = min(images[0].height, bbox[3] + pad)
    return [image.crop((left, top, right, bottom)) for image in images]


def _crop_each(images: list[Image.Image]) -> list[Image.Image]:
    cropped: list[Image.Image] = []
    for image in images:
        bbox = image.getchannel("A").getbbox()
        if bbox is None:
            cropped.append(image)
            continue
        pad = 10
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(image.width, bbox[2] + pad)
        bottom = min(image.height, bbox[3] + pad)
        cropped.append(image.crop((left, top, right, bottom)))
    return cropped


def extract_one(defn: ExtractDef, source_dir: Path, output_dir: Path, ffmpeg: Path) -> None:
    source = _source_for(source_dir, defn.source_id)
    target = output_dir / defn.key
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob(f"{defn.key}_*.png"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix=f"flu-{defn.key}-") as tmp_name:
        tmp = Path(tmp_name)
        cmd = [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(defn.start), "-i", str(source),
            "-vf", f"fps={defn.fps}", "-frames:v", str(defn.frames),
            str(tmp / "frame_%03d.png"),
        ]
        subprocess.run(cmd, check=True)
        raw_paths = sorted(tmp.glob("frame_*.png"))
        if not raw_paths:
            raise RuntimeError(f"{defn.key}: ffmpeg produced no frames")
        # Some one-second clips end one sample before the requested frame count
        # because of container timestamp rounding.  Hold the final frame rather
        # than making runtime metadata depend on that encoder detail.
        while len(raw_paths) < defn.frames:
            duplicate = tmp / f"frame_{len(raw_paths) + 1:03d}.png"
            shutil.copyfile(raw_paths[-1], duplicate)
            raw_paths.append(duplicate)
        if len(raw_paths) > defn.frames:
            raw_paths = raw_paths[:defn.frames]

        images: list[Image.Image] = []
        for path in raw_paths:
            image = Image.open(path).convert("RGBA")
            if defn.key_mode == "black":
                image = _black_key(image)
            elif defn.key_mode == "green":
                image = _green_key(image)
            elif defn.key_mode == "opaque":
                image.putalpha(255)
            elif defn.key_mode != "native":
                raise ValueError(f"unknown key mode: {defn.key_mode}")
            images.append(image)

        if defn.crop_alpha:
            images = _crop_union(images)
        if defn.crop_each:
            images = _crop_each(images)
        for i, image in enumerate(images):
            if defn.flip_x:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            image = _fit(image, defn.canvas)
            image.save(target / f"{defn.key}_{i:02d}.png", optimize=True)
    print(f"{defn.key}: {defn.frames} frames from {source.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--only", choices=[defn.key for defn in DEFS])
    args = parser.parse_args()
    ffmpeg = _find_ffmpeg(args.ffmpeg)
    selected = [defn for defn in DEFS if args.only in (None, defn.key)]
    for defn in selected:
        extract_one(defn, args.source_dir, args.output_dir, ffmpeg)


if __name__ == "__main__":
    main()
