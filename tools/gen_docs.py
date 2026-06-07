"""design.md の AUTOGEN ブロックをコードから再生成する。

使い方:
  python tools/gen_docs.py           # design.md を上書き更新
  python tools/gen_docs.py --check   # 差分チェックのみ（書き込まない）。差分あり→exit 1

AUTOGEN ブロック形式:
  <!-- AUTOGEN:<key> START -->
  （生成内容）
  <!-- AUTOGEN:<key> END -->
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# pygame をダミードライバで無音起動（Sound 系モジュールのインポート対策）
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

DESIGN_MD = ROOT / "docs" / "design.md"


# ── ブロック生成関数 ──────────────────────────────────────────────────

def _gen_enemies() -> str:
    from src.core.registries import ENEMY_DEFS
    rows = ["| 敵種別 | 移動パターン | 備考 |", "|---|---|---|"]
    for d in ENEMY_DEFS:
        rows.append(f"| {d.name} | {d.doc_movement} | {d.doc_notes} |")
    rows.append("| Boss | フェーズ制（HPに応じて攻撃パターン変化） | ステージごとに固有セリフ・演出 |")
    return "\n".join(rows)


def _gen_items() -> str:
    from src.core.registries import ITEM_DEFS
    rows = ["| 種別 | 効果 |", "|---|---|"]
    for d in ITEM_DEFS:
        rows.append(f"| {d.name} | {d.label} |")
    return "\n".join(rows)


def _gen_balance() -> str:
    from src.core.balance import ENEMY_HP_SCALE, ENEMY_SPD_SCALE
    stages = sorted(set(ENEMY_HP_SCALE) | set(ENEMY_SPD_SCALE))
    rows = ["| ステージ | HPスケール | 速度スケール |", "|---|---|---|"]
    for s in stages:
        hp_s  = ENEMY_HP_SCALE.get(s, 1.0)
        spd_s = ENEMY_SPD_SCALE.get(s, 1.0)
        rows.append(f"| Stage{s} | {hp_s}× | {spd_s}× |")
    return "\n".join(rows)


def _gen_weapon_main() -> str:
    from src.entities.weapon import _MAIN_LEVELS  # type: ignore[attr-defined]
    _DESCRIPTIONS = {
        "single": "正面に弾1発（発射間隔0.25s）",
        "rapid1": "連射（発射間隔0.15s）",
        "rapid2": "超連射（発射間隔0.12s）",
        "wide1":  "正面＋斜め 2本発射",
        "wide2":  "正面＋斜め 3本発射",
        "medic":  "回復弾追加（メディックモード）",
    }
    rows = ["| レベル | 種別 | 効果 |", "|---|---|---|"]
    for lv, name in enumerate(_MAIN_LEVELS):
        desc = _DESCRIPTIONS.get(name, "—")
        rows.append(f"| {lv} | {name} | {desc} |")
    return "\n".join(rows)


# ブロックキー → 生成関数のマッピング
_GENERATORS = {
    "enemies":      _gen_enemies,
    "items":        _gen_items,
    "balance":      _gen_balance,
    "weapon_main":  _gen_weapon_main,
}


# ── マーカー置換ロジック ────────────────────────────────────────────

def _replace_blocks(text: str) -> tuple[str, list[str]]:
    """AUTOGEN ブロックを再生成し、(新テキスト, 更新されたキー一覧) を返す。"""
    import re
    updated: list[str] = []

    def replacer(m: re.Match) -> str:
        key = m.group(1)
        if key not in _GENERATORS:
            return m.group(0)  # 未知キーはそのまま
        content = _GENERATORS[key]()
        updated.append(key)
        start_marker = f"<!-- AUTOGEN:{key} START -->"
        end_marker   = f"<!-- AUTOGEN:{key} END -->"
        return f"{start_marker}\n{content}\n{end_marker}"

    new_text = re.sub(
        r"<!-- AUTOGEN:(\w+) START -->.*?<!-- AUTOGEN:\1 END -->",
        replacer,
        text,
        flags=re.DOTALL,
    )
    return new_text, updated


# ── エントリーポイント ────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="design.md の AUTOGEN ブロックを再生成する")
    parser.add_argument("--check", action="store_true",
                        help="差分チェックのみ（書き込まない）。差分あり→exit 1")
    args = parser.parse_args()

    original = DESIGN_MD.read_text(encoding="utf-8")
    new_text, updated = _replace_blocks(original)

    if args.check:
        if new_text != original:
            print("AUTOGEN DRIFT: design.md の以下のブロックが最新ではありません:", file=sys.stderr)
            for key in updated if updated else ["(不明)"]:
                print(f"  - {key}", file=sys.stderr)
            sys.exit(1)
        print("OK: design.md AUTOGEN ブロックは最新です。")
    else:
        if new_text == original:
            print("gen_docs: no changes (design.md is already up-to-date)")
        else:
            DESIGN_MD.write_text(new_text, encoding="utf-8")
            for key in updated:
                print(f"gen_docs: updated <!-- AUTOGEN:{key} --> in design.md")


if __name__ == "__main__":
    main()
