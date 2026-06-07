"""マスターデータの単一定義ソース。

敵・アイテムの名前/SE/ドロップ情報はここだけに定義し、
他のモジュールは全てここから導出する。
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


# ── 敵定義 ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnemyDef:
    name: str           # "EnemyVirus" など stage JSON の type と一致
    label: str          # 日本語表示名（docs / balance_sheet 用）
    se: str | None      # 撃破SE パス（None = 共通SEのみ）
    se_volume: float = 0.0
    drop_chance: float = 0.0   # 雑魚ドロップ確率（0 = 確定ドロップ or 対象外）
    debug_spawnable: bool = True
    doc_movement: str = ""    # docs §2.4 移動パターン列
    doc_notes: str = "—"      # docs §2.4 備考列


ENEMY_DEFS: list[EnemyDef] = [
    EnemyDef("EnemyVirus",    "直進型",             "music/se/game_explosion9.mp3",   0.9, drop_chance=0.10, doc_movement="直進"),
    EnemyDef("EnemyTakeshi",  "波状移動型",          "music/se/お前ら人間じゃねぇ!.mp3", 0.45, drop_chance=0.10, doc_movement="波状移動"),
    EnemyDef("EnemyBroly",    "突進型",              "music/se/ブロリー_ヘェア！.mp3",   0.9, drop_chance=0.10, doc_movement="プレイヤーへ突進"),
    EnemyDef("EnemyPachemon", "ジグザグ＋狙い撃ち型", "music/se/でたぁ.mp3",              0.45, drop_chance=0.10, doc_movement="ジグザグ＋狙い撃ち", doc_notes="中強度、弾を撃つ"),
    EnemyDef("EnemyBilly",    "低速・高HP・確定Wドロップ", "music/se/アｯー♂.mp3",       1.0, drop_chance=0.0,  doc_movement="低速直進",           doc_notes="HP高い、撃破必ずWeaponItemドロップ"),
    EnemyDef("EnemyTurret",   "砲台（地形固定・狙撃）",   "music/se/game_explosion9.mp3",  0.7, drop_chance=0.10, doc_movement="固定（地形にスクロール追従）", doc_notes="自機を狙い撃ち、SE_ENEMY_SHOT"),
]

ENEMY_NAMES:   list[str]             = [d.name for d in ENEMY_DEFS]
ENEMY_BY_NAME: dict[str, EnemyDef]  = {d.name: d for d in ENEMY_DEFS}

# 雑魚ドロップ確率マップ（EnemyBilly は確定ドロップなので含まない）
ENEMY_DROP_CHANCE: dict[str, float] = {
    d.name: d.drop_chance for d in ENEMY_DEFS if d.drop_chance > 0
}


# ── アイテム定義 ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class ItemDef:
    name: str
    label: str
    drop_weight: int = 0   # random_item の抽選重み（0 = ランダムドロップ対象外）


ITEM_DEFS: list[ItemDef] = [
    ItemDef("WeaponItem",    "武器スロット選択",    drop_weight=1),
    ItemDef("HealItem",      "HP回復（+30）",       drop_weight=3),
    ItemDef("ScoreItem",     "スコア+1000",          drop_weight=1),
    ItemDef("ExtraLifeItem", "残機追加（1UP）",      drop_weight=0),
]

ITEM_NAMES:   list[str]            = [d.name for d in ITEM_DEFS]
ITEM_BY_NAME: dict[str, ItemDef]  = {d.name: d for d in ITEM_DEFS}


# ── ステージ番号（data/stages/*.json を単一ソースとする）──────────

def stage_ids() -> list[int]:
    """data/stages/stage*.json を走査してステージ番号を昇順で返す。"""
    stages_dir = Path(__file__).parent.parent.parent / "data" / "stages"
    ids: list[int] = []
    for p in sorted(stages_dir.glob("stage*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ids.append(int(data["stage_id"]))
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    return sorted(ids)
