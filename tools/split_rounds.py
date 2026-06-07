"""
round1_fight.wav を無音検出で分割し、
assets/music/rounds/ に round1.wav～round9.wav, final.wav として保存する。
使い方: python tools/split_rounds.py
"""
import wave
import struct
import math
from pathlib import Path

SRC = Path("assets/music/round1_fight.wav")
OUT = Path("assets/music/rounds")
OUT.mkdir(exist_ok=True)

SILENCE_THRESH_RMS = 200   # この値未満をサイレンスとみなす
MIN_SILENCE_FRAMES = 2000  # サイレンスと判断する最小フレーム数
MIN_CLIP_FRAMES    = 4000  # この長さ以下のクリップは無視する


def rms(frames_bytes: bytes, sampwidth: int) -> float:
    fmt = {1: "b", 2: "h", 4: "i"}[sampwidth]
    n   = len(frames_bytes) // sampwidth
    if n == 0:
        return 0.0
    samples = struct.unpack(f"{n}{fmt}", frames_bytes)
    return math.sqrt(sum(s * s for s in samples) / n)


def split_wav(src: Path):
    with wave.open(str(src), "rb") as wf:
        nch      = wf.getnchannels()
        sw       = wf.getsampwidth()
        fr       = wf.getframerate()
        n_frames = wf.getnframes()
        raw      = wf.readframes(n_frames)
        params   = wf.getparams()

    frame_bytes = nch * sw
    chunk       = 512   # RMS計算単位 (フレーム数)

    # チャンクごとに RMS を計算
    chunks_rms = []
    for i in range(0, n_frames, chunk):
        start = i * frame_bytes
        end   = min((i + chunk) * frame_bytes, len(raw))
        chunks_rms.append(rms(raw[start:end], sw))

    # 無音区間を検出し、クリップ境界を割り出す
    in_silence  = chunks_rms[0] < SILENCE_THRESH_RMS
    silence_len = 0
    clips       = []
    clip_start  = 0

    for idx, r in enumerate(chunks_rms):
        is_silent = r < SILENCE_THRESH_RMS
        if is_silent:
            silence_len += chunk
            if not in_silence and silence_len >= MIN_SILENCE_FRAMES:
                # サイレンス開始 → クリップ終端
                clips.append((clip_start, idx * chunk))
                in_silence = True
        else:
            if in_silence:
                clip_start  = idx * chunk
                silence_len = 0
                in_silence  = False

    # 最後のクリップ
    if not in_silence:
        clips.append((clip_start, n_frames))

    # 短すぎるクリップを除去
    clips = [(s, e) for s, e in clips if (e - s) >= MIN_CLIP_FRAMES]

    # 偶数個ある場合はペアで結合（"ROUND X" + "FIGHT!" を1クリップに）
    if len(clips) % 2 == 0:
        paired = []
        for i in range(0, len(clips), 2):
            paired.append((clips[i][0], clips[i + 1][1]))
        clips = paired
        print(f"ペア結合後クリップ数: {len(clips)}")

    names = [f"round{i+1}" for i in range(9)] + ["final"]

    for i, (start_f, end_f) in enumerate(clips):
        name = names[i] if i < len(names) else f"extra{i}"
        out_path = OUT / f"{name}.wav"
        start_b = start_f * frame_bytes
        end_b   = end_f   * frame_bytes
        clip_data = raw[start_b:end_b]

        with wave.open(str(out_path), "wb") as wo:
            wo.setnchannels(nch)
            wo.setsampwidth(sw)
            wo.setframerate(fr)
            wo.writeframes(clip_data)
        dur = (end_f - start_f) / fr
        print(f"  {out_path.name}: {dur:.2f}s")

    if len(clips) < len(names):
        print(f"警告: 期待{len(names)}クリップ、実際{len(clips)}クリップ")


if __name__ == "__main__":
    split_wav(SRC)
    print("分割完了")
