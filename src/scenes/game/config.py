"""
game_scene 専用の定数・設定値。
ここを編集すればゲームバランスに一括反映される。
"""
from __future__ import annotations
from pathlib import Path

# ── アセットパス ─────────────────────────────────────────────────
ROUNDS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "music" / "rounds"

# ── アイテムドロップ確率（敵強度別）──────────────────────────────
# registries.ENEMY_DROP_CHANCE を単一ソースとする
from src.core.registries import ENEMY_DROP_CHANCE as DROP_CHANCE

# ── ボス撃破後の遷移 ────────────────────────────────────────────
POST_BOSS_AUTO_TIMEOUT  = 30.0   # 通常ボス: 30秒で自動遷移
POST_BOSS_FINAL_TIMEOUT = 2.4    # ラスボス: 短い余韻のあと自動クリア
POST_BOSS_EDGE_MARGIN   = 30     # 右端から何px以内で次ステージ遷移
MAGNET_SPEED            = 90.0   # ボス後アイテム引き寄せ速度 px/秒
FINAL_SLOW_FACTOR       = 0.18   # ラスボス撃破時スロー倍率

# ── マグネット段階設定: レベル別 (引き寄せ半径px, 速度px/s) ─────
MAGNET_CONFIG: dict[int, tuple[float, float]] = {
    0: (0,    0),
    1: (130,  60),
    2: (260, 140),
    3: (9999, 240),  # 全画面
}

# ── ステージ名バナー ────────────────────────────────────────────
STAGE_NAMES: dict[int, tuple[str, str, str]] = {
    1: ("第一章", "発熱回廊",          "寒い。熱い。まずは、この熱そのものを撃ち落とすしかない。"),
    2: ("第二章", "ミーム汚染地帯",    "熱で弱ってる時ほど、余計な言葉はよく刺さるものだ…"),
    3: ("第三章", "婚活・労働複合戦線", "その「ちゃんと」が、何も保証してくれないことも。"),
    4: ("第四章", "棋理深淵",          "将棋だけは、盤面が正直だと思っていた。"),
}
STAGE_BANNER_DURATION = 3.0   # 秒

# ── ボス名 ─────────────────────────────────────────────────────
BOSS_NAMES: dict[int, str] = {
    1: "悪寒大王インフルX",
    2: "情報汚染超人野獣ブロリー",
    3: "婚活要塞マッチング・ゼロ",
    4: "棋理の化身　藤井竜王",
}
BOSS_NAME_DURATION = 2.5   # 秒

# ── ボス戦BGM（ステージ別・SSOT）─────────────────────────────────
BOSS_BGM: dict[int, str] = {
    1: "music/bgm/決戦.mp3",
    2: "music/bgm/決戦！N_short.mp3",
    3: "music/bgm/決戦！N_short.mp3",
    4: "music/bgm/決戦_FF10.mp3",   # ラスボス（先輩復帰で Rebirth_the_edge に切替）
}

# ── ボスセリフ（内容は src/story/script.py が SSOT）───────────────
# BOSS_INTRO（登場時・ENTER送り）/ BOSS_MID（戦闘中・自動順送り）/
# BOSS_DEFEAT（撃破後・ENTER送り）は story.script を参照すること。
BOSS_DIALOGUE_DURATION = 4.0   # 秒（戦闘中セリフ1行の既定表示時間）
BOSS_MID_LINE_DURATION = 3.0   # 秒（mid/form2 のキュー1行あたり表示時間）

# ── ボス演出タイミング ───────────────────────────────────────
ALERT_DURATION        = 2.0   # ALERT表示秒数
FIGHT_BANNER_DURATION = 1.2   # FIGHT!表示秒数

# ── コンボシステム ───────────────────────────────────────────
COMBO_WINDOW = 3.0   # 秒以内に次の撃破でコンボ継続
COMBO_MIN    = 3     # この連続数からコンボ表示＆スコア倍率開始

def combo_multiplier(count: int) -> int:
    """コンボ数 → スコア倍率"""
    if count >= 20: return 8
    if count >= 10: return 4
    if count >= 5:  return 2
    return 1

# ── グラディウス式ウェポン選択スロット ─────────────────────────
UPGRADE_SLOTS: list[tuple[str, str]] = [
    ("weapon_main", "MAIN UP"),
    ("homing",      "HOMING"),
    ("laser",       "LASER"),
    ("speed",       "SPEED"),
    ("barrier",     "BARRIER"),
    ("magnet",      "MAGNET"),
]
MAIN_NEXT_NAMES = ["RAPID1", "RAPID2", "WIDE", "WIDE+", "MEDIC", "(MAX)"]

# ── コンティニュー時ウェポン初期状態 ────────────────────────────
# main_level: 0=single,1=rapid1,2=rapid2,3=wide1,4=wide2,5=medic
CONTINUE_WEAPON: dict[int, dict] = {
    1: {},
    2: {"main_level": 2, "speed_level": 1},
    3: {"main_level": 2, "speed_level": 3, "has_barrier": True},
    4: {"main_level": 4, "speed_level": 4, "has_barrier": True},
}


# ── ユーティリティ ───────────────────────────────────────────────

def random_item(world_x: float, world_y: float, *, spread: float = 0.0):
    """ランダムアイテムを1つ生成する。重みは registries.ITEM_DEFS.drop_weight で管理。"""
    from src.core.factories import random_item as _random_item
    return _random_item(world_x, world_y, spread=spread)
