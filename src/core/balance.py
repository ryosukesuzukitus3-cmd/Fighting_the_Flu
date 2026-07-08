"""
ゲームバランス定数の一元管理。
ステージ別のHP・速度スケールはここだけを編集すれば全敵に反映される。

使い方:
    from src.core.balance import ENEMY_HP_SCALE, ENEMY_SPD_SCALE
    hp    = max(1, round(base_hp    * ENEMY_HP_SCALE.get(stage_id, 1.0)))
    speed = base_speed * ENEMY_SPD_SCALE.get(stage_id, 1.0)
"""

# ── ステージ別スケール ───────────────────────────────────────────
# Stage2 は HP 2.5倍 / Speed 1.3倍、Stage3 は HP 8倍 / Speed 1.7倍
ENEMY_HP_SCALE: dict[int, float] = {
    1: 1.0,
    2: 2.0,
    3: 3.0,
    4: 5.0,
}

ENEMY_SPD_SCALE: dict[int, float] = {
    1: 1.0,
    2: 1.3,
    3: 1.7,
    4: 2.0,
}

# ── プレイヤー HP / 被ダメージ設計（HP ゲージ・最大100）─────────────
PLAYER_MAX_HP        = 100   # 多段階 HP ゲージの最大値
PLAYER_INVINCIBLE    = 0.8   # 被弾後の無敵時間（秒）

# 被ダメージ量（被弾源別）
PLAYER_DMG_ENEMY     = 15    # 雑魚との接触
PLAYER_DMG_BULLET    = 10    # 敵弾・ボス弾（EnemyBullet.damage 未指定時の既定）
PLAYER_DMG_BOSS      = 25    # ボス本体との接触
PLAYER_DMG_TERRAIN   = 8     # 地形との接触（i-frame で連続接触を間引く）

HEAL_AMOUNT          = 30    # HealItem の回復量

# 先輩（カロナール）が接触した敵へ与える反撃ダメージ
KARONARU_CONTACT_DMG = 12


# ════════════════════════════════════════════════════════════════════
# バトルシステムv2（体幹 / 体温オーバーヒート / 持ち駒ボム / 症状悪化）
#   純ロジックは src/core/battle_systems.py、配線は game_scene / boss.py。
# ════════════════════════════════════════════════════════════════════
# お披露目直前に旧挙動へ戻すための一括スイッチ（False で v2 全系統を無効化）
BATTLE_V2_ENABLED = True

# ── 体幹（ボス）──────────────────────────────────────────────────
# ゲージ最大値（形態キー別）。0 のボス（turrets=マッチング・ゼロ）は
# サクラ子機の生存数がそのまま体幹の代わりになる（ゲージは子機比率表示）。
STANCE_MAX: dict[str | int, float] = {
    1: 60.0,        # 悪寒大王インフルX（shield: シールド解除中のみ削れる）
    2: 55.0,        # ブロリー（weakpoint: 旧「装甲」を体幹へ統合）
    "2f2": 70.0,    # 超サイヤ人ブロリー（ギミック無し形態にも体幹で攻略軸を作る）
    3: 0.0,         # マッチング・ゼロ（サクラ子機が体幹の代替）
    4: 80.0,        # 藤井竜王 Form1（shield）
    "4f2": 75.0,    # 赤眼の真・藤井四段（weakpoint）
    # "4f3" 頑固王サワグチはスクリプト演出が主役のため体幹対象外
}
STANCE_DOWN_DUR    = 4.0    # 体幹ブレイク時のダウン時間（秒。weakpoint は既存の露出5秒）
STANCE_DOWN_MULT   = 2.0    # ダウン中の被ダメ倍率（weakpoint 露出 / turrets スタンも統一）
STANCE_REGEN_DELAY = 2.0    # 体幹を削られなくなってから回復が始まるまで（秒）
STANCE_REGEN_RATE  = 3.0    # 体幹の自然回復速度（/秒）＝チクチク削りっぱなし防止

# 武器別の体幹ダメージ（1ヒットあたり）。レーザー＝体幹ブレイカー。
STANCE_MAIN       = 2.0
STANCE_HOMING     = 1.0
STANCE_LASER_TICK = 3.0

# ── 体温オーバーヒート（プレイヤー）─────────────────────────────
# 射撃で体温が上がり、撃たなければ下がる。39.9℃で「熱暴走」＝一定時間
# メイン/レーザー射撃不可（ホーミングは撃てる）。先輩の解熱弾Lvが冷却を強化。
HEAT_MAX            = 100.0
HEAT_PER_SHOT       = 2.4    # メイン1射撃（1トリガー）あたり
HEAT_PER_LASER      = 26.0   # レーザー1発射あたり
HEAT_COOL_RATE      = 12.0   # 基礎冷却（/秒）。無強化の初期連射では過熱しない設計
HEAT_COOL_KARONARU  = 3.0    # 先輩・解熱弾Lv1につき加算される冷却（/秒）
HEAT_BOSS_DOWN_MULT = 2.0    # ボスダウン中の冷却倍率（＝ダウン中は全部撃ってよい）
OVERHEAT_DURATION   = 2.8    # 熱暴走の射撃ロック時間（秒）
HEAT_AFTER_OVERHEAT = 45.0   # 熱暴走明けの体温（すぐ再過熱しない程度に残す）
HEAT_TEMP_MIN       = 36.5   # 表示用: ゲージ0%の体温
HEAT_TEMP_MAX       = 39.9   # 表示用: ゲージ100%の体温

# ── 持ち駒ボム（コンボ報酬・Bキーで「打つ」）────────────────────
# 閾値はヘッドレス実測（直進連射で combo 最大3程度）に合わせた初期値。実機で要調整
PIECE_COMBO_THRESHOLDS: dict[int, str] = {6: "歩", 14: "金", 25: "龍"}
PIECE_MAX_HELD = 3
# 駒種 → (雑魚ダメージ, ボスHPダメージ, ボス体幹ダメージ, 無敵時間秒)
PIECE_EFFECTS: dict[str, tuple[int, int, float, float]] = {
    "歩": (25,  8, 18.0, 0.0),
    "金": (40, 25, 45.0, 0.8),
    "龍": (60, 55, 90.0, 1.2),
}

# ── 症状悪化（ボスのエンレイジ。待ち戦法への対抗）───────────────
ENRAGE_T0       = 40.0   # 発動開始（フェーズ経過秒）
ENRAGE_T1       = 85.0   # 最大到達（秒）
ENRAGE_MAX_MULT = 1.4    # 攻撃間隔の短縮倍率（interval / mult）。Form3 は対象外
