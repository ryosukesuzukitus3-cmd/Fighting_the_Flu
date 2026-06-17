"""マスターデータの単一定義ソース。

敵・アイテムの名前/SE/ドロップ情報はここだけに定義し、
他のモジュールは全てここから導出する。
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path


# ── 敵定義 ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnemyStats:
    base_hp: int
    base_speed: float
    enhanced_hp: int
    enhanced_speed: float
    note: str = ""


@dataclass(frozen=True)
class EnemyDef:
    name: str           # "EnemyVirus" など stage JSON の type と一致
    label: str          # 日本語表示名（docs / balance_sheet 用）
    se: str | None      # 撃破SE パス（None = 共通SEのみ）
    se_volume: float = 0.0
    drop_chance: float = 0.0   # 雑魚ドロップ確率（0 = 確定ドロップ or 対象外）
    stats: EnemyStats | None = None
    debug_spawnable: bool = True
    doc_movement: str = ""    # docs §2.4 移動パターン列
    doc_notes: str = "—"      # docs §2.4 備考列


ENEMY_DEFS: list[EnemyDef] = [
    EnemyDef("EnemyVirus",    "直進型",             "music/se/game_explosion9.mp3",   0.9, drop_chance=0.10, stats=EnemyStats(1, 160.0, 3, 210.0, "直進"), doc_movement="直進"),
    EnemyDef("EnemyTakeshi",  "波状移動型",          "music/se/お前ら人間じゃねぇ!.mp3", 0.45, drop_chance=0.10, stats=EnemyStats(2, 110.0, 6, 145.0, "sin波"), doc_movement="波状移動"),
    EnemyDef("EnemyBroly",    "突進型",              "music/se/ブロリー_ヘェア！.mp3",   0.9, drop_chance=0.10, stats=EnemyStats(5, 80.0, 14, 100.0, "突進(charge:520→650)"), doc_movement="プレイヤーへ突進"),
    EnemyDef("EnemyPachemon", "ジグザグ＋狙い撃ち型", "music/se/でたぁ.mp3",              0.45, drop_chance=0.10, stats=EnemyStats(3, 130.0, 8, 170.0, "ジグザグ+狙撃"), doc_movement="ジグザグ＋狙い撃ち", doc_notes="中強度、弾を撃つ"),
    EnemyDef("EnemyCoughSprayer", "咳スプレー中ボス", "music/se/game_explosion9.mp3",     0.75, drop_chance=0.35, stats=EnemyStats(34, 260.0, 62, 310.0, "前方滞空+扇状咳弾"), doc_movement="画面右前方に滞空し扇状射撃", doc_notes="高HPの中ボス枠、短い間隔で小型弾を散布"),
    EnemyDef("EnemySporeSplitter", "胞子分裂中ボス",  "music/se/game_explosion9.mp3",     0.85, drop_chance=0.45, stats=EnemyStats(46, 230.0, 82, 285.0, "前方滞空+撃破で胞子ポッド分裂"), doc_movement="画面右前方に滞空・撃破時に分裂", doc_notes="高HPの中ボス枠、倒すと小型胞子ポッドを放出"),
    EnemyDef("EnemySporePod", "胞子ポッド",           "music/se/game_explosion9.mp3",     0.35, drop_chance=0.0, stats=EnemyStats(2, 0.0, 4, 0.0, "分裂時の慣性飛散"), debug_spawnable=False, doc_movement="分裂時の慣性で飛散", doc_notes="胞子分裂型の撃破後に残る二次目標"),
    EnemyDef("EnemyBilly",    "低速・高HP・確定Wドロップ", "music/se/アｯー♂.mp3",       1.0, drop_chance=0.0,  stats=EnemyStats(18, 45.0, 18, 45.0, "高HP・鈍足・確定W(強化なし)"), doc_movement="低速直進",           doc_notes="HP高い、撃破必ずWeaponItemドロップ"),
    EnemyDef("EnemyTurret",   "砲台（地形固定・狙撃）",   "music/se/game_explosion9.mp3",  0.7, drop_chance=0.10, stats=EnemyStats(6, 0.0, 12, 0.0, "地形固定(速度0)・狙撃"), doc_movement="固定（地形にスクロール追従）", doc_notes="自機を狙い撃ち、SE_ENEMY_SHOT"),
    EnemyDef("EnemyCrawler",  "地形走行型",          "music/se/game_explosion9.mp3",  0.7, drop_chance=0.12, stats=EnemyStats(5, 78.0, 11, 105.0, "地形表面を走行・狙撃"), doc_movement="地形表面を走行", doc_notes="上下地形に吸着して移動しながら狙い撃ち"),
    EnemyDef("EnemyDebrisLarge", "大型回転デブリ",    "music/se/game_explosion9.mp3",  0.8, drop_chance=0.18, stats=EnemyStats(14, 70.0, 24, 92.0, "回転・破壊で小デブリ化"), doc_movement="回転しながら直進", doc_notes="撃破時に小デブリへ分裂、接触ダメージ"),
    EnemyDef("EnemyDebrisShard", "小型破片デブリ",    "music/se/game_explosion9.mp3",  0.45, drop_chance=0.04, stats=EnemyStats(3, 0.0, 5, 0.0, "大型デブリ破片"), doc_movement="分裂時の慣性で飛散", doc_notes="大型デブリ破壊後に残る二次目標"),
]

ENEMY_NAMES:   list[str]             = [d.name for d in ENEMY_DEFS]
ENEMY_BY_NAME: dict[str, EnemyDef]  = {d.name: d for d in ENEMY_DEFS}


def enemy_stats(name: str) -> EnemyStats:
    stats = ENEMY_BY_NAME[name].stats
    if stats is None:
        raise KeyError(f"enemy stats are not defined: {name}")
    return stats

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
    ItemDef("WeaponItem",    "武器スロット選択",    drop_weight=0),
    ItemDef("HealItem",      "HP回復（+30）",       drop_weight=3),
]

ITEM_NAMES:   list[str]            = [d.name for d in ITEM_DEFS]
ITEM_BY_NAME: dict[str, ItemDef]  = {d.name: d for d in ITEM_DEFS}


# ── ステージ番号（data/stages/*.json を単一ソースとする）──────────

def stage_ids() -> list[int]:
    """data/stages/stage*.json を走査してステージ番号を昇順で返す。"""
    stages_dir = Path(__file__).parent.parent.parent / "data" / "stages"
    ids: list[int] = []
    for p in sorted(stages_dir.glob("stage*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("debug"):
            continue
        ids.append(int(data["stage_id"]))
    return sorted(ids)
