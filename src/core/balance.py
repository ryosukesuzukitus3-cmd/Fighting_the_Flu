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
