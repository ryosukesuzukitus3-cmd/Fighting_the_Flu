"""Generate small UI sound effects used by aliases.py."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "music" / "se"


def _write_wav(name: str, samples: list[float]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    clipped = [max(-1.0, min(1.0, sample)) for sample in samples]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(struct.pack(
            f"{len(clipped)}h",
            *(int(sample * 32767) for sample in clipped),
        ))
    print(f"generated: {path}")


def _tone(duration: float, freq: float, *, volume: float, decay: float) -> list[float]:
    samples = []
    for i in range(max(1, int(RATE * duration))):
        t = i / RATE
        env = math.exp(-t * decay)
        samples.append(math.sin(2.0 * math.pi * freq * t) * env * volume)
    return samples


def _type_sound() -> list[float]:
    samples = []
    for i in range(int(RATE * 0.035)):
        t = i / RATE
        env = math.exp(-t * 75.0)
        click = 0.55 * math.sin(2.0 * math.pi * 1180.0 * t)
        tick = 0.35 * math.sin(2.0 * math.pi * 2260.0 * t)
        noise = (((i * 1103515245 + 12345) & 0x7FFF) / 0x7FFF * 2.0 - 1.0) * 0.10
        samples.append((click + tick + noise) * env * 0.34)
    return samples


def _item_pickup_sound() -> list[float]:
    lower = _tone(0.075, 880.0, volume=0.40, decay=13.0)
    upper = [0.0] * int(RATE * 0.035) + _tone(0.11, 1320.0, volume=0.36, decay=11.0)
    samples = []
    for i in range(max(len(lower), len(upper))):
        t = i / RATE
        shimmer = math.sin(2.0 * math.pi * 2480.0 * t) * math.exp(-t * 17.0) * 0.09
        samples.append(
            (lower[i] if i < len(lower) else 0.0)
            + (upper[i] if i < len(upper) else 0.0)
            + shimmer
        )
    return samples


def main() -> None:
    _write_wav("type.wav", _type_sound())
    _write_wav("item_pickup.wav", _item_pickup_sound())


if __name__ == "__main__":
    main()
