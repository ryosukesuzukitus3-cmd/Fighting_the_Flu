"""ダミー SE（プレースホルダ効果音）を合成して assets/music/se/ に保存する。

専用素材が未用意の効果音（敵/ボス攻撃・先輩 被弾/退場）を、短い合成音で仮置きする。
後で本素材へ差し替え前提。実行: .venv/Scripts/python tools/gen_dummy_se.py
"""
from __future__ import annotations
import math
import struct
import wave
from pathlib import Path

RATE = 44100
_OUT = Path(__file__).resolve().parent.parent / "assets" / "music" / "se"


def _noise(i: int) -> float:
    return ((i * 1103515245 + 12345) & 0x7FFF) / 0x7FFF * 2 - 1


def _write(name: str, samples: list[float]) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / name
    n = len(samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(struct.pack(f"{n}h", *(int(max(-1.0, min(1.0, s)) * 32767) for s in samples)))
    print(f"生成: {path}")


def _tone(duration: float, f0: float, f1: float, *, decay: float, vol: float,
          noise_mix: float = 0.0) -> list[float]:
    """f0→f1 へ周波数スイープする減衰トーン。"""
    n = int(RATE * duration)
    out: list[float] = []
    for i in range(n):
        t = i / RATE
        prog = t / duration
        f = f0 + (f1 - f0) * prog
        sine = math.sin(2 * math.pi * f * t)
        v = (sine * (1.0 - noise_mix) + _noise(i) * noise_mix) * math.exp(-t * decay) * vol
        out.append(v)
    return out


def main() -> None:
    # 敵攻撃: 高めの短いピチュン（下降スイープ）
    _write("dummy_enemy_shot.wav", _tone(0.10, 1400, 600, decay=38, vol=0.5, noise_mix=0.15))
    # ボス攻撃: 低く重いズドン（下降＋ノイズ）
    _write("dummy_boss_shot.wav", _tone(0.16, 420, 160, decay=22, vol=0.6, noise_mix=0.25))
    # 先輩 被弾: 柔らかい中音のポッ
    _write("dummy_karonaru_hit.wav", _tone(0.09, 700, 520, decay=34, vol=0.45))
    # 先輩 退場: 下降する「しゅるん」
    _write("dummy_karonaru_retire.wav", _tone(0.32, 900, 200, decay=10, vol=0.5))
    # 持ち駒を置く「ピシッ」: 短く鋭いクリック（高音＋ノイズの立ち上がり）
    _write("dummy_shogi_place.wav", _tone(0.06, 2200, 900, decay=60, vol=0.5, noise_mix=0.30))


if __name__ == "__main__":
    main()
