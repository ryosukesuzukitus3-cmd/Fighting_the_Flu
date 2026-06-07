"""
ボス登場SE (boss_alert.wav) を合成して assets/music/ に保存する。

設計:
  - 重低音ドローン (55 Hz) : 不気味な低音基調
  - 悪魔の音程 トライトーン (78 Hz = 55 * sqrt(2)) : 不協和音
  - オカルト・コーラス : 3声部ミクソリディアン風コード (220/261/330 Hz) with tremolo
  - 初発インパクト : 短いノイズバースト + 低周波ビート
  - 低周波クレッシェンド : 徐々に盛り上がる
  合計尺: 2.8 秒
"""
import wave
import struct
import math
import random

RATE     = 44100
DURATION = 2.8
VOL      = 0.85

n = int(RATE * DURATION)
samples = []

for i in range(n):
    t = i / RATE

    # ── Layer 1: 重低音ドローン ────────────────────────────
    bass_env = min(1.0, t * 3.0) * math.exp(-t * 0.45)   # フェードイン→ゆっくり減衰
    bass = math.sin(2 * math.pi * 55 * t) * bass_env * 0.45
    # 第2倍音で厚みを出す
    bass += math.sin(2 * math.pi * 110 * t) * bass_env * 0.12

    # ── Layer 2: トライトーン (悪魔の音程) ────────────────
    tri_env = min(1.0, t * 2.0) * math.exp(-t * 0.55)
    tri = math.sin(2 * math.pi * 77.78 * t) * tri_env * 0.28  # 55 * sqrt(2)

    # ── Layer 3: 不気味なコーラス ─────────────────────────
    # 3声部をわずかにデチューンして不安定な響きを作る
    tremolo = 0.7 + 0.3 * math.sin(2 * math.pi * 4.5 * t)  # 4.5 Hzトレモロ
    choir_env = max(0.0, min(1.0, (t - 0.3) * 2.0)) * math.exp(-t * 0.5)
    v1 = math.sin(2 * math.pi * 220.0  * t)   # A3
    v2 = math.sin(2 * math.pi * 261.3  * t)   # C4 (わずかにフラット)
    v3 = math.sin(2 * math.pi * 309.8  * t)   # Eb4 (短3度 = オカルト感)
    choir = (v1 * 0.14 + v2 * 0.12 + v3 * 0.10) * choir_env * tremolo

    # ── Layer 4: 初発インパクト (低周波ドン) ─────────────
    impact_env = math.exp(-t * 18.0) if t < 0.3 else 0.0
    # 低い倍音群をまとめて鳴らす（金属的なヒット感）
    impact = 0.0
    for f, a in [(60, 0.25), (80, 0.20), (120, 0.12), (180, 0.08)]:
        impact += math.sin(2 * math.pi * f * t) * a
    impact *= impact_env

    # ── Layer 5: ノイズバースト (インパクト直後のシャ) ────
    if t < 0.18:
        # 線形合同法による疑似ノイズ
        noise_raw = ((i * 1103515245 + 12345) & 0x7FFF) / 0x7FFF * 2 - 1
        noise = noise_raw * math.exp(-t * 25.0) * 0.30
    else:
        noise = 0.0

    # ── Layer 6: 低周波クレッシェンド (ゴロゴロ感) ────────
    rumble_freq = 38 + 10 * math.sin(2 * math.pi * 1.2 * t)   # うなり
    rumble_env  = min(1.0, t * 1.5) * math.exp(-t * 0.6) * 0.25
    rumble = math.sin(2 * math.pi * rumble_freq * t) * rumble_env

    # ── ミックス ────────────────────────────────────────
    v = (bass + tri + choir + impact + noise + rumble) * VOL
    samples.append(max(-1.0, min(1.0, v)))

out_path = "assets/music/boss_alert.wav"
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(struct.pack(f"{n}h", *(int(s * 32767) for s in samples)))

print(f"生成: {out_path}  ({DURATION}秒)")
