"""BGM_* / SE_* エイリアス → 実ファイルパスの一元マップ。

台本は BGM_TITLE / SE_TYPE のようなエイリアスで音を指定する。
ここで実ファイルへ解決する。未用意の音は None（呼び出し側は None を無視）。
未用意分は Phase 4 でダミー音を作成して差し替える。
"""
from __future__ import annotations

# ── BGM ────────────────────────────────────────────────────────────
BGM: dict[str, str | None] = {
    "BGM_TITLE":    "music/bgm/The_Final_Battle_short.mp3",
    "BGM_STAGE1":   "music/bgm/MEGALOVANIA.mp3",
    "BGM_STAGE2":   "music/bgm/戦艦ハルバード：甲板.mp3",
    "BGM_STAGE3":   "music/bgm/とげとげタルめいろ.mp3",
    "BGM_STAGE4":   "music/bgm/決戦.mp3",
    "BGM_BOSS":     "music/bgm/決戦.mp3",
    "BGM_BOSS_FORM2": "music/bgm/決戦.mp3",             # 仮：第2形態専用曲は後で差し替え
    "BGM_FINAL":    "music/bgm/決戦.mp3",
    "BGM_BLACKHOLE": "music/bgm/The_world_of_spirit.mp3",  # 仮：インターステラー系（後で差し替え）
    "BGM_EPILOGUE": None,                              # TODO(Phase4): 専用曲ダミー
    "BGM_CLEAR":    "music/bgm/FFVI_勝利のファンファーレ.mp3",
    "BGM_CREDITS":  "music/bgm/il_vento_d'oro.mp3",
}

# ── SE ─────────────────────────────────────────────────────────────
SE: dict[str, str | None] = {
    "SE_TYPE":         "music/se/type.wav",
    "SE_ITEM":         "music/se/item_pickup.wav",
    "SE_ITEM_WEAPON":  "music/se/item_weapon_pickup.wav",
    "SE_ITEM_HEAL":    "music/se/item_heal_pickup.wav",
    "SE_ALERT":        "music/se/boss_alert.wav",
    # ── 以下の dummy/仮 スロットは candidates/ の候補1番を仮配線（採用未定）。
    #    各スロットの別案とライセンスは assets/music/se/candidates/README.md 参照。
    "SE_BOSS_TRANSFORM": "music/se/candidates/boss_transform/01_soundeffectlab_doon1.mp3",  # dummy候補（形態変化スティンガー）
    "SE_FIGHT":        "music/se/fight.wav",
    "SE_EXPLOSION":    "music/se/game_explosion9.mp3",
    "SE_HIT":          "music/se/hit.wav",
    "SE_PLAYER_HIT":   "music/se/shout.wav",
    "SE_NORMALSHOT":   "music/se/candidates/normalshot/01_soundeffectlab_shot1.mp3",  # dummy候補（通常弾。旧: ウェポン：normalshot_shot.mp3）
    "SE_ENEMY_SHOT":   "music/se/candidates/enemy_shot/01_soundeffectlab_handgun-firing1.mp3",  # dummy候補（雑魚/砲台の発射）
    "SE_BOSS_SHOT":    "music/se/candidates/boss_shot/01_soundeffectlab_cannon1.mp3",  # dummy候補（ボスの発射）
    "SE_LASER_FIRE":   "music/se/laser_fire.mp3",            # ブロリー粒子砲の発射音

    "SE_KARONARU_HIT": "music/se/candidates/karonaru_hit/01_soundeffectlab_boyoyon1.mp3",  # dummy候補（先輩 被弾・コミカル）
    "SE_KARONARU_RETIRE": "music/se/candidates/karonaru_retire/01_soundeffectlab_flee1.mp3",  # dummy候補（先輩 退場）
    "SE_KARONARU_ARRIVE": "music/se/candidates/karonaru_arrive/01_soundeffectlab_shakin1.mp3",  # dummy候補（先輩 登場・シャキーン）
    "SE_LIGHT":        "music/se/candidates/light/01_soundeffectlab_eye-shine1.mp3",  # dummy候補（白閃光のキラーン）
    "SE_BLACKHOLE":    "music/se/candidates/blackhole_rumble/01_soundeffectlab_earth-tremor1.mp3",  # dummy候補（ズゴゴ重低音）
    "SE_HEAL":         "music/se/item_heal_pickup.wav",
    "SE_ERROR":        "music/se/candidates/error/01_soundeffectlab_beep4.mp3",  # dummy候補（エラー音）
    "SE_SHOGI_PLACE":  "music/se/candidates/shogi_place/01_tairakomori_Shogi1.mp3",  # dummy候補（駒を打つ「ピシッ」）
}


def bgm_path(alias: str | None) -> str | None:
    """BGM エイリアス（または生パス）を実パスに解決する。"""
    if alias is None:
        return None
    return BGM.get(alias, alias)


def se_path(alias: str | None) -> str | None:
    """SE エイリアス（または生パス）を実パスに解決する。未用意なら None。"""
    if alias is None:
        return None
    return SE.get(alias, alias)
