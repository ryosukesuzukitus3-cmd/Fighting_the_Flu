"""EnemyCrawler の登坂挙動テスト。

接地障害物を乗り越える／浮遊障害物は無視する／通路中央で頭打ち／
姿勢（回転）は変えない／1フレーム移動量が暴れない、を検証する。
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

from src.entities.terrain import make_terrain_strip, Terrain
from src.entities.enemies.crawler import EnemyCrawler, _CLIMB_SPEED


class _Cam:
    x = 0.0

    def to_screen_x(self, wx):
        return wx - self.x


class _Sound:
    @staticmethod
    def play_se_alias(*a, **k):
        pass


class _Game:
    sound = _Sound()


def _flat_strip(top_h=120, bottom_y=480, length=2000, seg_w=40):
    """side 付きの平坦な上下壁ストリップを手組みする。"""
    from src.entities.terrain import TerrainStripSegment
    from src.core.constants import SCREEN_HEIGHT
    segs = []
    n = length // seg_w
    for i in range(n):
        wx = i * seg_w
        segs.append(TerrainStripSegment(wx, 0, seg_w, top_h, side="top",
                                        theme="fever_cave", seed=1, index=i))
        segs.append(TerrainStripSegment(wx, bottom_y, seg_w, SCREEN_HEIGHT - bottom_y,
                                        side="bottom", theme="fever_cave", seed=1, index=i))
    return pygame.sprite.Group(*segs)


def _run(crawler, frames=400):
    cam = _Cam()
    dt = 1 / 60.0
    prev = crawler.world_y
    max_jump = 0.0
    sizes = set()
    ys = []
    for _ in range(frames):
        crawler.update(dt, cam)
        max_jump = max(max_jump, abs(crawler.world_y - prev))
        prev = crawler.world_y
        sizes.add(crawler.image.get_size())
        ys.append(crawler.world_y)
    return max_jump, sizes, ys


def test_bottom_crawler_climbs_grounded_obstacle():
    grp = _flat_strip(bottom_y=480)
    # 床(480)に接地した障害物（高さ100、上面=380）を進路上に置く
    grp.add(Terrain(900, 380, 120, 100, "clot"))
    c = EnemyCrawler(_Game(), 1500, 480 - 18, None, None, grp, surface="bottom")
    max_jump, sizes, ys = _run(c)
    # 障害物の上面(380)付近まで登る（床基準 462 から十分上へ）
    assert min(ys) < 430, f"climbed apex y={min(ys):.0f}"
    # 1フレーム移動量は登坂速度上限内（暴れない）
    assert max_jump <= _CLIMB_SPEED / 60.0 + 0.5, max_jump
    # 姿勢（回転）は変えない＝スプライト寸法は常に一定
    assert len(sizes) == 1, sizes


def test_floating_obstacle_is_ignored():
    grp = _flat_strip(bottom_y=480)
    # 床から大きく浮いた障害物（下面=300、床480から180px上）は登らない
    grp.add(Terrain(900, 240, 120, 60, "clot"))
    c = EnemyCrawler(_Game(), 1500, 480 - 18, None, None, grp, surface="bottom")
    _, _, ys = _run(c)
    # 床(462中心)付近を保ち、浮遊物には吸着しない
    assert min(ys) > 430, f"should stay near floor, got {min(ys):.0f}"


def test_climb_capped_at_passage_center():
    grp = _flat_strip(top_h=120, bottom_y=480)   # 通路中央 = 300
    # 床から天井近くまで届く極端に高い障害物
    grp.add(Terrain(900, 140, 120, 340, "clot"))
    c = EnemyCrawler(_Game(), 1500, 480 - 18, None, None, grp, surface="bottom")
    _, _, ys = _run(c)
    # 通路中央(300)より上には行かない（多少のマージン含む）
    assert min(ys) >= 300 - 20, f"exceeded center, y={min(ys):.0f}"


def test_top_crawler_climbs_onto_underside():
    grp = _flat_strip(top_h=120, bottom_y=480)
    # 天井(下面120)に接地して垂れ下がる障害物（下面=220）
    grp.add(Terrain(900, 120, 120, 100, "clot"))
    c = EnemyCrawler(_Game(), 1500, 120 + 18, None, None, grp, surface="top")
    max_jump, sizes, ys = _run(c)
    assert max(ys) > 160, f"top crawler should descend onto obstacle underside, y={max(ys):.0f}"
    assert max_jump <= _CLIMB_SPEED / 60.0 + 0.5, max_jump
    # 姿勢（回転）は変えない＝スプライト寸法は常に一定
    assert len(sizes) == 1, sizes
