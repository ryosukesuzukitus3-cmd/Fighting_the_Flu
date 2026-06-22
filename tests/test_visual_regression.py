"""ビジュアル回帰の SSOT ガード：ショット行列に baseline 画像が揃っているか。

レンダリングはしない（速い）。ショットを足したのに baseline を生成し忘れた、を捕まえる。
実際のピクセル比較は `tools/run.py visual-regress`（目視レビュー用、CIゲートではない）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.visual_regression import BASELINE_DIR, SHOTS  # noqa: E402


def test_every_shot_has_a_baseline():
    missing = [name for name in SHOTS if not (BASELINE_DIR / f"{name}.png").exists()]
    assert not missing, (
        f"baseline 未生成のショット: {missing}  "
        f"→ `python tools/run.py visual-regress --update` を実行"
    )
