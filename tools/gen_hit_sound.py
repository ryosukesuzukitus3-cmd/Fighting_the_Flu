"""弾ヒット音(hit.wav)を合成して assets/music/ に保存する"""
import wave, struct, math

RATE     = 44100
DURATION = 0.08   # 秒
FREQ     = 1200   # ベース周波数 Hz
VOLUME   = 0.6

out_path = "assets/music/hit.wav"
n = int(RATE * DURATION)

samples = []
for i in range(n):
    t       = i / RATE
    decay   = math.exp(-t * 40)          # 急速減衰
    sine    = math.sin(2 * math.pi * FREQ * t * (1 - t * 3))  # 周波数ダウン
    noise   = ((i * 1103515245 + 12345) & 0x7FFF) / 0x7FFF * 2 - 1  # 簡易ノイズ
    v       = (sine * 0.6 + noise * 0.4) * decay * VOLUME
    samples.append(max(-1.0, min(1.0, v)))

with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(struct.pack(f"{n}h", *(int(s * 32767) for s in samples)))

print(f"生成: {out_path}")
