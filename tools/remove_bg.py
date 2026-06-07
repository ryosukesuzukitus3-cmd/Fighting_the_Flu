"""
背景削除ツール
各シード点からBFSで伝播し、隣接ピクセル同士の色差がtolerance以下なら背景とみなして透明化。
"""
from PIL import Image
import numpy as np
from collections import deque
from pathlib import Path


def remove_bg(path_in: str, path_out: str, tolerance: int = 35) -> None:
    img  = Image.open(path_in).convert("RGBA")
    data = np.array(img, dtype=np.int32)
    h, w = data.shape[:2]

    visited = np.zeros((h, w), dtype=bool)
    # (y, x, parent_rgb) を格納
    queue: deque = deque()

    # 4 隅 + 辺の中点をシード点に
    seeds = [
        (0, 0), (0, w-1), (h-1, 0), (h-1, w-1),
        (0, w//2), (h-1, w//2), (h//2, 0), (h//2, w-1),
    ]
    for (sy, sx) in seeds:
        if not visited[sy, sx]:
            visited[sy, sx] = True
            queue.append((sy, sx, data[sy, sx, :3].copy()))

    while queue:
        y, x, ref = queue.popleft()
        pixel = data[y, x, :3]
        dist  = float(np.sqrt(np.sum((pixel - ref) ** 2)))
        if dist <= tolerance:
            data[y, x, 3] = 0   # 透明化
            for ny, nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx, pixel.copy()))

    result = Image.fromarray(data.astype(np.uint8), "RGBA")
    bbox = result.getbbox()
    if bbox:
        result = result.crop(bbox)
    result.save(path_out)
    print(f"saved: {path_out}  size={result.size}")


BASE = Path(__file__).parent.parent / "assets" / "graphic"


def remove_bg_corners(path_in: str, path_out: str, tolerance: int = 28) -> None:
    """4コーナーのみをシードにする安全版（人物が辺端に接する画像向け）"""
    img  = Image.open(path_in).convert("RGBA")
    data = np.array(img, dtype=np.int32)
    h, w = data.shape[:2]

    visited = np.zeros((h, w), dtype=bool)
    queue: deque = deque()

    for sy, sx in [(0, 0), (0, w-1), (h-1, 0), (h-1, w-1)]:
        if not visited[sy, sx]:
            visited[sy, sx] = True
            queue.append((sy, sx, data[sy, sx, :3].copy()))

    while queue:
        y, x, ref = queue.popleft()
        pixel = data[y, x, :3]
        dist  = float(np.sqrt(np.sum((pixel - ref) ** 2)))
        if dist <= tolerance:
            data[y, x, 3] = 0
            for ny, nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx, pixel.copy()))

    result = Image.fromarray(data.astype(np.uint8), "RGBA")
    bbox = result.getbbox()
    if bbox:
        result = result.crop(bbox)
    result.save(path_out)
    print(f"saved: {path_out}  size={result.size}")


# 澤口: 原本は sawaguchi_49_64_original.png → 処理後 sawaguchi_49_64.png
# (人物が左辺に接しているため corners 版を使用、tolerance=28)
remove_bg_corners(
    str(BASE / "sawaguchi_49_64_original.png"),
    str(BASE / "sawaguchi_49_64.png"),
    tolerance=28,
)

# その他の敵キャラ（辺端に人物が接しない前提で全辺シード版）
other_targets = [
    ("enemy_タケシ.png",    35),
    ("enemy_ブロリー.png",  40),
]

for fname, tol in other_targets:
    src = BASE / fname
    dst = BASE / fname
    print(f"processing {fname} (tolerance={tol})...")
    remove_bg(str(src), str(dst), tolerance=tol)

print("done.")
