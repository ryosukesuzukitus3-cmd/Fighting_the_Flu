"""BGM_* / SE_* エイリアス → 実ファイルパスの一元マップ。

台本は BGM_TITLE / SE_TYPE のようなエイリアスで音を指定する。
ここで実ファイルへ解決する。未用意の音は None（呼び出し側は None を無視）。
未用意分は Phase 4 でダミー音を作成して差し替える。
"""
from __future__ import annotations

# ── BGM ────────────────────────────────────────────────────────────
BGM: dict[str, str | None] = {
    "BGM_TITLE":    "music/bgm/The_Final_Battle.mp3",
    "BGM_STAGE1":   "music/bgm/MEGALOVANIA.mp3",
    "BGM_STAGE2":   "music/bgm/戦艦ハルバード：甲板.mp3",
    "BGM_STAGE3":   "music/bgm/とげとげタルめいろ.mp3",
    "BGM_STAGE4":   "music/bgm/決戦.mp3",
    "BGM_BOSS":     "music/bgm/決戦.mp3",
    "BGM_FINAL":    "music/bgm/決戦.mp3",
    "BGM_EPILOGUE": None,                              # TODO(Phase4): 専用曲ダミー
    "BGM_CLEAR":    "music/bgm/FFVI_勝利のファンファーレ.mp3",
}

# ── SE ─────────────────────────────────────────────────────────────
SE: dict[str, str | None] = {
    "SE_TYPE":         None,                           # TODO(Phase4): タイプ音ダミー
    "SE_ALERT":        "music/se/boss_alert.wav",
    "SE_FIGHT":        "music/se/fight.wav",
    "SE_EXPLOSION":    "music/se/game_explosion9.mp3",
    "SE_HIT":          "music/se/hit.wav",
    "SE_PLAYER_HIT":   "music/se/shout.wav",
    "SE_ENEMY_SHOT":   "music/se/dummy_enemy_shot.wav",      # dummy（雑魚/砲台の発射）
    "SE_BOSS_SHOT":    "music/se/dummy_boss_shot.wav",       # dummy（ボスの発射）
    "SE_KARONARU_HIT": "music/se/dummy_karonaru_hit.wav",    # dummy（先輩 被弾）
    "SE_KARONARU_RETIRE": "music/se/dummy_karonaru_retire.wav",  # dummy（先輩 退場）
    "SE_LIGHT":        None,                           # TODO(Phase4)
    "SE_BLACKHOLE":    None,                           # TODO(Phase4)
    "SE_HEAL":         None,                           # TODO(Phase4)
    "SE_ERROR":        None,                           # TODO(Phase4)
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
